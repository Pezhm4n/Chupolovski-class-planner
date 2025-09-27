#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration module for Schedule Planner
Contains global constants, paths, and configuration functions
"""

import os
import logging
import sys
from PyQt5 import QtGui

# Get script directory for absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_FILE = os.path.join(SCRIPT_DIR, 'user_data.json')
COURSES_DATA_FILE = os.path.join(SCRIPT_DIR, 'courses_data.json')
STYLES_FILE = os.path.join(SCRIPT_DIR, 'styles.qss')

# Global COURSES dictionary - will be loaded from JSON
COURSES = {}

# OPTIONS برای چیدن خودکار (فقط دروس تخصصی)
OPTIONS = {
    'database': ['database_29', 'database_30'],
    'micro': ['micro_29', 'micro_31'],
    'software': ['software_29'],
    'micro_lab': ['micro_lab_30', 'micro_lab_31'],
    'ai': ['ai_29', 'ai_30'],
    'compiler': ['compiler_29', 'compiler_30']
}

# روزها و اسلات‌ها
DAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه']

def generate_time_slots():
    """Generate time slots from 7:30 to 18:00 in 30-minute intervals"""
    TIME_SLOTS = []
    start_minutes = 7 * 60 + 30
    end_minutes = 18 * 60
    m = start_minutes
    while m <= end_minutes:
        hh = m // 60
        mm = m % 60
        TIME_SLOTS.append(f"{hh:02d}:{mm:02d}")
        m += 30
    return TIME_SLOTS

TIME_SLOTS = generate_time_slots()

# Extended time slots for schedule table (7:00 to 19:00)
def generate_extended_time_slots():
    """Generate extended time slots from 7:00 to 19:00 in 30-minute intervals"""
    EXTENDED_TIME_SLOTS = []
    start_minutes = 7 * 60
    end_minutes = 19 * 60
    m = start_minutes
    while m <= end_minutes:
        hh = m // 60
        mm = m % 60
        EXTENDED_TIME_SLOTS.append(f"{hh:02d}:{mm:02d}")
        m += 30
    return EXTENDED_TIME_SLOTS

EXTENDED_TIME_SLOTS = generate_extended_time_slots()

# رنگ‌ها
COLOR_MAP = [
    QtGui.QColor(219, 234, 254), QtGui.QColor(235, 233, 255), QtGui.QColor(237, 247, 237),
    QtGui.QColor(255, 249, 230), QtGui.QColor(255, 235, 238), QtGui.QColor(232, 234, 246)
]

# ---------------------- Logging Setup ----------------------

def setup_logging():
    """Setup application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# Initialize logger
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