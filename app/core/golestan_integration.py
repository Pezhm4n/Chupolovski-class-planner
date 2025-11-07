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

from .config import COURSES, get_golestan_credentials
from .logger import setup_logging

logger = setup_logging()

from ..scrapers.requests_scraper.fetch_data import get_courses

COURSE_MAJORS = {}

def fetch_golestan_courses(status='both', username=None, password=None):
    """
    Fetch courses from Golestan system and convert to internal format
    
    Args:
        status: 'available', 'unavailable', or 'both'
        username: Golestan login username (required)
        password: Golestan login password (required)
        
    Returns:
        dict: Courses in internal format
    """
    try:
        logger.info("Fetching courses from Golestan system...")
        
        if username is None or password is None or username.strip() == "" or password.strip() == "":
            raise ValueError("Username and password are required to fetch from Golestan")
        
        from app.data.courses_db import CourseDatabase
        db = CourseDatabase()
        
        get_courses(status=status, username=username, password=password, db=db)
        
        courses = load_courses_from_database(db)
        
        if not courses or len(courses) == 0:
            raise RuntimeError("No courses were fetched from Golestan. Please check your credentials and try again.")
        
        logger.info(f"Successfully fetched and processed {len(courses)} courses from Golestan")
        return courses
        
    except Exception as e:
        logger.error(f"Error fetching courses from Golestan: {e}")
        raise

def load_courses_from_database(db):
    """
    Load courses from the database and convert to the format expected by the UI
    
    Args:
        db: CourseDatabase instance
        
    Returns:
        dict: Courses in internal format compatible with COURSES structure
    """
    try:
        logger.info("Loading courses from database...")
        
        db_courses = db.get_all_courses(return_hierarchy=True)
        
        all_courses = {}
        global COURSE_MAJORS
        COURSE_MAJORS = {}
        
        course_count = 0
        
        for faculty_name, departments in db_courses.items():
            for department_name, courses in departments.items():
                major_identifier = f"{faculty_name} - {department_name}"
                
                for course in courses:
                    course_key = generate_course_key_from_db(course)
                    converted_course = convert_db_course_format(course)
                    converted_course['major'] = major_identifier
                    all_courses[course_key] = converted_course
                    COURSE_MAJORS[course_key] = major_identifier
                    course_count += 1
        
        logger.info(f"Successfully loaded {course_count} courses from database")
        return all_courses
        
    except Exception as e:
        logger.error(f"Error loading courses from database: {e}")
        raise

def load_golestan_data() -> Dict[str, Any]:
    """
    Load and process course data from Golestan scraper output files
    
    Returns:
        dict: Courses in internal format
    """
    try:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        courses_data_dir = os.path.join(app_dir, 'data', 'courses_data')
        
        available_courses_file = os.path.join(courses_data_dir, 'available_courses.json')
        unavailable_courses_file = os.path.join(courses_data_dir, 'unavailable_courses.json')
        
        all_courses = {}
        global COURSE_MAJORS
        COURSE_MAJORS = {}
        
        available_count = 0
        unavailable_count = 0
        
        if os.path.exists(available_courses_file):
            with open(available_courses_file, 'r', encoding='utf-8') as f:
                available_data = json.load(f)
            for faculty_name, departments in available_data.items():
                for department_name, courses in departments.items():
                    available_count += len(courses)
            process_golestan_faculty_data(available_data, all_courses, COURSE_MAJORS, is_available=True)
        
        if os.path.exists(unavailable_courses_file):
            with open(unavailable_courses_file, 'r', encoding='utf-8') as f:
                unavailable_data = json.load(f)
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
        if os.environ.get('DEBUG'):
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
                major_identifier = f"{faculty_name_clean} - {department_name_clean}"
                
                for course in courses:
                    course_key = generate_course_key(course)
                    converted_course = convert_golestan_course_format(course, is_available)
                    all_courses[course_key] = converted_course
                    course_majors[course_key] = major_identifier
                    
    except Exception as e:
        logger.error(f"Error processing faculty data: {e}")
        raise

def generate_course_key_from_db(course: Dict) -> str:
    """
    Generate a unique key for a course based on its code from database
    
    Args:
        course: Course data from database
        
    Returns:
        str: Unique course key
    """
    code = course.get('code', '')
    safe_code = code.replace(' ', '_').replace('-', '_').replace('.', '_')
    
    if not safe_code:
        name = course.get('name', 'unknown')
        instructor = course.get('instructor', 'unknown')
        safe_code = f"{name}_{instructor}".replace(' ', '_').replace('-', '_').replace('.', '_')
    
    base_key = safe_code
    counter = 1
    while base_key in COURSES:
        base_key = f"{safe_code}_{counter}"
        counter += 1
    
    return base_key

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

def convert_db_course_format(course: Dict) -> Dict:
    """
    Convert course data from database format to internal format
    
    Args:
        course: Course data from database
        
    Returns:
        dict: Course in internal format
    """
    try:
        # Extract location from first schedule session if exists
        schedule = course.get('schedule', [])
        course_location = ''
        
        if schedule:
            for session in schedule:
                if session.get('location'):
                    course_location = session['location']
                    break
        
        converted = {
            'code': course.get('code', ''),
            'name': course.get('name', ''),
            'credits': int(course.get('credits', 0)),
            'instructor': course.get('instructor', 'اساتيد گروه آموزشي'),
            'schedule': schedule,
            'location': course_location,
            'description': '',
            'exam_time': course.get('exam_time', ''),
            'capacity': course.get('capacity', ''),
            'gender_restriction': course.get('gender', ''),
            'enrollment_conditions': course.get('enrollment_conditions', ''),
            'is_available': course.get('is_available', True)
        }
        
        converted['instructor'] = converted['instructor'].replace('<BR>', '').strip()
        
        return converted
        
    except Exception as e:
        logger.error(f"Error converting database course format: {e}")
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
            'is_available': True
        }

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
        schedule = course.get('schedule', [])
        course_location = course.get('location', '')
        
        if not course_location and schedule:
            course_location = schedule[0].get('location', '')
        
        converted = {
            'code': course.get('code', ''),
            'name': course.get('name', ''),
            'credits': int(course.get('credits', 0)),
            'instructor': course.get('instructor', 'اساتيد گروه آموزشي'),
            'schedule': schedule,
            'location': course_location,
            'description': course.get('description', ''),
            'exam_time': course.get('exam_time', ''),
            'capacity': course.get('capacity', ''),
            'gender_restriction': course.get('gender', ''),
            'enrollment_conditions': course.get('enrollment_conditions', ''),
            'is_available': is_available
        }
        
        converted['instructor'] = converted['instructor'].replace('<BR>', '').strip()
        converted['description'] = converted['description'].replace('<BR>', '')
        
        return converted
        
    except Exception as e:
        logger.error(f"Error converting course format: {e}")
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
        username: Golestan login username (required)
        password: Golestan login password (required)
    """
    try:
        logger.info("Updating courses from Golestan...")
        
        if username is None or password is None or username.strip() == "" or password.strip() == "":
            raise ValueError("Username and password are required to fetch from Golestan")
        
        golestan_courses = fetch_golestan_courses(username=username, password=password)
        
        COURSES.clear()
        COURSES.update(golestan_courses)
        
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