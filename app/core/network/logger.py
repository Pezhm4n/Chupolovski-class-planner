# -*- coding: utf-8 -*-
"""
Golestoon Network Logger and Credential Sanitizer.

This module provides a specialized logging interface equipped with a redacting filter
that automatically obfuscates sensitive information (JWT tokens, passwords, authorization headers)
from log outputs.

Architecture Layer: Layer 1 (Network Leaf Infrastructure / Utility)
Dependencies: Python Standard Library ONLY (`logging`, `re`, `os`, `typing`).
"""

import logging
import re
from typing import List, Optional, Pattern


class SensitiveDataRedactor(logging.Filter):
    """
    Logging filter that sanitizes passwords, JWT tokens, and sensitive headers from log records.
    """

    DEFAULT_PATTERNS: List[str] = [
        r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*",  # Bearer JWT Tokens
        r"(?i)(password['\"]?\s*[:=]\s*['\"]?)[^\s'\",&]+",  # JSON / Form Password
        r"(?i)(x-password['\"]?\s*[:=]\s*['\"]?)[^\s'\",&]+",  # Golestan Header Password
        r"(?i)(token['\"]?\s*[:=]\s*['\"]?)[^\s'\",&]+",  # Generic API Tokens
        r"(?i)(Authorization['\"]?\s*[:=]\s*['\"]?)[^\s'\",&]+",  # Auth Headers
    ]

    def __init__(self, name: str = "", extra_patterns: Optional[List[str]] = None) -> None:
        super().__init__(name=name)
        patterns = self.DEFAULT_PATTERNS + (extra_patterns or [])
        self._regexes: List[Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in patterns
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Intercept and redact sensitive strings in the log record message.

        Args:
            record (logging.LogRecord): The log record to sanitize.

        Returns:
            bool: Always True (allows the log record to pass after redaction).
        """
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (self._redact(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    (self._redact(arg) if isinstance(arg, str) else arg)
                    for arg in record.args
                )
        return True

    def _redact(self, text: str) -> str:
        """Redact matched patterns in text string."""
        for regex in self._regexes:
            text = regex.sub(r"\1[REDACTED]", text)
        return text


def get_network_logger(name: str = "golestoon.network") -> logging.Logger:
    """
    Get or create a network logger instance configured with redacting filters.

    Args:
        name (str): Logger channel name. Defaults to 'golestoon.network'.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if already initialized
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)

        # Attach redactor filter
        redactor = SensitiveDataRedactor()
        console_handler.addFilter(redactor)
        logger.addFilter(redactor)

        logger.addHandler(console_handler)

    return logger
