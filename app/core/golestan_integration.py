# -*- coding: utf-8 -*-
"""
Golestan Integration Module for Golestoon Class Planner

This module handles the integration with the Golestan university system,
including authentication, data fetching, and parsing.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any

# Import from core modules
from .config import COURSES
from .logger import setup_logging

logger = setup_logging()

from ..scrapers.requests_scraper.fetch_data import get_courses

# Global variable to store major information for courses
COURSE_MAJORS = {}

# ---------------------- Golestan Integration Functions ----------------------

def fetch_golestan_courses(status='both', username=None, password=None):
    """
    Fetch courses from Golestan system and convert to internal format
    
    Args:
        status: 'available', 'unavailable', or 'both'
        username: Golestan login username
        password: Golestan login password
        
    Returns:
        dict: Courses in internal format
    """
    try:
        logger.info("Fetching courses from Golestan system...")
        
        # Fetch data from Golestan
        get_courses(status=status, username=username, password=password)
        
        # Load the fetched data
        courses = load_golestan_data()
        
        logger.info(f"Successfully fetched and processed {len(courses)} courses from Golestan")
        return courses
        
    except Exception as e:
        logger.error(f"Error fetching courses from Golestan: {e}")
        raise

def load_golestan_data() -> Dict[str, Any]:
    """
    Load and process course data from Golestan scraper output files
    
    Returns:
        dict: Courses in internal format
    """
    try:
        # Get the app directory
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        courses_data_dir = os.path.join(app_dir, 'data', 'courses_data')
        
        # Load available courses
        available_courses_file = os.path.join(courses_data_dir, 'available_courses.json')
        unavailable_courses_file = os.path.join(courses_data_dir, 'unavailable_courses.json')
        
        all_courses = {}
        global COURSE_MAJORS
        COURSE_MAJORS = {}
        
        available_count = 0
        unavailable_count = 0
        
        # Process available courses
        if os.path.exists(available_courses_file):
            with open(available_courses_file, 'r', encoding='utf-8') as f:
                available_data = json.load(f)
            # Count available courses before processing
            for faculty_name, departments in available_data.items():
                for department_name, courses in departments.items():
                    available_count += len(courses)
            process_golestan_faculty_data(available_data, all_courses, COURSE_MAJORS, is_available=True)
        
        # Process unavailable courses
        if os.path.exists(unavailable_courses_file):
            with open(unavailable_courses_file, 'r', encoding='utf-8') as f:
                unavailable_data = json.load(f)
            # Count unavailable courses before processing
            for faculty_name, departments in unavailable_data.items():
                for department_name, courses in departments.items():
                    unavailable_count += len(courses)
            process_golestan_faculty_data(unavailable_data, all_courses, COURSE_MAJORS, is_available=False)
        
        # Normalize day names in all loaded courses
        for course in all_courses.values():
            if 'schedule' in course:
                for session in course['schedule']:
                    if 'day' in session:
                        # Import normalize_day_name from xml_parser
                        from ..scrapers.requests_scraper.parsers import normalize_day_name
                        session['day'] = normalize_day_name(session['day'])
        
        logger.info(f"Loaded {len(all_courses)} total courses ({available_count} available + {unavailable_count} unavailable)")
        print(f"Loaded {len(all_courses)} total courses ({available_count} available + {unavailable_count} unavailable)")
        return all_courses
        
    except Exception as e:
        logger.error(f"Error loading Golestan data: {e}")
        raise

def process_golestan_faculty_data(faculty_data: Dict, all_courses: Dict, course_majors: Dict, is_available: bool):
    """
    Process faculty data from Golestan and convert to internal format
    
    Args:
        faculty_data: Data from Golestan scraper
        all_courses: Dictionary to store processed courses
        course_majors: Dictionary to store course major information
        is_available: Whether these are available courses
    """
    try:
        for faculty_name, departments in faculty_data.items():
            faculty_name_clean = faculty_name.strip()
            for department_name, courses in departments.items():
                department_name_clean = department_name.strip()
                # Create major identifier from faculty and department
                major_identifier = f"{faculty_name_clean} - {department_name_clean}"
                
                for course in courses:
                    # Generate a unique key for the course
                    course_key = generate_course_key(course)
                    
                    # Convert Golestan format to internal format
                    converted_course = convert_golestan_course_format(course, is_available)
                    
                    # Add to all courses
                    all_courses[course_key] = converted_course
                    
                    # Store major information for this course
                    course_majors[course_key] = major_identifier
                    
    except Exception as e:
        logger.error(f"Error processing faculty data: {e}")
        raise

def generate_course_key(course: Dict) -> str:
    """
    Generate a unique key for a course based on its code and other identifiers
    
    Args:
        course: Course data from Golestan
        
    Returns:
        str: Unique course key
    """
    code = course.get('code', '')
    # Create a safe key by replacing problematic characters
    safe_code = code.replace(' ', '_').replace('-', '_').replace('.', '_')
    
    # If the code is empty or already exists, generate a unique key
    if not safe_code or safe_code in COURSES:
        # Use name and instructor as fallback
        name = course.get('name', 'unknown')
        instructor = course.get('instructor', 'unknown')
        safe_code = f"{name}_{instructor}".replace(' ', '_').replace('-', '_').replace('.', '_')
    
    # Ensure uniqueness
    base_key = safe_code
    counter = 1
    while base_key in COURSES:
        base_key = f"{safe_code}_{counter}"
        counter += 1
    
    return base_key

def convert_golestan_course_format(course: Dict, is_available: bool) -> Dict:
    """
    Convert course data from Golestan format to internal format
    
    Args:
        course: Course data from Golestan
        is_available: Whether this course is available
        
    Returns:
        dict: Course in internal format
    """
    try:
        # Extract basic information
        # Extract location from first schedule session if exists
        schedule = course.get('schedule', [])
        course_location = course.get('location', '')  # Try course-level first
        
        if not course_location and schedule:
            # Fallback to first session's location
            course_location = schedule[0].get('location', '')
        
        converted = {
            'code': course.get('code', ''),
            'name': course.get('name', ''),
            'credits': int(course.get('credits', 0)),
            'instructor': course.get('instructor', 'اساتيد گروه آموزشي'),
            'schedule': schedule,
            'location': course_location,  # ← Now properly populated from schedule
            'description': course.get('description', ''),
            'exam_time': course.get('exam_time', ''),
            # New fields from Golestan scraper
            'capacity': course.get('capacity', ''),
            'gender_restriction': course.get('gender', ''),
            'enrollment_conditions': course.get('enrollment_conditions', ''),
            'is_available': is_available
        }
        
        # Clean up instructor name
        converted['instructor'] = converted['instructor'].replace('<BR>', '').strip()
        
        # Clean up description
        converted['description'] = converted['description'].replace('<BR>', '')
        
        return converted
        
    except Exception as e:
        logger.error(f"Error converting course format: {e}")
        # Return a basic conversion if there's an error
        return {
            'code': course.get('code', ''),
            'name': course.get('name', ''),
            'credits': 0,
            'instructor': 'اساتيد گروه آموزشي',
            'schedule': [],
            'location': '',
            'description': '',
            'exam_time': '',
            'capacity': '',
            'gender_restriction': '',
            'enrollment_conditions': '',
            'is_available': is_available
        }

def update_courses_from_golestan(username=None, password=None):
    """
    Fetch latest courses from Golestan and update the application's course data
    
    Args:
        username: Golestan login username
        password: Golestan login password
    """
    try:
        logger.info("Updating courses from Golestan...")
        
        # Fetch courses from Golestan
        golestan_courses = fetch_golestan_courses(username=username, password=password)
        
        # Update the global COURSES dictionary
        COURSES.clear()
        COURSES.update(golestan_courses)
        
        # NOTE: No longer saving to courses_data.json - data is saved in Golestan files
        logger.info(f"Successfully updated {len(golestan_courses)} courses from Golestan")
        
    except Exception as e:
        logger.error(f"Error updating courses from Golestan: {e}")
        raise

def get_course_major(course_key: str) -> str:
    """
    Get the major for a course by its key
    
    Args:
        course_key: The key of the course
        
    Returns:
        str: The major identifier for the course
    """
    global COURSE_MAJORS
    return COURSE_MAJORS.get(course_key, "رشته نامشخص")

# Example usage
if __name__ == "__main__":
    # This is just for testing purposes
    try:
        courses = load_golestan_data()
        print(f"Loaded {len(courses)} courses from Golestan data")
    except Exception as e:
        print(f"Error: {e}")