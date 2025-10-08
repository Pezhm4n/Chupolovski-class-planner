"""
Centralized logging configuration for the Golestoon Class Planner application.

This module provides a unified logging setup for the entire application,
ensuring consistent log formatting and output across all modules.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Set up logging configuration for the Golestoon Class Planner application"""
    # Create logger with 'golestoon' name instead of 'Golestoon'
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
    
    # Create rotating file handler (10MB max, 5 backup files)
    log_path = Path(__file__).parent.parent / 'app.log'
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(get_log_level())
    file_handler.setFormatter(formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(get_log_level())
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_log_level():
    """Determine the log level based on the environment variable"""
    log_level = os.getenv('GOLESTOON_LOG_LEVEL', 'INFO').upper()
    return getattr(logging, log_level, logging.INFO)