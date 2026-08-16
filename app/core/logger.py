"""
Centralized logging configuration for the Golestoon Class Planner application.

This module provides a unified logging setup for the entire application,
ensuring consistent log formatting, rotation, and sensitive data masking across all modules.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

class SensitiveDataFilter(logging.Filter):
    """
    Security filter that masks sensitive tokens, passwords, and student credentials
    from all log records before writing to disk or console.
    """
    MASK_RULES = [
        (re.compile(r'("password"|"pass"|password|pass)\s*[:=]\s*["\']?([^"\'\s,]+)["\']?', re.IGNORECASE), r'\1=***REDACTED***'),
        (re.compile(r'(Bearer\s+)[A-Za-z0-9\-\._~\+\/]{15,}=*', re.IGNORECASE), r'\1***TOKEN_REDACTED***'),
        (re.compile(r'("student_number"|student_number)\s*[:=]\s*["\']?(\d{3})\d+(["\']?)', re.IGNORECASE), r'\1=\2***\3'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern, repl in self.MASK_RULES:
                msg = pattern.sub(repl, msg)
            record.msg = msg
        return True


def setup_logging():
    """Set up logging configuration for the Golestoon Class Planner application"""
    logger = logging.getLogger('golestoon')
    logger.setLevel(get_log_level())
    
    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create rotating file handler (5MB max, 3 backup files)
    log_path = Path(__file__).parent.parent / 'app.log'
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(get_log_level())
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SensitiveDataFilter())
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(get_log_level())
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_log_level():
    """Determine the log level based on the environment variable"""
    log_level = os.getenv('GOLESTOON_LOG_LEVEL', 'INFO').upper()
    return getattr(logging, log_level, logging.INFO)