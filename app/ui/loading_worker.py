#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loading Worker Thread for initial data loading
Handles background loading of courses and user data
"""

import time
from PyQt5.QtCore import QThread, pyqtSignal
from app.core.logger import setup_logging

logger = setup_logging()


class InitialLoadWorker(QThread):
    """Worker thread for initial data loading"""
    
    # Signals
    progress = pyqtSignal(str)  # Progress message
    courses_loaded = pyqtSignal(int)  # Number of courses loaded
    finished = pyqtSignal(object)  # Result or exception
    cache_hit = pyqtSignal(bool)  # Whether cache was used
    
    def __init__(self, db, use_cache=True):
        super().__init__()
        self.db = db
        self.use_cache = use_cache
        self.start_time = None
        self.end_time = None
    
    def run(self):
        """Execute the loading in background thread"""
        try:
            self.start_time = time.time()
            
            # Check cache first
            from app.core.cache_manager import load_cached_courses, save_cached_courses
            from app.core.config import COURSES
            from pathlib import Path
            
            cached_courses = None
            if self.use_cache:
                self.progress.emit("در حال بررسی cache...")
                source_files = [
                    Path('app/data/courses_data/available_courses.json'),
                    Path('app/data/courses_data/unavailable_courses.json'),
                    Path('app/data/courses_data.json')
                ]
                cached_courses = load_cached_courses(source_files)
                
                if cached_courses:
                    self.cache_hit.emit(True)
                    self.progress.emit("بارگذاری از cache...")
                    COURSES.clear()
                    COURSES.update(cached_courses)
                    self.end_time = time.time()
                    load_time = self.end_time - self.start_time
                    logger.info(f"Loaded {len(COURSES)} courses from cache in {load_time:.2f}s")
                    self.courses_loaded.emit(len(COURSES))
                    self.finished.emit(True)
                    return
            
            self.cache_hit.emit(False)
            
            # Load from database or JSON
            if self.db is not None:
                self.progress.emit("در حال بارگذاری از دیتابیس...")
                from app.core.golestan_integration import load_courses_from_database
                db_courses = load_courses_from_database(self.db)
                
                if db_courses:
                    COURSES.clear()
                    COURSES.update(db_courses)
                    
                    # Load user-added courses
                    from app.core.data_manager import load_user_added_courses
                    load_user_added_courses()
                    
                    # Save to cache
                    if self.use_cache:
                        from pathlib import Path
                        source_files = [
                            Path('app/data/courses_data/available_courses.json'),
                            Path('app/data/courses_data/unavailable_courses.json')
                        ]
                        save_cached_courses(COURSES, source_files)
                    
                    self.end_time = time.time()
                    load_time = self.end_time - self.start_time
                    logger.info(f"Loaded {len(COURSES)} courses from database in {load_time:.2f}s")
                    self.courses_loaded.emit(len(COURSES))
                    self.finished.emit(True)
                    return
            
            # Fallback to JSON
            self.progress.emit("در حال بارگذاری از فایل‌های JSON...")
            from app.core.data_manager import load_courses_from_json
            load_courses_from_json()
            
            # Save to cache
            if self.use_cache and COURSES:
                from pathlib import Path
                source_files = [
                    Path('app/data/courses_data/available_courses.json'),
                    Path('app/data/courses_data/unavailable_courses.json'),
                    Path('app/data/courses_data.json')
                ]
                save_cached_courses(COURSES, source_files)
            
            self.end_time = time.time()
            load_time = self.end_time - self.start_time
            logger.info(f"Loaded {len(COURSES)} courses from JSON in {load_time:.2f}s")
            self.courses_loaded.emit(len(COURSES))
            self.finished.emit(True)
            
        except Exception as e:
            logger.error(f"Error in InitialLoadWorker: {e}")
            import traceback
            traceback.print_exc()
            self.finished.emit(e)

