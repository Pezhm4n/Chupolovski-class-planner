#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Search Worker Thread for course search operations
Handles background search to prevent UI freezing
"""

from PyQt5.QtCore import QThread, pyqtSignal
from app.core.logger import setup_logging
from app.data.courses_db import get_db

logger = setup_logging()


class SearchWorker(QThread):
    """Worker thread for course search operations"""
    
    # Signals
    search_finished = pyqtSignal(dict)  # Emits filtered courses dictionary
    search_progress = pyqtSignal(str)  # Progress message (optional)
    
    def __init__(self, courses_dict, filter_text, major_filter=None, filters=None):
        super().__init__()
        self.courses_dict = courses_dict
        self.filter_text = filter_text
        self.major_filter = major_filter
        self.filters = filters or {}
        self._cancelled = False
    
    def cancel(self):
        """Cancel the search operation"""
        self._cancelled = True
    
    def run(self):
        """Execute the search in background thread"""
        try:
            if self._cancelled:
                return
            
            filtered_courses = {}
            
            # First, filter by major if selected
            if self.major_filter and self.major_filter.strip():
                filtered_courses = {
                    key: course for key, course in self.courses_dict.items()
                    if course.get('major', '').strip() == self.major_filter.strip()
                }
            else:
                # Start with all courses if no major filter
                filtered_courses = dict(self.courses_dict)
            
            if self._cancelled:
                return
            
            # Then, apply search filter if search text is provided
            if self.filter_text and self.filter_text.strip():
                filter_text_lower = self.filter_text.strip().lower()
                
                # Optimize search by pre-compiling search terms
                search_terms = filter_text_lower.split()
                
                # Use set comprehension for faster filtering
                filtered_courses = {
                    key: course for key, course in filtered_courses.items()
                    if self._matches_search(course, search_terms)
                }
            
            if self._cancelled:
                return
            
            # Apply additional filters (time, general courses, gender)
            filtered_courses = self._apply_filters(filtered_courses)
            
            if not self._cancelled:
                self.search_finished.emit(filtered_courses)
                
        except Exception as e:
            logger.error(f"Error in SearchWorker: {e}")
            import traceback
            traceback.print_exc()
            if not self._cancelled:
                self.search_finished.emit({})
    
    def _matches_search(self, course, search_terms):
        """Check if course matches all search terms (optimized)"""
        # Pre-compute lowercased values once
        name_lower = course.get('name', '').lower()
        code_lower = course.get('code', '').lower()
        instructor_lower = course.get('instructor', '').lower()
        
        # Check if all search terms match
        for term in search_terms:
            if (term not in name_lower and 
                term not in code_lower and 
                term not in instructor_lower):
                return False
        return True
    
    def _apply_filters(self, courses):
        """Apply time, general courses, and gender filters"""
        from .filter_dialog import GENERAL_COURSES
        
        filtered = courses
        
        # Time filter
        time_from = self.filters.get('time_from')
        time_to = self.filters.get('time_to')
        if time_from is not None and time_to is not None:
            filtered = {
                key: course for key, course in filtered.items()
                if self._matches_time_filter(course, time_from, time_to)
            }
        
        # General courses filter
        if self.filters.get('general_courses_only', False):
            filtered = {
                key: course for key, course in filtered.items()
                if self._is_general_course(course, GENERAL_COURSES)
            }
        
        # Gender filter
        gender_filter = self.filters.get('gender')
        if gender_filter:
            filtered = {
                key: course for key, course in filtered.items()
                if self._matches_gender_filter(course, gender_filter)
            }
        
        return filtered
    
    def _matches_time_filter(self, course, time_from, time_to):
        """Check if course has any session in the time range"""
        schedule = course.get('schedule', [])
        if not schedule:
            return False
        
        for session in schedule:
            start = session.get('start', '')
            end = session.get('end', '')
            
            if start and end:
                # Extract hour from time string (format: "HH:MM")
                try:
                    start_hour = int(start.split(':')[0])
                    end_hour = int(end.split(':')[0])
                    
                    # Check if session overlaps with filter range
                    # Session overlaps if: start_hour <= time_to AND end_hour >= time_from
                    # This includes sessions that start or end at the boundaries
                    if start_hour <= time_to and end_hour >= time_from:
                        return True
                except (ValueError, IndexError):
                    continue
        
        return False
    
    def _is_general_course(self, course, general_courses_list):
        """Check if course is a general course"""
        from app.core.text_normalizer import is_general_course_match
        
        course_name = course.get('name', '')
        if not course_name:
            return False
        
        for general_course_pattern in general_courses_list:
            if is_general_course_match(course_name, general_course_pattern):
                return True
        
        return False
    
    def _matches_gender_filter(self, course, gender_filter):
        """Check if course matches gender filter"""
        course_gender = course.get('gender_restriction', '')
        if not course_gender:
            # If course has no gender restriction, it's considered "مختلط"
            return gender_filter == 'مختلط'
        
        # Normalize gender values for matching
        # Support both old and new values
        gender_mapping = {
            'آقا': 'مرد',
            'خانم': 'زن',
            'مرد': 'مرد',
            'زن': 'زن',
            'مختلط': 'مختلط'
        }
        
        normalized_course_gender = gender_mapping.get(course_gender, course_gender)
        normalized_filter = gender_mapping.get(gender_filter, gender_filter)
        
        return normalized_course_gender == normalized_filter