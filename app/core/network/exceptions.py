# -*- coding: utf-8 -*-
"""
Golestoon Core Network Exceptions.

This module defines the strongly-typed, immutable exception hierarchy
for all network, transport, HTTP, and API proxy operations in Golestoon Desktop.

Architecture Layer: Layer 1 (Network Leaf Infrastructure)
Dependencies: Python Standard Library ONLY.
"""

from typing import Dict, Any, Optional


class GolestoonNetworkError(Exception):
    """
    Base immutable exception for all Golestoon network and transport errors.

    Attributes:
        message (str): Human-readable error description.
        original_exception (Optional[Exception]): Underlying caught exception if any.
    """

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None
    ) -> None:
        super().__init__(message)
        self._message: str = message
        self._original_exception: Optional[Exception] = original_exception

    @property
    def message(self) -> str:
        """Get the error message."""
        return self._message

    @property
    def original_exception(self) -> Optional[Exception]:
        """Get the underlying original exception if available."""
        return self._original_exception

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize exception to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing error classification and message.
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self._message,
            "original_exception": (
                str(self._original_exception) if self._original_exception else None
            ),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self._message!r})"

    def __str__(self) -> str:
        return self._message


class ConnectionFailedError(GolestoonNetworkError):
    """Raised when host is unreachable or TCP connection fails."""

    pass


class TimeoutError(GolestoonNetworkError):
    """Raised when request times out during connection or socket read."""

    pass


class OfflineError(GolestoonNetworkError):
    """Raised when application is operating in offline mode or network interface is down."""

    pass


class GolestanProxyError(GolestoonNetworkError):
    """Raised when remote Golestan scraper proxy or captcha solver fails."""

    pass


class ApiHttpError(GolestoonNetworkError):
    """
    Base Exception for HTTP status code responses (4xx / 5xx).

    Attributes:
        status_code (int): HTTP response status code (e.g. 401, 404, 500).
        message (str): Error message string returned by server or client.
        error_code (str): Machine-readable server error code (e.g. 'INVALID_CREDENTIALS').
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str = "HTTP_ERROR",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(message=message, original_exception=original_exception)
        self._status_code: int = status_code
        self._error_code: str = error_code

    @property
    def status_code(self) -> int:
        """Get the HTTP status code."""
        return self._status_code

    @property
    def error_code(self) -> str:
        """Get the machine-readable error code."""
        return self._error_code

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize HTTP exception to dictionary representation.

        Returns:
            Dict[str, Any]: Serialized dictionary representation.
        """
        data = super().to_dict()
        data["status_code"] = self._status_code
        data["error_code"] = self._error_code
        return data

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self._status_code}, "
            f"error_code={self._error_code!r}, "
            f"message={self._message!r})"
        )


class ValidationApiError(ApiHttpError):
    """Raised when server returns HTTP 400 Bad Request / Schema Validation failure."""

    def __init__(
        self,
        message: str,
        error_code: str = "VALIDATION_ERROR",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            status_code=400,
            message=message,
            error_code=error_code,
            original_exception=original_exception,
        )


class AuthenticationError(ApiHttpError):
    """Raised when server returns HTTP 401 Unauthorized or HTTP 403 Forbidden."""

    def __init__(
        self,
        message: str,
        status_code: int = 401,
        error_code: str = "UNAUTHORIZED",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            message=message,
            error_code=error_code,
            original_exception=original_exception,
        )


class NotFoundError(ApiHttpError):
    """Raised when requested resource is not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        error_code: str = "NOT_FOUND",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            status_code=404,
            message=message,
            error_code=error_code,
            original_exception=original_exception,
        )


class RateLimitError(ApiHttpError):
    """Raised when client exceeds API rate limits (HTTP 429)."""

    def __init__(
        self,
        message: str = "Too many requests. Please try again later.",
        retry_after: Optional[int] = None,
        error_code: str = "RATE_LIMIT_EXCEEDED",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            status_code=429,
            message=message,
            error_code=error_code,
            original_exception=original_exception,
        )
        self._retry_after: Optional[int] = retry_after

    @property
    def retry_after(self) -> Optional[int]:
        """Get the recommended retry delay in seconds."""
        return self._retry_after


class ServerError(ApiHttpError):
    """Raised when backend server encounters an internal error (HTTP 500 / 502 / 503 / 504)."""

    def __init__(
        self,
        status_code: int = 500,
        message: str = "Internal server error",
        error_code: str = "SERVER_ERROR",
        original_exception: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            message=message,
            error_code=error_code,
            original_exception=original_exception,
        )
