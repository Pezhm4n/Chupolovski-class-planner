#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual Course Utilities
Helper functions for handling odd/even week courses and dual course widgets
"""

from app.core.logger import setup_logging
from app.core.translator import translator

logger = setup_logging()


def check_odd_even_compatibility(session1, session2):
    """
    Check if two sessions are compatible (one odd, one even)
    Returns True if they can coexist in the same time slot
    
    Args:
        session1: First session dict with 'parity' key
        session2: Second session dict with 'parity' key
    
    Returns:
        bool: True if sessions are compatible (one odd, one even)
    """
    try:
        parity1 = session1.get('parity', '') or ''
        parity2 = session2.get('parity', '') or ''
        
        if not isinstance(parity1, str):
            parity1 = str(parity1)
        if not isinstance(parity2, str):
            parity2 = str(parity2)
        
        is_compatible = (
            (parity1 == 'ز' and parity2 == 'ف') or
            (parity1 == 'ف' and parity2 == 'ز')
        )
        
        return is_compatible
    except Exception as e:
        logger.warning(f"Error checking odd/even compatibility: {e}")
        return False


def translate_parity(parity_value):
    """
    Translate parity value to localized string
    
    Args:
        parity_value: Parity value ('ز' for even, 'ف' for odd)
    
    Returns:
        str: Translated parity string
    """
    if parity_value == 'ز':
        return translator.t("parity.even")
    if parity_value == 'ف':
        return translator.t("parity.odd")
    return ""


def schedules_overlap(schedule1, schedule2):
    """
    Check if two schedules have overlapping time slots
    
    Args:
        schedule1: First schedule list
        schedule2: Second schedule list
    
    Returns:
        bool: True if schedules have overlapping time slots
    """
    for sess1 in schedule1:
        for sess2 in schedule2:
            if (sess1.get('day') == sess2.get('day') and
                sess1.get('start') == sess2.get('start') and
                sess1.get('end') == sess2.get('end')):
                return True
    return False


def courses_are_compatible(odd_course, even_course, new_course):
    """
    Check if new course is compatible with existing dual courses
    
    Args:
        odd_course: Course dict for odd week
        even_course: Course dict for even week
        new_course: New course dict to check
    
    Returns:
        bool: True if new course is compatible with dual courses
    """
    if not all([odd_course, even_course, new_course]):
        return False
    
    # Check if new course shares time slot with existing dual
    new_schedule = new_course.get('schedule', [])
    odd_schedule = odd_course.get('schedule', [])
    
    return schedules_overlap(odd_schedule, new_schedule)

