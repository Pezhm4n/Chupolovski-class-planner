"""
Centralized logging configuration for the Chupolovski Class Planner application.

This module provides a consistent logging setup with rotating file handlers
and configurable log levels.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_level=logging.INFO, log_file='app.log'):
    """
    Set up application logging with rotating file handler.
    
    Args:
        log_level: The logging level (default: INFO)
        log_file: The log file name (default: app.log)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('chupolovski')
    logger.setLevel(log_level)
    
    # Prevent adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create rotating file handler (10MB max, 5 backup files)
    log_path = Path(__file__).parent.parent / log_file
    file_handler = RotatingFileHandler(
        log_path, 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger