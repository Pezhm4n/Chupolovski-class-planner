# -*- coding: utf-8 -*-
"""
Golestoon Core Authentication Token Manager.

This module provides a thread-safe, secure abstraction for storing, retrieving,
and purging JWT access tokens on the host operating system. It utilizes OS Keyring
(Windows Credential Manager / DPAPI) with a secure memory-cache fallback.

Architecture Layer: Layer 2 (Security & Authentication Infrastructure)
Dependencies: Python Standard Library (`threading`, `logging`, `json`, `base64`), `keyring` (optional).
"""

import base64
import json
import logging
import threading
from typing import Optional

logger = logging.getLogger("golestoon.auth")

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False


class TokenManager:
    """
    Thread-safe JWT Token Manager handling storage, retrieval, and expiration checks.

    Attributes:
        service_name (str): Service name identifier for OS Keyring.
        username (str): Target key identifier for OS Keyring.
    """

    def __init__(
        self,
        service_name: str = "GolestoonDesktop",
        username: str = "JWT_ACCESS_TOKEN"
    ) -> None:
        self._service_name: str = service_name
        self._username: str = username
        self._lock: threading.Lock = threading.Lock()
        self._cached_token: Optional[str] = None

    def save_token(self, token: str) -> bool:
        """
        Securely save the JWT token to in-memory cache and OS Keyring.

        Args:
            token (str): JWT token string returned from server.

        Returns:
            bool: True if saved successfully.
        """
        if not token or not isinstance(token, str):
            logger.warning("[TokenManager] Invalid token string provided for storage.")
            return False

        with self._lock:
            self._cached_token = token
            if KEYRING_AVAILABLE and keyring is not None:
                try:
                    keyring.set_password(self._service_name, self._username, token)
                    logger.debug("[TokenManager] Token saved successfully to OS Keyring.")
                    return True
                except Exception as err:
                    logger.warning(
                        "[TokenManager] OS Keyring write failed: %s. Using memory fallback.",
                        type(err).__name__
                    )
            return True

    def get_token(self) -> Optional[str]:
        """
        Retrieve the current JWT token from memory cache or OS Keyring.

        Returns:
            Optional[str]: Active JWT token string, or None if not authenticated.
        """
        with self._lock:
            if self._cached_token:
                return self._cached_token

            if KEYRING_AVAILABLE and keyring is not None:
                try:
                    token = keyring.get_password(self._service_name, self._username)
                    if token:
                        self._cached_token = token
                        logger.debug("[TokenManager] Token loaded from OS Keyring.")
                        return token
                except Exception as err:
                    logger.warning(
                        "[TokenManager] OS Keyring read failed: %s.",
                        type(err).__name__
                    )
            return None

    def has_token(self) -> bool:
        """Check if a valid token exists."""
        return bool(self.get_token())

    def clear_token(self) -> bool:
        """
        Purge the active JWT token from memory cache and OS Keyring.

        Returns:
            bool: True if cleared successfully.
        """
        with self._lock:
            self._cached_token = None
            if KEYRING_AVAILABLE and keyring is not None:
                try:
                    keyring.delete_password(self._service_name, self._username)
                    logger.debug("[TokenManager] Token deleted from OS Keyring.")
                except Exception as err:
                    # Ignore keyring missing entry errors during deletion
                    logger.debug("[TokenManager] Keyring deletion note: %s", type(err).__name__)
            return True

    def has_valid_token(self) -> bool:
        """
        Check if a non-expired valid token is currently stored.

        Returns:
            bool: True if active token exists and is valid.
        """
        token = self.get_token()
        if not token:
            return False
        return not self.is_expired(token)

    @staticmethod
    def is_expired(token: str) -> bool:
        """
        Inspect JWT payload claims to check if token expiration (`exp`) has passed.

        Args:
            token (str): JWT token string.

        Returns:
            bool: True if token is expired or malformed, False if still valid.
        """
        if not token or not isinstance(token, str):
            return True

        parts = token.split(".")
        if len(parts) != 3:
            return True

        try:
            # Decode Base64URL payload (part 1)
            payload_b64 = parts[1]
            # Add padding if necessary
            reminder = len(payload_b64) % 4
            if reminder > 0:
                payload_b64 += "=" * (4 - reminder)

            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload_dict = json.loads(payload_bytes.decode("utf-8"))

            exp = payload_dict.get("exp")
            if exp is None:
                return False  # Token has no expiration claim

            import time
            current_time = time.time()
            return current_time >= float(exp)
        except Exception:
            # If payload parsing fails, treat token as unverified/expired
            return True
