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

# Use the core config
from .config import COURSES, USER_DATA_FILE, COURSES_DATA_FILE, APP_DIR
from .logger import setup_logging

# Set up logger
logger = setup_logging()

# Define backup directory
BACKUP_DIR = APP_DIR / 'data' / 'backups'

# Ensure backup directory exists
os.makedirs(BACKUP_DIR, exist_ok=True)

# ---------------------- Course Data Management ----------------------

def load_courses_from_json():
    """Load all courses from Golestan JSON files with enhanced error handling"""
    global COURSES
    try:
        from .golestan_integration import load_golestan_data
        logger.info("Loading courses from Golestan data files...")
        
        # Load courses from Golestan data files
        golestan_courses = load_golestan_data()
        
        # Update COURSES dictionary
        COURSES.clear()
        COURSES.update(golestan_courses)
        
        logger.info(f"Successfully loaded {len(COURSES)} courses from Golestan data files")
        print(f"Loaded {len(COURSES)} courses from Golestan data files")
        
    except Exception as e:
        logger.error(f"Error loading courses from Golestan data: {e}")
        print(f"Error loading courses from Golestan data: {e}")
        COURSES = {}

def save_courses_to_json():
    """Save all courses to JSON file - deprecated, no longer used"""
    logger.info("save_courses_to_json is deprecated - courses are saved in Golestan data files")
    pass

# Add new function to load courses from Golestan data
def load_courses_from_golestan_data():
    """Load courses from Golestan scraper data files"""
    global COURSES
    try:
        from .golestan_integration import load_golestan_data
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
        from .config import APP_DIR
        courses_data_dir = APP_DIR / 'data' / 'courses_data'
        
        available_courses_file = courses_data_dir / 'available_courses.json'
        unavailable_courses_file = courses_data_dir / 'unavailable_courses.json'
        
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
    """Load user data from JSON file or latest backup"""
    # First check if main file exists
    if os.path.exists(USER_DATA_FILE):
        logger.info(f"Loading user data from main file: {USER_DATA_FILE}")
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ensure required keys exist
            required_keys = ['custom_courses', 'saved_combos', 'current_schedule']
            for key in required_keys:
                if key not in data:
                    data[key] = []
                    
            logger.info(f"Successfully loaded user data from main file: {USER_DATA_FILE}")
            return data
        except Exception as e:
            logger.error(f"Error loading user data from main file {USER_DATA_FILE}: {e}")
    
    # If main file doesn't exist or failed to load, try to load from latest backup
    logger.info("Main user data file not found or failed to load, checking for backups...")
    try:
        # Find all backup files
        backup_pattern = str(BACKUP_DIR / "user_data_*.json")
        backup_files = glob.glob(backup_pattern)
        
        # Also check in the data directory (legacy backups)
        legacy_backup_pattern = str(APP_DIR / 'data' / "user_data.json.backup_*")
        legacy_backup_files = glob.glob(legacy_backup_pattern)
        backup_files.extend(legacy_backup_files)
        
        if backup_files:
            # Sort by modification time to get the latest
            backup_files.sort(key=os.path.getmtime, reverse=True)
            latest_backup = backup_files[0]
            
            logger.info(f"Loading user data from latest backup: {latest_backup}")
            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ensure required keys exist
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
    
    # If nothing worked, return default structure
    logger.info("No user data file or backups found, returning default structure")
    return {
        'custom_courses': [],
        'saved_combos': [],
        'current_schedule': []
    }

def save_user_data(user_data):
    """Save user data to JSON file with backup functionality"""
    try:
        # Create backup first
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = BACKUP_DIR / f"user_data_{timestamp}.json"
        
        # If main file exists, copy it to backup location
        if os.path.exists(USER_DATA_FILE):
            import shutil
            shutil.copy2(USER_DATA_FILE, backup_file)
            logger.info(f"Backup created: {backup_file}")
        else:
            # If main file doesn't exist, create backup from current data
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Backup created from current data: {backup_file}")
        
        # Save to main file
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        logger.info(f"User data saved to: {USER_DATA_FILE}")
        
        # Clean up old backups (keep only last 5)
        cleanup_old_backups()
        
    except Exception as e:
        logger.error(f"Error saving user data to {USER_DATA_FILE}: {e}")

def cleanup_old_backups():
    """Clean up old backup files, keeping only the last 5"""
    try:
        # Find all backup files in the backups directory
        backup_pattern = str(BACKUP_DIR / "user_data_*.json")
        backup_files = glob.glob(backup_pattern)
        
        # Also check in the data directory (legacy backups)
        legacy_backup_pattern = str(APP_DIR / 'data' / "user_data.json.backup_*")
        legacy_backup_files = glob.glob(legacy_backup_pattern)
        backup_files.extend(legacy_backup_files)
        
        # Sort by modification time
        backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # Remove backups older than 5
        for old_backup in backup_files[5:]:
            try:
                os.remove(old_backup)
                logger.info(f"Removed old backup: {old_backup}")
            except Exception as e:
                logger.error(f"Failed to remove backup {old_backup}: {e}")
                
        # Move legacy backups to the correct directory
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
        # Create backup with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = BACKUP_DIR / f"user_data_auto_{timestamp}.json"
        
        # Save current user data to backup file
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Auto-backup created: {backup_file}")
        
        # Clean up old auto-backups (keep only last 5)
        cleanup_auto_backups()
        
        return backup_file
    except Exception as e:
        logger.error(f"Error creating auto-backup: {e}")
        return None

def cleanup_auto_backups():
    """Clean up old auto-backup files, keeping only the last 5"""
    try:
        # Find all auto backup files in the backups directory
        auto_backup_pattern = str(BACKUP_DIR / "user_data_auto_*.json")
        auto_backup_files = glob.glob(auto_backup_pattern)
        
        # Sort by modification time (newest first)
        auto_backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # Remove auto backups older than 5
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
        # Find all auto backup files in the backups directory
        auto_backup_pattern = str(BACKUP_DIR / "user_data_auto_*.json")
        auto_backup_files = glob.glob(auto_backup_pattern)
        
        if not auto_backup_files:
            logger.info("No auto-backup files found")
            return None
            
        # Sort by modification time (newest first)
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
        
        # Ensure required keys exist
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
        # Find all backup files (both manual and auto)
        manual_backup_pattern = str(BACKUP_DIR / "user_data_*.json")
        auto_backup_pattern = str(BACKUP_DIR / "user_data_auto_*.json")
        
        manual_backup_files = glob.glob(manual_backup_pattern)
        auto_backup_files = glob.glob(auto_backup_pattern)
        
        # Combine all backup files
        all_backup_files = manual_backup_files + auto_backup_files
        
        # Sort by modification time (newest first)
        all_backup_files.sort(key=os.path.getmtime, reverse=True)
        
        # Return only the requested limit
        return all_backup_files[:limit]
    except Exception as e:
        logger.error(f"Error getting backup history: {e}")
        return []

# Import datetime here to avoid circular imports
import datetime