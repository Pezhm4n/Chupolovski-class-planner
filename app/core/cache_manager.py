#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache Manager for Golestoon Class Planner
Handles caching of course data and loading results to improve startup performance
"""

import os
import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any
from app.core.logger import setup_logging
from app.core.config import APP_DIR

logger = setup_logging()

# Cache directory
CACHE_DIR = APP_DIR / 'data' / 'cache'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache file paths
COURSES_CACHE_FILE = CACHE_DIR / 'courses_cache.json'
COURSES_CACHE_META_FILE = CACHE_DIR / 'courses_cache_meta.json'


def get_file_hash(file_path: Path) -> Optional[str]:
    """Get MD5 hash of a file"""
    try:
        if not file_path.exists():
            return None
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Error calculating file hash for {file_path}: {e}")
        return None


def get_cache_key(source_files: list) -> str:
    """Generate cache key from source file hashes"""
    hashes = []
    for file_path in source_files:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        elif not isinstance(file_path, Path):
            continue
        if not file_path.is_absolute():
            file_path = APP_DIR / file_path
        file_hash = get_file_hash(file_path)
        if file_hash:
            hashes.append(f"{file_path.name}:{file_hash}")
    return hashlib.md5('|'.join(hashes).encode()).hexdigest() if hashes else ""


def load_cached_courses(source_files: list) -> Optional[Dict[str, Any]]:
    """
    Load courses from cache if available and valid
    
    Args:
        source_files: List of source file paths that courses are loaded from
        
    Returns:
        Cached courses dict or None if cache is invalid/missing
    """
    try:
        if not COURSES_CACHE_FILE.exists() or not COURSES_CACHE_META_FILE.exists():
            return None
        
        with open(COURSES_CACHE_META_FILE, 'r', encoding='utf-8') as f:
            cache_meta = json.load(f)
        
        current_cache_key = get_cache_key(source_files)
        if cache_meta.get('cache_key') != current_cache_key:
            logger.info("Cache invalid - source files changed")
            return None
        
        cache_age = time.time() - cache_meta.get('timestamp', 0)
        if cache_age > 7 * 24 * 3600:  # 7 days
            logger.info("Cache expired - too old")
            return None
        
        with open(COURSES_CACHE_FILE, 'r', encoding='utf-8') as f:
            cached_data = json.load(f)
        
        logger.info(f"Loaded {len(cached_data.get('courses', {}))} courses from cache")
        return cached_data.get('courses', {})
        
    except Exception as e:
        logger.warning(f"Error loading cache: {e}")
        return None


def save_cached_courses(courses: Dict[str, Any], source_files: list):
    """
    Save courses to cache
    
    Args:
        courses: Courses dictionary to cache
        source_files: List of source file paths
    """
    try:
        cache_key = get_cache_key(source_files)
        
        with open(COURSES_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'courses': courses}, f, ensure_ascii=False, indent=2)
        
        cache_meta = {
            'cache_key': cache_key,
            'timestamp': time.time(),
            'course_count': len(courses)
        }
        with open(COURSES_CACHE_META_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_meta, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Cached {len(courses)} courses")
        
    except Exception as e:
        logger.warning(f"Error saving cache: {e}")


def clear_cache():
    """Clear all cached data"""
    try:
        if COURSES_CACHE_FILE.exists():
            COURSES_CACHE_FILE.unlink()
        if COURSES_CACHE_META_FILE.exists():
            COURSES_CACHE_META_FILE.unlink()
        logger.info("Cache cleared")
    except Exception as e:
        logger.warning(f"Error clearing cache: {e}")

