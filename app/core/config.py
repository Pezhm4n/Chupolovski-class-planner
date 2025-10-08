"""
Core configuration module for the Golestoon Class Planner application.

This module provides centralized configuration management including:
- Environment variable loading
- Application constants
- Logging setup
- Path management
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from PyQt5 import QtGui

# Global COURSES dictionary - will be loaded from JSON
COURSES = {}

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
def load_environment():
    """Load environment variables from .env file."""
    # Try to find .env file in several possible locations
    possible_paths = [
        Path(__file__).parent.parent / 'scrapers' / '.env',  # Current location
        Path(__file__).parent.parent / '.env',               # App root
        Path(__file__).parent / '.env',                      # Core directory
        Path('.env')                                         # Current working directory
    ]
    
    for path in possible_paths:
        if path.exists():
            load_dotenv(dotenv_path=path, override=True)
            break

# Load environment on import
load_environment()

# Get script directory for absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Environment variables with defaults
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
DATA_PATH = Path(os.getenv('DATA_PATH', Path(__file__).parent.parent / 'data'))

# API Keys and credentials
API_KEYS = {
    'golestan_username': os.getenv('USERNAME', ''),
    'golestan_password': os.getenv('PASSWORD', '')
}

# File paths
APP_DIR = Path(__file__).parent.parent
USER_DATA_FILE = APP_DIR / 'data' / 'user_data.json'
COURSES_DATA_FILE = APP_DIR / 'data' / 'courses_data.json'
STYLES_FILE = APP_DIR / 'ui' / 'styles.qss'

# روزها و اسلات‌ها
DAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه']

def generate_time_slots():
    """Generate time slots from 7:30 to 18:00 in 30-minute intervals."""
    time_slots = []
    start_minutes = 7 * 60 + 30
    end_minutes = 18 * 60
    m = start_minutes
    while m <= end_minutes:
        hh = m // 60
        mm = m % 60
        time_slots.append(f"{hh:02d}:{mm:02d}")
        m += 30
    return time_slots

TIME_SLOTS = generate_time_slots()

def generate_extended_time_slots():
    """Generate extended time slots from 7:00 to 19:00 in 30-minute intervals."""
    extended_time_slots = []
    start_minutes = 7 * 60
    end_minutes = 19 * 60
    m = start_minutes
    while m <= end_minutes:
        hh = m // 60
        mm = m % 60
        extended_time_slots.append(f"{hh:02d}:{mm:02d}")
        m += 30
    return extended_time_slots

EXTENDED_TIME_SLOTS = generate_extended_time_slots()

# رنگ‌ها
COLOR_MAP = [
    QtGui.QColor(219, 234, 254), QtGui.QColor(235, 233, 255), QtGui.QColor(237, 247, 237),
    QtGui.QColor(255, 249, 230), QtGui.QColor(255, 235, 238), QtGui.QColor(232, 234, 246)
]

# Logging configuration
def get_log_level():
    """Convert string log level to logging constant."""
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    return level_map.get(LOG_LEVEL.upper(), logging.INFO)

# ---------------------- QSS Style Loading ----------------------

def load_qss_styles():
    """Load QSS styles from external file with fallback"""
    try:
        if os.path.exists(STYLES_FILE):
            with open(STYLES_FILE, 'r', encoding='utf-8') as f:
                qss_content = f.read()
                # Import logger here to avoid circular imports
                from .logger import setup_logging
                logger = setup_logging()
                logger.info(f"Successfully loaded styles from {STYLES_FILE}")
                return qss_content
        else:
            # Import logger here to avoid circular imports
            from .logger import setup_logging
            logger = setup_logging()
            logger.warning(f"QSS file not found: {STYLES_FILE}")
    except Exception as e:
        # Import logger here to avoid circular imports
        from .logger import setup_logging
        logger = setup_logging()
        logger.error(f"Error loading QSS file: {e}")
    
    # Return empty string if no QSS file - app will use default styles
    # Import logger here to avoid circular imports
    from .logger import setup_logging
    logger = setup_logging()
    logger.info("Using default Qt styles")
    return ""