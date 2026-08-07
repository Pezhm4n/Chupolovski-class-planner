# -*- coding: utf-8 -*-
"""
Golestoon Central Network Configuration.

This module defines the immutable NetworkConfig dataclass managing base API URLs,
connection timeouts, connection pool sizes, user agent strings, and default HTTP headers.

Architecture Layer: Layer 1 (Network Infrastructure Configuration)
Dependencies: Python Standard Library ONLY (`os`, `dataclasses`, `typing`).
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Tuple

DEFAULT_PRODUCTION_BASE_URL: str = "https://api.example.com"


@dataclass(frozen=True)
class NetworkConfig:
    """
    Immutable Central Network Configuration.

    Attributes:
        base_url (str): Target REST API Base URL.
        connect_timeout (int): Socket connection timeout in seconds.
        read_timeout (int): Standard HTTP response read timeout in seconds.
        proxy_read_timeout (int): Extended timeout for scraper proxy requests in seconds.
        max_retries (int): Maximum connection retry attempts.
        pool_connections (int): Number of urllib3 connection pools to cache.
        pool_maxsize (int): Maximum number of connections to save in the pool.
        user_agent (str): Client User-Agent header value.
        ssl_verify (bool): Whether to enforce HTTPS SSL certificate verification.
    """

    base_url: str = field(
        default_factory=lambda: os.environ.get(
            "GOLESTOON_API_BASE_URL", DEFAULT_PRODUCTION_BASE_URL
        ).rstrip("/")
    )
    connect_timeout: int = 5
    read_timeout: int = 15
    proxy_read_timeout: int = 35
    max_retries: int = 3
    pool_connections: int = 5
    pool_maxsize: int = 10
    user_agent: str = "GolestoonDesktopClient/4.0.0 (Windows NT 10.0; Win64; x64)"
    ssl_verify: bool = True

    def get_default_headers(self) -> Dict[str, str]:
        """
        Construct default HTTP headers dictionary.

        Returns:
            Dict[str, str]: Map of default request headers.
        """
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_timeout_tuple(self, is_proxy: bool = False) -> Tuple[int, int]:
        """
        Get (connect_timeout, read_timeout) tuple for requests calls.

        Args:
            is_proxy (bool): Whether request targets extended scraper proxy.

        Returns:
            Tuple[int, int]: (connect_timeout, read_timeout) in seconds.
        """
        read_to = self.proxy_read_timeout if is_proxy else self.read_timeout
        return (self.connect_timeout, read_to)
