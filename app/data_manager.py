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

# Add new function to load courses from Golestan data
def load_courses_from_golestan_data():
    """Load courses from Golestan scraper data files"""
    global COURSES
    try:
        from golestan_integration import load_golestan_data
        logger.info("Loading courses from Golestan data files...")
        
        # Load courses from Golestan data
        golestan_courses = load_golestan_data()
        
        # Update COURSES dictionary
        COURSES.clear()
        COURSES.update(golestan_courses)
        
        logger.info(f"Successfully loaded {len(COURSES)} courses from Golestan data")
        print(f"Loaded {len(COURSES)} courses from Golestan data")
        
    except Exception as e:
        logger.error(f"Error loading courses from Golestan data: {e}")
        print(f"Error loading courses from Golestan data: {e}")

# Add new function to check if Golestan data files exist
def golestan_data_files_exist():
    """Check if Golestan data files exist in the courses_data directory"""
    try:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        courses_data_dir = os.path.join(app_dir, 'courses_data')
        
        available_courses_file = os.path.join(courses_data_dir, 'available_courses.json')
        unavailable_courses_file = os.path.join(courses_data_dir, 'unavailable_courses.json')
        
        return os.path.exists(available_courses_file) or os.path.exists(unavailable_courses_file)
    except Exception as e:
        logger.error(f"Error checking Golestan data files: {e}")
        return False

# Load courses at module level
# Try to load from Golestan data first if files exist, fallback to JSON
try:
    if golestan_data_files_exist():
        load_courses_from_golestan_data()
    else:
        load_courses_from_json()
except Exception as e:
    logger.info("Failed to load from Golestan data, falling back to JSON")
    load_courses_from_json()

def load_user_data():
    """Load user data from JSON file"""
    if not os.path.exists(USER_DATA_FILE):
        # Return default user data structure
        return {
            'custom_courses': [],
            'saved_combos': [],
            'current_schedule': []
        }
    
    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Ensure required keys exist
        required_keys = ['custom_courses', 'saved_combos', 'current_schedule']
        for key in required_keys:
            if key not in data:
                data[key] = []
                
        return data
    except Exception as e:
        logger.error(f"Error loading user data from {USER_DATA_FILE}: {e}")
        # Return default structure on error
        return {
            'custom_courses': [],
            'saved_combos': [],
            'current_schedule': []
        }

def save_user_data(user_data):
    """Save user data to JSON file"""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving user data to {USER_DATA_FILE}: {e}")

def generate_unique_key(base_key, existing_keys):
    """Generate a unique key by appending a number if needed"""
    if base_key not in existing_keys:
        return base_key
    
    counter = 1
    new_key = f"{base_key}_{counter}"
    while new_key in existing_keys:
        counter += 1
        new_key = f"{base_key}_{counter}"
    
    return new_key
