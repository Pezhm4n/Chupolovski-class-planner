import sqlite3
import os
import json
import time
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from ..core.settings import settings
from ..core.logger import setup_logging
from ..core.course_utils import to_minutes

logger = setup_logging()


class CourseDatabase:
    def __init__(self, db_path: str = "courses.db"):
        self.db_path = str(db_path)  # Convert Path to string
        self.connection = None
        self._init_db()
        self._singleton_instance = None

    def _init_db(self):
        """Initialize the database and create tables if they don't exist."""
        # Use check_same_thread=False to allow access from multiple threads
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        cursor = self.connection.cursor()

        # Create courses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT NOT NULL,
                course_name TEXT NOT NULL,
                instructor TEXT,
                credits INTEGER,
                capacity INTEGER,
                enrolled INTEGER,
                time_slots TEXT,
                days TEXT,
                location TEXT,
                prerequisites TEXT,
                department TEXT,
                faculty TEXT, 
                semester TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create metadata table to track data freshness
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create faculties table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS faculties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)

        # Create departments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                faculty_id INTEGER,
                FOREIGN KEY (faculty_id) REFERENCES faculties (id)
            )
        """)

        self.connection.commit()

    def _is_data_fresh(self) -> bool:
        """Check if the data in the database is fresh (less than 15 minutes old)."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM courses")
        count = cursor.fetchone()['count']

        if count == 0:
            return False

        # Check if the last update was within 15 minutes
        cursor.execute("SELECT MAX(last_updated) as last_update FROM courses")
        result = cursor.fetchone()
        if result and result['last_update']:
            last_update = datetime.fromisoformat(result['last_update'])
            return datetime.now() >= last_update >= datetime.now() - timedelta(minutes=15)
        return False

    def fetch_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch courses from API if available."""
        if not settings.API_URL:
            logger.info("API_URL not configured, skipping API fetch")
            return None

        # Correct endpoint logic
        base_url = settings.API_URL.rstrip('/')
        if not base_url.endswith('/api/courses/all'):
            api_url = f"{base_url}/api/courses/all"
        else:
            api_url = base_url

        try:
            logger.info(f"Attempting to fetch courses from API: {api_url}")

            params = {
                'hierarchy': 'false',
                'availability': 'both'
            }

            response = requests.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, list):
                logger.error(f"API returned unexpected format: expected list, got {type(data)}")
                return None

            logger.info(f"Fetched {len(data)} courses from API")
            return data

        except requests.exceptions.RequestException as e:
            logger.warning(f"API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode API response: {e}")
            return None

    def store_courses(self, courses: List[Dict[str, Any]]) -> None:
        """Store courses in the database, replacing existing data."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()

        # Clear existing courses
        cursor.execute("DELETE FROM courses")

        # Insert new courses
        for course in courses:
            # CLEANING DATA
            faculty = (course.get('faculty') or 'General').strip()
            department = (course.get('department') or '').strip()
            course_name = (course.get('course_name') or course.get('name') or '').strip()
            instructor = (course.get('instructor') or '').strip()

            cursor.execute("""
                INSERT INTO courses (
                    course_code, course_name, instructor, credits, capacity, 
                    enrolled, time_slots, days, location, prerequisites, 
                    department, faculty, semester
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                course.get('course_code') or course.get('code'),
                course_name,
                instructor,
                course.get('credits'),
                course.get('capacity'),
                course.get('enrolled'),
                json.dumps(course.get('time_slots', []) if 'time_slots' in course else course.get('schedule', [])),
                json.dumps(course.get('days', [])),
                course.get('location'),
                json.dumps(course.get('prerequisites', [])),
                department,
                faculty,
                course.get('semester')
            ))

        self.connection.commit()
        logger.info(f"Stored {len(courses)} courses in database")

    def _ensure_fresh_data(self):
        """Ensure database has fresh data, fetching from API if needed."""
        if not self._is_data_fresh():
            logger.info("Database data is stale or empty, attempting to fetch from API...")
            courses = self.fetch_from_api()
            if courses is not None:
                self.store_courses(courses)
            else:
                logger.info("API fetch failed or not available, using existing database data")

    def search_courses(self, query: str) -> List[Dict[str, Any]]:
        """Search for courses based on a query string."""
        self._ensure_fresh_data()

        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()
        search_pattern = f"%{query}%"
        cursor.execute("""
            SELECT * FROM courses 
            WHERE course_name LIKE ? OR course_code LIKE ? OR instructor LIKE ?
        """, (search_pattern, search_pattern, search_pattern))

        return self._parse_schedule_results(cursor)

    def get_all_courses(self) -> List[Dict[str, Any]]:
        """Get all courses from the database."""
        self._ensure_fresh_data()

        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM courses")

        return self._parse_schedule_results(cursor)

    def get_course_count(self) -> int:
        """Get the total count of courses in the database."""
        self._ensure_fresh_data()

        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM courses")
        result = cursor.fetchone()
        return result['count'] if result else 0

    def get_course_by_id(self, course_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific course by ID."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))

        results = self._parse_schedule_results(cursor)
        return results[0] if results else None

    def _parse_schedule_results(self, cursor) -> List[Dict[str, Any]]:
        """Parse SQLite results into course dictionaries in a UI-friendly format."""
        results = []
        rows = cursor.fetchall()
        for row in rows:
            course = dict(row)

            # Normalize course code: expose both `course_code` (DB) and `code` (UI/legacy)
            course_code = course.get('course_code') or course.get('code')
            if course_code:
                course['course_code'] = course_code
                course['code'] = course_code

            # Normalize name: DB uses `course_name`, UI expects `name`
            name = course.get('name') or course.get('course_name')
            course['name'] = name or ''

            # Normalize credits to int
            try:
                course['credits'] = int(course.get('credits') or 0)
            except (ValueError, TypeError):
                course['credits'] = 0

            # Robust major construction: "Faculty - Department" to match old JSON/UI expectations
            faculty = (course.get('faculty') or 'General').strip()
            department = (course.get('department') or '').strip()
            course['major'] = f"{faculty} - {department}" if department else faculty

            # Parse JSON/text fields that are stored as JSON strings in the DB
            for field in ['time_slots', 'days', 'prerequisites']:
                if course.get(field):
                    try:
                        if isinstance(course[field], str):
                            course[field] = json.loads(course[field])
                    except (json.JSONDecodeError, TypeError):
                        course[field] = []
                else:
                    # Ensure the key exists with a consistent type
                    if field not in course:
                        course[field] = []

            # Derive `schedule` from `time_slots` to mimic the old JSON format
            if course.get('time_slots'):
                course['schedule'] = course['time_slots']
            else:
                # Guarantee `schedule` exists and is a list
                schedule = course.get('schedule')
                if isinstance(schedule, str):
                    try:
                        schedule = json.loads(schedule)
                    except (json.JSONDecodeError, TypeError):
                        schedule = []
                if not isinstance(schedule, list):
                    schedule = []
                course['schedule'] = schedule

            results.append(course)
        return results

    def get_faculties_with_departments(self) -> Dict[str, List[str]]:
        """Get a dictionary of faculties with their departments."""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

        cursor = self.connection.cursor()

        try:
            cursor.execute("""
                SELECT DISTINCT faculty, department
                FROM courses
                WHERE faculty IS NOT NULL AND faculty != ''
            """)
            rows = cursor.fetchall()

            faculties_dict = {}
            if rows:
                for row in rows:
                    fac_name = (row['faculty'] or '').strip()
                    dept_name = (row['department'] or '').strip()

                    if not fac_name: continue

                    if fac_name not in faculties_dict:
                        faculties_dict[fac_name] = []

                    if dept_name and dept_name not in faculties_dict[fac_name]:
                        faculties_dict[fac_name].append(dept_name)

            if not faculties_dict:
                cursor.execute("""
                    SELECT DISTINCT department
                    FROM courses
                    WHERE department IS NOT NULL AND department != ''
                """)
                departments = cursor.fetchall()
                if departments:
                    faculties_dict['General'] = [d['department'].strip() for d in departments if d['department']]

            if not faculties_dict:
                faculties_dict['General'] = ['All Departments']

            return faculties_dict

        except sqlite3.OperationalError:
            return {'General': ['All Departments']}

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()


# Singleton instance
_database_instance = None


def get_db() -> CourseDatabase:
    """Get the singleton instance of CourseDatabase."""
    global _database_instance
    if _database_instance is None:
        db_path = str(settings.DATABASE_PATH)
        _database_instance = CourseDatabase(db_path)
    return _database_instance


# Backward compatibility alias
SmartCourseDatabase = CourseDatabase