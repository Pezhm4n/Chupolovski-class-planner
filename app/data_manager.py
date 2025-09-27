#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data management module for Schedule Planner
Handles loading and saving course data and user data
"""

import os
import json
import logging
import sys

# Add the app directory to the Python path to enable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import COURSES, USER_DATA_FILE, COURSES_DATA_FILE, logger

# ---------------------- Course Data Management ----------------------

def load_courses_from_json():
    """Load all courses from JSON file with enhanced error handling"""
    global COURSES
    logger.info(f"Loading courses from {COURSES_DATA_FILE}")
    
    if not os.path.exists(COURSES_DATA_FILE):
        logger.warning(f"{COURSES_DATA_FILE} not found. Creating empty course data.")
        print(f"Warning: {COURSES_DATA_FILE} not found. Creating empty course data.")
        COURSES = {}
        return
    
    try:
        with open(COURSES_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Validate JSON structure
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON structure: Root must be a dictionary")
            
        courses_data = data.get('courses', {})
        if not isinstance(courses_data, dict):
            raise ValueError("Invalid JSON structure: 'courses' must be a dictionary")
            
        # Validate each course entry
        valid_courses = {}
        invalid_count = 0
        
        for course_id, course_info in courses_data.items():
            try:
                # Check required fields
                required_fields = ['code', 'name', 'credits', 'instructor', 'schedule']
                for field in required_fields:
                    if field not in course_info:
                        raise ValueError(f"Missing required field '{field}'")
                        
                # Validate schedule structure
                if not isinstance(course_info['schedule'], list):
                    raise ValueError("Schedule must be a list")
                    
                for schedule_item in course_info['schedule']:
                    if not isinstance(schedule_item, dict):
                        raise ValueError("Schedule item must be a dictionary")
                    if 'day' not in schedule_item or 'start' not in schedule_item or 'end' not in schedule_item:
                        raise ValueError("Schedule item missing required fields")
                        
                valid_courses[course_id] = course_info
                logger.debug(f"Successfully validated course: {course_id}")
                
            except Exception as e:
                logger.warning(f"Invalid course data for {course_id}: {e}")
                invalid_count += 1
                continue
                
        # Update COURSES dictionary in place to maintain references
        COURSES.clear()
        COURSES.update(valid_courses)
        logger.info(f"Successfully loaded {len(COURSES)} valid courses from {COURSES_DATA_FILE}")
        if invalid_count > 0:
            logger.warning(f"Skipped {invalid_count} invalid course entries")
            print(f"Warning: Skipped {invalid_count} invalid course entries")
        print(f"Loaded {len(COURSES)} courses from {COURSES_DATA_FILE}")
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {COURSES_DATA_FILE}: {e}", exc_info=True)
        print(f"Error: Invalid JSON format in {COURSES_DATA_FILE}: {e}")
        COURSES = {}
    except (IOError, OSError) as e:
        logger.error(f"File I/O error loading {COURSES_DATA_FILE}: {e}", exc_info=True)
        print(f"Error: Cannot read {COURSES_DATA_FILE}: {e}")
        COURSES = {}
    except Exception as e:
        logger.error(f"Unexpected error loading courses from {COURSES_DATA_FILE}: {e}", exc_info=True)
        print(f"Error loading courses from {COURSES_DATA_FILE}: {e}")
        COURSES = {}

def save_courses_to_json():
    """Save all courses to JSON file"""
    try:
        # Load existing data first
        existing_data = {'courses': {}, 'custom_courses': [], 'saved_combos': []}
        if os.path.exists(COURSES_DATA_FILE):
            with open(COURSES_DATA_FILE, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        
        # Update courses section
        existing_data['courses'] = COURSES
        
        # Save back to file
        with open(COURSES_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"Error saving courses to {COURSES_DATA_FILE}: {e}")

# Load courses at module level
load_courses_from_json()

# ---------------------- User Data Management ----------------------

def load_user_data():
    """Load user data from JSON file with error handling"""
    data = {'custom_courses': [], 'saved_combos': []}
    if not os.path.exists(USER_DATA_FILE):
        return data
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            data.update(loaded_data)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load user data - {e}")
        return data
    
    # Load custom courses into COURSES dictionary
    try:
        for c in data.get('custom_courses', []):
            if isinstance(c, dict) and 'code' in c and 'name' in c:
                key = generate_unique_key(c.get('code', 'custom'), COURSES)
                COURSES[key] = c
    except Exception as e:
        print(f"Warning: Error loading custom courses - {e}")
    
    return data


def save_user_data(data):
    """Save user data to JSON file with error handling"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(USER_DATA_FILE)), exist_ok=True)
        
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except (IOError, OSError) as e:
        print(f'Error saving user data: {e}')
        raise


def generate_unique_key(base_code, store):
    """Generate a unique key for a course based on its code"""
    # base_code may contain invalid chars; make a safe key
    safe = base_code.replace(' ', '_')
    if safe not in store:
        return safe
    i = 1
    while f"{safe}_u{i}" in store:
        i += 1
    return f"{safe}_u{i}"