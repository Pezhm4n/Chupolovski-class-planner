#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import json
from pathlib import Path
from dotenv import load_dotenv
from PyQt5 import QtGui

# Global COURSES dictionary - will be loaded from JSON
COURSES = {}

# Base directory for the application
BASE_DIR = Path(__file__).parent.parent

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
USER_ADDED_COURSES_FILE = APP_DIR / 'data' / 'user_added_courses.json'
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

# Import logger here to avoid circular imports
from .logger import setup_logging
logger = setup_logging()

# ---------------------- QSS Style Loading ----------------------

def load_qss_styles():
    """Load QSS styles from external file with fallback"""
    try:
        if os.path.exists(STYLES_FILE):
            with open(STYLES_FILE, 'r', encoding='utf-8') as f:
                qss_content = f.read()
                logger.info(f"Successfully loaded styles from {STYLES_FILE}")
                return qss_content
        else:
            logger.warning(f"QSS file not found: {STYLES_FILE}")
    except Exception as e:
        logger.error(f"Error loading QSS file: {e}")
    
    # Return empty string if no QSS file - app will use default styles
    logger.info("Using default Qt styles")
    return ""

# ---------------------- Courses Loading ----------------------

def load_courses_from_json():
    """Load courses from JSON file"""
    global COURSES
    logger.info("Loading courses from JSON file...")
    try:
        with open(COURSES_DATA_FILE, 'r', encoding='utf-8') as f:
            golestan_courses = json.load(f)
            COURSES.clear()
            COURSES.update(golestan_courses)
            logger.info(f"Successfully loaded {len(COURSES)} courses from JSON file")
            print(f"Loaded {len(COURSES)} courses from JSON file")
    except Exception as e:
        logger.error(f"Error loading courses from JSON file: {e}")
        print(f"Error loading courses from JSON file: {e}")

def load_user_added_courses():
    """Load user-added courses from dedicated JSON file"""
    global COURSES
    try:
        if USER_ADDED_COURSES_FILE.exists():
            with open(USER_ADDED_COURSES_FILE, 'r', encoding='utf-8') as f:
                user_added_data = json.load(f)
                user_courses = user_added_data.get('courses', [])
                
                # Add user-added courses to COURSES dictionary
                for course in user_courses:
                    # Ensure the course has a proper key
                    course_key = course.get('code', f"user_{len(COURSES)}")
                    course['key'] = course_key
                    course['major'] = 'دروس اضافه‌شده توسط کاربر'  # Set the correct major category
                    COURSES[course_key] = course
                    
                logger.info(f"Successfully loaded {len(user_courses)} user-added courses")
                print(f"Loaded {len(user_courses)} user-added courses")
        else:
            # Create the file with empty structure if it doesn't exist
            with open(USER_ADDED_COURSES_FILE, 'w', encoding='utf-8') as f:
                json.dump({"courses": []}, f, ensure_ascii=False, indent=2)
            logger.info("Created empty user_added_courses.json file")
    except Exception as e:
        logger.error(f"Error loading user-added courses: {e}")
        print(f"Error loading user-added courses: {e}")

# Load courses at module level
# Try to load from Golestan data first if files exist, fallback to JSON
try:
    if golestan_data_files_exist():
        load_courses_from_golestan_data()
        load_user_added_courses()  # Load user-added courses after Golestan courses
    else:
        load_courses_from_json()
        load_user_added_courses()  # Load user-added courses after main courses
except Exception as e:
    logger.info("Failed to load from Golestan data, falling back to JSON")
    load_courses_from_json()
    load_user_added_courses()  # Load user-added courses after main courses