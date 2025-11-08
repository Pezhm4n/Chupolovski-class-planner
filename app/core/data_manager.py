"""
Core data management module for the Golestoon Class Planner application.

This module handles loading, saving, and managing application data including:
- Course data
- User preferences
- Schedule backups
"""

import os
import json
import logging
import glob
from pathlib import Path

from .config import COURSES, USER_DATA_FILE, USER_ADDED_COURSES_FILE, COURSES_DATA_FILE, APP_DIR
from .logger import setup_logging

logger = setup_logging()

BACKUP_DIR = APP_DIR / 'data' / 'backups'

os.makedirs(BACKUP_DIR, exist_ok=True)

def load_user_added_courses():
    """Load user-added courses from dedicated JSON file"""
    global COURSES
    try:
        if USER_ADDED_COURSES_FILE.exists():
            with open(USER_ADDED_COURSES_FILE, 'r', encoding='utf-8') as f:
                user_added_data = json.load(f)
                user_courses = user_added_data.get('courses', [])
                
                for course in user_courses:
                    course_key = course.get('code', f"user_{len(COURSES)}")
                    course['key'] = course_key
                    from app.core.translator import translator
                    course['major'] = translator.t("hardcoded_texts.user_added_courses")
                    COURSES[course_key] = course
                    
                logger.info(f"Successfully loaded {len(user_courses)} user-added courses")
                if os.environ.get('DEBUG'):
                    print(f"Loaded {len(user_courses)} user-added courses")
        else:
            with open(USER_ADDED_COURSES_FILE, 'w', encoding='utf-8') as f:
                json.dump({"courses": []}, f, ensure_ascii=False, indent=2)
            logger.info("Created empty user_added_courses.json file")
    except Exception as e:
        logger.error(f"Error loading user-added courses: {e}")
        if os.environ.get('DEBUG'):
            print(f"Error loading user-added courses: {e}")

def save_user_added_courses():
    """Save user-added courses to dedicated JSON file"""
    try:
        from app.core.translator import translator
        user_added_category = translator.t("hardcoded_texts.user_added_courses")
        user_courses = [course for course in COURSES.values() 
                       if course.get('major') == user_added_category]
        
        user_added_data = {
            "courses": user_courses
        }
        
        with open(USER_ADDED_COURSES_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_added_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Successfully saved {len(user_courses)} user-added courses")
        if os.environ.get('DEBUG'):
            print(f"Saved {len(user_courses)} user-added courses")
    except Exception as e:
        logger.error(f"Error saving user-added courses: {e}")
        if os.environ.get('DEBUG'):
            print(f"Error saving user-added courses: {e}")

def load_courses_from_json():
    """Load all courses from Golestan JSON files with enhanced error handling"""
    global COURSES
    try:
        from .golestan_integration import load_golestan_data
        logger.info("Loading courses from Golestan data files...")
        
        golestan_courses = load_golestan_data()
        
        COURSES.clear()
        COURSES.update(golestan_courses)
        
        load_user_added_courses()
        
        logger.info(f"Successfully loaded {len(COURSES)} courses from Golestan data and user data")
        if os.environ.get('DEBUG'):
            print(f"Loaded {len(COURSES)} courses from Golestan data and user data")
        
    except Exception as e:
        logger.error(f"Error loading courses from Golestan data: {e}")
        if os.environ.get('DEBUG'):
            print(f"Error loading courses from Golestan data: {e}")

def golestan_data_files_exist():
    """Check if Golestan data files exist in the courses_data directory"""
    try:
        from .config import APP_DIR
        courses_data_dir = APP_DIR / 'data' / 'courses_data'
        
        available_courses_file = courses_data_dir / 'available_courses.json'
        unavailable_courses_file = courses_data_dir / 'unavailable_courses.json'
        
        return os.path.exists(available_courses_file) or os.path.exists(unavailable_courses_file)
    except Exception as e:
        logger.error(f"Error checking Golestan data files: {e}")
        return False

def load_user_data():
    """Load user data from JSON file or latest backup"""
    if os.path.exists(USER_DATA_FILE):
        logger.info(f"Loading user data from main file: {USER_DATA_FILE}")
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            required_keys = ['custom_courses', 'saved_combos', 'current_schedule']
            for key in required_keys:
                if key not in data:
                    data[key] = []
                    
            logger.info(f"Successfully loaded user data from main file: {USER_DATA_FILE}")
            return data
        except Exception as e:
            logger.error(f"Error loading user data from main file {USER_DATA_FILE}: {e}")
    
    logger.info("Main user data file not found or failed to load, checking for backups...")
    try:
        backup_pattern = str(BACKUP_DIR / "user_data_*.json")
        backup_files = glob.glob(backup_pattern)
        
        legacy_backup_pattern = str(APP_DIR / 'data' / "user_data.json.backup_*")
        legacy_backup_files = glob.glob(legacy_backup_pattern)
        backup_files.extend(legacy_backup_files)
        
        if backup_files:
            backup_files.sort(key=os.path.getmtime, reverse=True)
            latest_backup = backup_files[0]
            
            logger.info(f"Loading user data from latest backup: {latest_backup}")
            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            required_keys = ['custom_courses', 'saved_combos', 'current_schedule']
            for key in required_keys:
                if key not in data:
                    data[key] = []
                    
            logger.info(f"Successfully loaded user data from backup: {latest_backup}")
            return data
        else:
            logger.info("No backup files found")
    except Exception as e:
        logger.error(f"Error loading user data from backups: {e}")
    
    logger.info("No user data file or backups found, returning default structure")
    return {
        'custom_courses': [],
        'saved_combos': [],
        'current_schedule': []
    }

def save_user_data(user_data):
    """Save user data to JSON file with backup functionality"""
    try:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = BACKUP_DIR / f"user_data_{timestamp}.json"
        
        if os.path.exists(USER_DATA_FILE):
            import shutil
            shutil.copy2(USER_DATA_FILE, backup_file)
            logger.info(f"Backup created: {backup_file}")
        else:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Backup created from current data: {backup_file}")
        
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        logger.info(f"User data saved to: {USER_DATA_FILE}")
        
        save_user_added_courses()
        cleanup_old_backups()
        
    except Exception as e:
        logger.error(f"Error saving user data to {USER_DATA_FILE}: {e}")

def cleanup_old_backups():
    """Clean up old backup files, keeping only the last 5"""
    try:
        backup_pattern = str(BACKUP_DIR / "user_data_*.json")
        backup_files = glob.glob(backup_pattern)
        
        legacy_backup_pattern = str(APP_DIR / 'data' / "user_data.json.backup_*")
        legacy_backup_files = glob.glob(legacy_backup_pattern)
        backup_files.extend(legacy_backup_files)
        
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        for old_backup in backup_files[5:]:
            try:
                os.remove(old_backup)
                logger.info(f"Removed old backup: {old_backup}")
            except Exception as e:
                logger.error(f"Failed to remove backup {old_backup}: {e}")
                
        for legacy_backup in legacy_backup_files:
            try:
                filename = os.path.basename(legacy_backup)
                new_location = BACKUP_DIR / filename
                if not os.path.exists(new_location):
                    import shutil
                    shutil.move(legacy_backup, new_location)
                    logger.info(f"Moved legacy backup to correct location: {new_location}")
            except Exception as e:
                logger.error(f"Failed to move legacy backup {legacy_backup}: {e}")
                
    except Exception as e:
        logger.error(f"Backup cleanup failed: {e}")

def generate_unique_key(base_key, existing_keys):
    """Generate a unique key by appending a counter if needed"""
    if base_key not in existing_keys:
        return base_key
    
    counter = 1
    new_key = f"{base_key}_{counter}"
    while new_key in existing_keys:
        counter += 1
        new_key = f"{base_key}_{counter}"
    
    return new_key

def create_auto_backup(user_data):
    """Create an automatic backup before app exit"""
    try:
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = BACKUP_DIR / f"user_data_auto_{timestamp}.json"
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Auto-backup created: {backup_file}")
        
        cleanup_auto_backups()
        
        return backup_file
    except Exception as e:
        logger.error(f"Error creating auto-backup: {e}")
        return None

def cleanup_auto_backups():
    """Clean up old auto-backup files, keeping only the last 5"""
    try:
        auto_backup_pattern = str(BACKUP_DIR / "user_data_auto_*.json")
        auto_backup_files = glob.glob(auto_backup_pattern)
        
        auto_backup_files.sort(key=os.path.getmtime, reverse=True)
        
        for old_backup in auto_backup_files[5:]:
            try:
                os.remove(old_backup)
                logger.info(f"Removed old auto-backup: {old_backup}")
            except Exception as e:
                logger.error(f"Failed to remove auto-backup {old_backup}: {e}")
                
        logger.info("Auto-backup cleanup complete (kept last 5 files)")
        
    except Exception as e:
        logger.error(f"Auto-backup cleanup failed: {e}")

def get_latest_auto_backup():
    """Get the latest auto backup file"""
    try:
        auto_backup_pattern = str(BACKUP_DIR / "user_data_auto_*.json")
        auto_backup_files = glob.glob(auto_backup_pattern)
        
        if not auto_backup_files:
            logger.info("No auto-backup files found")
            return None
            
        auto_backup_files.sort(key=os.path.getmtime, reverse=True)
        
        latest_backup = auto_backup_files[0]
        logger.info(f"Latest auto-backup found: {latest_backup}")
        return latest_backup
    except Exception as e:
        logger.error(f"Error finding latest auto-backup: {e}")
        return None

def load_auto_backup(backup_file):
    """Load data from an auto backup file"""
    try:
        logger.info(f"Loading auto-backup: {backup_file}")
        
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        required_keys = ['custom_courses', 'saved_combos', 'current_schedule']
        for key in required_keys:
            if key not in data:
                data[key] = []
                
        logger.info(f"Successfully loaded auto-backup: {backup_file}")
        return data
    except Exception as e:
        logger.error(f"Error loading auto-backup {backup_file}: {e}")
        return None

def get_backup_history(limit=5):
    """Get the backup history (all backup files sorted by date)"""
    try:
        manual_backup_pattern = str(BACKUP_DIR / "user_data_*.json")
        auto_backup_pattern = str(BACKUP_DIR / "user_data_auto_*.json")
        
        manual_backup_files = glob.glob(manual_backup_pattern)
        auto_backup_files = glob.glob(auto_backup_pattern)
        
        all_backup_files = manual_backup_files + auto_backup_files
        
        all_backup_files.sort(key=os.path.getmtime, reverse=True)
        
        return all_backup_files[:limit]
    except Exception as e:
        logger.error(f"Error getting backup history: {e}")
        return []

_course_database = None

def set_course_database(db):
    """Set the global course database instance"""
    global _course_database
    _course_database = db

def get_course_database():
    """Get the global course database instance"""
    global _course_database
    return _course_database

import datetime