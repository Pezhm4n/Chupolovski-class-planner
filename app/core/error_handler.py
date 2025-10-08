"""
Global error handler for the Golestoon Class Planner application.

This module provides centralized error handling and logging functionality
for the entire application.
"""

import sys
import logging
import traceback
from typing import Callable, Any

# Import logger
try:
    from .logger import setup_logging
    logger = setup_logging()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Global exception handler that logs unhandled exceptions.
    
    Args:
        exc_type: Exception type
        exc_value: Exception value
        exc_traceback: Exception traceback
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_traceback)
    )

def setup_global_exception_handler():
    """Set up the global exception handler."""
    sys.excepthook = handle_exception
    logger.info("Global exception handler installed")

def safe_execute(func: Callable, *args, **kwargs) -> Any:
    """
    Execute a function safely with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Any: Function result or None if exception occurred
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing {func.__name__}: {e}")
        logger.error(traceback.format_exc())
        return None

# Set up global exception handler on import
setup_global_exception_handler()