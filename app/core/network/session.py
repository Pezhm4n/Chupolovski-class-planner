# -*- coding: utf-8 -*-
"""
Golestoon Core Network Session Transport.

This module provides the NetworkSession wrapper around `requests.Session`.
It handles TCP connection pooling, HTTP Keep-Alive, automatic JWT header injection,
SSL enforcement, request/response logging redaction, and exception translation.

Architecture Layer: Layer 1 (Network Session Infrastructure)
Dependencies: `requests`, `urllib3`, `TokenManager`, `NetworkConfig`, `exceptions`, `logger`.
"""

import json
from typing import Dict, Any, Optional, Tuple, Union, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.auth.token_manager import TokenManager
from app.core.network.config import NetworkConfig
from app.core.network.exceptions import (
    GolestoonNetworkError,
    ConnectionFailedError,
    TimeoutError,
    ApiHttpError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationApiError,
)
from app.core.network.logger import get_network_logger

logger = get_network_logger("golestoon.network.session")


class NetworkSession:
    """
    Thread-safe HTTP Session wrapper managing connection pooling, Keep-Alive,
    JWT header injection, SSL verification, and exception mapping.
    """

    def __init__(
        self,
        config: Optional[NetworkConfig] = None,
        token_manager: Optional[TokenManager] = None
    ) -> None:
        self.config: NetworkConfig = config or NetworkConfig()
        self.token_manager: Optional[TokenManager] = token_manager
        self._session: requests.Session = requests.Session()
        self._configure_session()

    def _configure_session(self) -> None:
        """Configure internal requests.Session headers, SSL, and connection adapters."""
        headers = self.config.get_default_headers()
        self._session.headers.update(headers)
        self._session.verify = self.config.ssl_verify

        # Configure connection pool adapter with zero auto-retries on socket failures
        # (retries are handled explicitly in the business logic layer)
        adapter = HTTPAdapter(
            pool_connections=self.config.pool_connections,
            pool_maxsize=self.config.pool_maxsize,
            max_retries=Retry(total=0, connect=0, read=0)
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _apply_auth_header(self, headers: Dict[str, str]) -> None:
        """Inject Authorization header if a valid token is available in TokenManager."""
        if self.token_manager and self.token_manager.has_valid_token():
            token = self.token_manager.get_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

    # Methods that are safe to transparently retry when the server closes an
    # idle keep-alive connection mid-request (RemoteDisconnected races).
    IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Tuple[int, int]] = None,
        is_proxy: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request against the backend server.

        Idempotent methods (GET/HEAD/OPTIONS) are retried once on transient
        connection failures (server closing a pooled keep-alive socket),
        which otherwise surfaces as spurious ConnectionFailedError bursts.

        Args:
            method (str): HTTP method ('GET', 'POST', 'PUT', 'DELETE').
            endpoint (str): Relative REST API endpoint path (e.g. '/api/auth/login').
            data (Optional[Union[Dict, List]]): Request payload body.
            params (Optional[Dict]): Query parameters.
            headers (Optional[Dict]): Additional request headers.
            timeout (Optional[Tuple[int, int]]): Custom (connect, read) timeout tuple.
            is_proxy (bool): Whether request targets scraper proxy.

        Returns:
            Dict[str, Any]: Parsed JSON response dictionary.

        Raises:
            ConnectionFailedError: On host unreachable or TCP failure.
            TimeoutError: On socket read or connect timeout.
            ApiHttpError: On HTTP 4xx or 5xx status codes.
        """
        try:
            return self._do_request(
                method=method, endpoint=endpoint, data=data, params=params,
                headers=headers, timeout=timeout, is_proxy=is_proxy,
            )
        except ConnectionFailedError as err:
            # _do_request translates raw socket failures into
            # ConnectionFailedError; retry idempotent verbs once on a fresh
            # connection (server closing a pooled keep-alive socket).
            if method.upper() in self.IDEMPOTENT_METHODS:
                logger.warning(
                    "[HTTP RETRY] %s %s after transient connection failure; retrying once",
                    method.upper(), endpoint,
                )
                return self._do_request(
                    method=method, endpoint=endpoint, data=data, params=params,
                    headers=headers, timeout=timeout, is_proxy=is_proxy,
                )
            raise

    def _do_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Union[Dict[str, Any], List[Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[Tuple[int, int]] = None,
        is_proxy: bool = False,
    ) -> Dict[str, Any]:
        if not self.config.base_url or not str(self.config.base_url).strip():
            logger.info("[OFFLINE MODE] Skipping network request to '%s' (no base_url configured)", endpoint)
            raise GolestoonNetworkError("حالت ابری غیرفعال است (آدرس سرور تنظیم نشده است).")

        url = f"{self.config.base_url}/{endpoint.lstrip('/')}"
        req_headers = dict(self._session.headers)
        if headers:
            req_headers.update(headers)

        self._apply_auth_header(req_headers)
        req_timeout = timeout or self.config.get_timeout_tuple(is_proxy=is_proxy)

        logger.info("[HTTP %s] -> %s", method.upper(), endpoint)

        try:
            json_data = json.dumps(data) if data is not None else None
            response = self._session.request(
                method=method.upper(),
                url=url,
                data=json_data,
                params=params,
                headers=req_headers,
                timeout=req_timeout,
                verify=self.config.ssl_verify,
            )
            logger.info("[HTTP %s] <- %s [%d]", method.upper(), endpoint, response.status_code)
            return self._handle_response(response)

        except requests.exceptions.Timeout as err:
            logger.warning("[HTTP TIMEOUT] %s: %s", endpoint, str(err))
            raise TimeoutError(f"Request timeout for endpoint '{endpoint}'", original_exception=err) from err

        except requests.exceptions.ConnectionError as err:
            logger.warning("[HTTP CONNECTION FAILED] %s: %s", endpoint, str(err))
            raise ConnectionFailedError(f"Failed to connect to host for '{endpoint}'", original_exception=err) from err

        except requests.exceptions.RequestException as err:
            logger.warning("[HTTP REQUEST ERROR] %s: %s", endpoint, str(err))
            raise GolestoonNetworkError(f"Network error executing request '{endpoint}'", original_exception=err) from err

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Process HTTP response status codes and parse JSON body.

        Args:
            response (requests.Response): Raw requests response object.

        Returns:
            Dict[str, Any]: Parsed JSON payload.
        """
        status_code = response.status_code

        # Attempt JSON parsing
        try:
            payload = response.json() if response.content else {}
        except Exception:
            payload = {"raw_text": response.text}

        if 200 <= status_code < 300:
            return payload if isinstance(payload, dict) else {"data": payload}

        # Error Handling by Status Code
        msg = payload.get("message") if isinstance(payload, dict) else response.reason or "HTTP Error"
        err_code = payload.get("code", "HTTP_ERROR") if isinstance(payload, dict) else "HTTP_ERROR"

        if status_code in (401, 403):
            raise AuthenticationError(message=msg, status_code=status_code, error_code=err_code)
        elif status_code == 400:
            raise ValidationApiError(message=msg, error_code=err_code)
        elif status_code == 404:
            raise NotFoundError(message=msg, error_code=err_code)
        elif status_code == 429:
            retry_after = payload.get("retry_after") if isinstance(payload, dict) else None
            raise RateLimitError(message=msg, retry_after=retry_after, error_code=err_code)
        elif status_code >= 500:
            raise ServerError(status_code=status_code, message=msg, error_code=err_code)
        else:
            raise ApiHttpError(status_code=status_code, message=msg, error_code=err_code)

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for HTTP GET."""
        return self.request(method="GET", endpoint=endpoint, params=params, **kwargs)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for HTTP POST."""
        return self.request(method="POST", endpoint=endpoint, data=data, **kwargs)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Convenience method for HTTP PUT."""
        return self.request(method="PUT", endpoint=endpoint, data=data, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for HTTP DELETE."""
        return self.request(method="DELETE", endpoint=endpoint, **kwargs)

    def close(self) -> None:
        """Close internal requests.Session and release connection pool sockets."""
        try:
            self._session.close()
            logger.debug("[NetworkSession] Session closed successfully.")
        except Exception as err:
            logger.warning("[NetworkSession] Error closing session: %s", type(err).__name__)

    def reset(self) -> None:
        """Reset internal session instance."""
        self.close()
        self._session = requests.Session()
        self._configure_session()


class SessionFactory:
    """Factory for instantiating configured NetworkSession instances."""

    @staticmethod
    def create_session(
        config: Optional[NetworkConfig] = None,
        token_manager: Optional[TokenManager] = None
    ) -> NetworkSession:
        """
        Create a new NetworkSession instance with injected dependencies.

        Args:
            config (Optional[NetworkConfig]): Custom network configuration.
            token_manager (Optional[TokenManager]): Custom token manager.

        Returns:
            NetworkSession: Configured session instance.
        """
        return NetworkSession(config=config, token_manager=token_manager)
