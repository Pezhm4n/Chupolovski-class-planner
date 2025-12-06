from typing import Dict, List, Optional, Union
import os
from dotenv import load_dotenv
import sqlite3
import requests
import time
from datetime import datetime, timedelta


class CourseDatabase:
    """Manages database operations with API and SQLite fallback."""

    def __init__(self, use_api: bool = True, force_local_scrape: bool = False):
        """
        Initialize database connection.

        Args:
            use_api: If True, attempts to use API first (default: True)
            force_local_scrape: If True, scrapes from Golestan immediately (default: False)
        """
        load_dotenv()

        self.sqlite_path = os.path.join(os.path.dirname(__file__), 'golestan_courses.db')
        self.force_local_scrape = force_local_scrape

        if self.force_local_scrape:
            self._scrape_and_store_locally()
            self.should_try_api = False
        else:
            self.api_url = os.getenv('API_URL', '').rstrip('/')
            self.should_try_api = use_api and bool(self.api_url)
            self.last_local_update = None
            self.local_data_timeout = timedelta(minutes=15)

    def _get_last_update_time(self) -> Optional[datetime]:
        """Get timestamp of last course update in local DB."""
        if not self.is_initialized():
            return None

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT MAX(updated_at) FROM courses")
            result = cursor.fetchone()[0]
            if result:
                return datetime.strptime(result, '%Y-%m-%d %H:%M:%S')
            return None
        except Exception:
            return None
        finally:
            cursor.close()
            conn.close()

    def _is_local_data_fresh(self) -> bool:
        """Check if local data is fresh (< 15 minutes old)."""
        last_update = self._get_last_update_time()
        if not last_update:
            return False

        age = datetime.now() - last_update
        return age < self.local_data_timeout

    def _api_request_with_retry(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Union[Dict, List]]:
        """Make API request with one retry after 1 second delay. Returns None if both fail."""
        if not self.should_try_api:
            return None

        for attempt in range(2):
            try:
                timeout = 5 if attempt == 0 else 3
                response = requests.get(f"{self.api_url}{endpoint}", params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException:
                if attempt == 0:
                    time.sleep(1)
                    continue
                else:
                    self.should_try_api = False
                    self.last_local_update = datetime.now()
                    return None

        return None

    def _should_retry_api(self) -> bool:
        """Check if 15 minutes passed since switching to local mode."""
        if self.should_try_api:
            return True

        if not self.last_local_update:
            return True

        time_since_local = datetime.now() - self.last_local_update
        if time_since_local >= self.local_data_timeout:
            self.should_try_api = True
            return True

        return False

    def get_connection(self):
        """Create and return SQLite connection."""
        conn = sqlite3.connect(self.sqlite_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def drop_all_tables(self):
        """Drop all tables - USE WITH CAUTION."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("DROP TABLE IF EXISTS course_schedules")
            cursor.execute("DROP TABLE IF EXISTS schedule_entries")
            cursor.execute("DROP TABLE IF EXISTS time_slots")
            cursor.execute("DROP TABLE IF EXISTS locations")
            cursor.execute("DROP TABLE IF EXISTS courses")
            cursor.execute("DROP TABLE IF EXISTS instructors")
            cursor.execute("DROP TABLE IF EXISTS genders")
            cursor.execute("DROP TABLE IF EXISTS departments")
            cursor.execute("DROP TABLE IF EXISTS faculties")
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def create_tables(self):
        """Create all database tables with indexes."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS faculties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    faculty_id INTEGER NOT NULL,
                    FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE CASCADE,
                    UNIQUE(name, faculty_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS genders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(6) UNIQUE NOT NULL
                )
            """)

            cursor.execute("INSERT OR IGNORE INTO genders (name) VALUES ('مرد')")
            cursor.execute("INSERT OR IGNORE INTO genders (name) VALUES ('زن')")
            cursor.execute("INSERT OR IGNORE INTO genders (name) VALUES ('مختلط')")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS instructors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS courses (
                    code VARCHAR(10) PRIMARY KEY,
                    name TEXT NOT NULL,
                    credits INTEGER DEFAULT 0,
                    department_id INTEGER NOT NULL,
                    instructor_id INTEGER,
                    gender_id INTEGER,
                    capacity VARCHAR(3),
                    enrollment_conditions TEXT,
                    exam_time VARCHAR(25),
                    is_available BOOLEAN DEFAULT TRUE,
                    updated_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id) ON DELETE SET NULL,
                    FOREIGN KEY (gender_id) REFERENCES genders(id) ON DELETE SET NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS time_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day VARCHAR(10) NOT NULL,
                    start_time VARCHAR(5) NOT NULL,
                    end_time VARCHAR(5) NOT NULL,
                    UNIQUE(day, start_time, end_time)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time_slot_id INTEGER NOT NULL,
                    parity VARCHAR(1),
                    location_id INTEGER,
                    FOREIGN KEY (time_slot_id) REFERENCES time_slots(id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL,
                    UNIQUE(time_slot_id, parity, location_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS course_schedules (
                    course_code VARCHAR(10) NOT NULL,
                    schedule_entry_id INTEGER NOT NULL,
                    PRIMARY KEY (course_code, schedule_entry_id),
                    FOREIGN KEY (course_code) REFERENCES courses(code) ON DELETE CASCADE,
                    FOREIGN KEY (schedule_entry_id) REFERENCES schedule_entries(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_name ON courses (name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_department ON courses (department_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_instructor ON courses (instructor_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_gender ON courses (gender_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_departments_faculty ON departments (faculty_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_slots_day ON time_slots (day)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_entries_timeslot ON schedule_entries (time_slot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_entries_location ON schedule_entries (location_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_instructors_name ON instructors (name)")

            conn.commit()
            print("✓ Database tables created")
        except Exception as e:
            conn.rollback()
            print(f"✗ Error creating tables: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def upsert_courses(self, courses_data: Dict, is_available: bool) -> int:
        """Insert or update courses in database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            course_count = 0

            for fac_name, departments in courses_data.items():
                cursor.execute("""
                    INSERT INTO faculties (name)
                    VALUES (?) ON CONFLICT (name) DO
                    UPDATE SET name = EXCLUDED.name
                """, (fac_name,))
                cursor.execute("SELECT id FROM faculties WHERE name = ?", (fac_name,))
                faculty_id = cursor.fetchone()[0]

                for dept_name, courses in departments.items():
                    cursor.execute("""
                        INSERT INTO departments (name, faculty_id)
                        VALUES (?, ?) ON CONFLICT (name, faculty_id) DO
                        UPDATE SET name = EXCLUDED.name
                    """, (dept_name, faculty_id))
                    cursor.execute("SELECT id FROM departments WHERE name = ? AND faculty_id = ?",
                                   (dept_name, faculty_id))
                    department_id = cursor.fetchone()[0]

                    for course in courses:
                        instructor_id = None
                        if course.get('instructor'):
                            cursor.execute("""
                                INSERT INTO instructors (name)
                                VALUES (?) ON CONFLICT (name) DO
                                UPDATE SET name = EXCLUDED.name
                            """, (course['instructor'],))
                            cursor.execute("SELECT id FROM instructors WHERE name = ?",
                                           (course['instructor'],))
                            instructor_id = cursor.fetchone()[0]

                        gender_id = None
                        if course.get('gender'):
                            cursor.execute("SELECT id FROM genders WHERE name = ?", (course['gender'],))
                            result = cursor.fetchone()
                            if result:
                                gender_id = result[0]

                        cursor.execute("""
                            INSERT INTO courses (code, name, credits, department_id, instructor_id,
                                               gender_id, capacity, enrollment_conditions, exam_time, is_available)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                            ON CONFLICT (code) DO UPDATE SET
                                name = EXCLUDED.name,
                                credits = EXCLUDED.credits,
                                department_id = EXCLUDED.department_id,
                                instructor_id = EXCLUDED.instructor_id,
                                gender_id = EXCLUDED.gender_id,
                                capacity = EXCLUDED.capacity,
                                enrollment_conditions = EXCLUDED.enrollment_conditions,
                                exam_time = EXCLUDED.exam_time,
                                is_available = EXCLUDED.is_available,
                                updated_at = CURRENT_TIMESTAMP
                        """, (
                            course['code'], course['name'], course['credits'],
                            department_id, instructor_id, gender_id,
                            course['capacity'], course['enrollment_conditions'],
                            course['exam_time'], is_available,
                        ))

                        cursor.execute("DELETE FROM course_schedules WHERE course_code = ?", (course['code'],))

                        for slot in course['schedule']:
                            cursor.execute("""
                                INSERT INTO time_slots (day, start_time, end_time)
                                VALUES (?, ?, ?) 
                                ON CONFLICT (day, start_time, end_time) DO
                                UPDATE SET day = EXCLUDED.day
                            """, (slot['day'], slot['start'], slot['end']))
                            cursor.execute(
                                "SELECT id FROM time_slots WHERE day = ? AND start_time = ? AND end_time = ?",
                                (slot['day'], slot['start'], slot['end']))
                            time_slot_id = cursor.fetchone()[0]

                            location_id = None
                            if slot.get('location'):
                                cursor.execute("""
                                    INSERT INTO locations (name)
                                    VALUES (?) ON CONFLICT (name) DO
                                    UPDATE SET name = EXCLUDED.name
                                """, (slot['location'],))
                                cursor.execute("SELECT id FROM locations WHERE name = ?", (slot['location'],))
                                location_id = cursor.fetchone()[0]

                            parity = slot.get('parity', '') or ''
                            cursor.execute("""
                                INSERT INTO schedule_entries (time_slot_id, parity, location_id)
                                VALUES (?, ?, ?) 
                                ON CONFLICT (time_slot_id, parity, location_id) DO
                                UPDATE SET time_slot_id = EXCLUDED.time_slot_id
                            """, (time_slot_id, parity, location_id))

                            if location_id is None:
                                cursor.execute(
                                    "SELECT id FROM schedule_entries WHERE time_slot_id = ? AND parity = ? AND location_id IS NULL",
                                    (time_slot_id, parity))
                            else:
                                cursor.execute(
                                    "SELECT id FROM schedule_entries WHERE time_slot_id = ? AND parity = ? AND location_id = ?",
                                    (time_slot_id, parity, location_id))
                            schedule_entry_id = cursor.fetchone()[0]

                            cursor.execute("""
                                INSERT INTO course_schedules (course_code, schedule_entry_id)
                                VALUES (?, ?) ON CONFLICT DO NOTHING
                            """, (course['code'], schedule_entry_id))

                        course_count += 1

            conn.commit()
            print(f"✓ Stored {course_count} courses")
            return course_count
        except Exception as e:
            conn.rollback()
            print(f"✗ Error storing courses: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def get_courses(self, availability: str = 'both',
                   return_hierarchy: bool = True, department_name: Optional[str] = None) -> Union[List[Dict], Dict]:
        """
        Get courses with automatic API/local fallback.

        Args:
            availability: 'available', 'unavailable', or 'both'
            return_hierarchy: Return as hierarchy or flat list
            return_hierarchy: Return as hierarchy or flat list
            department_name: Filter by department name (optional)
        """
        if self.force_local_scrape:
            return self._get_courses_local(department_name, availability, return_hierarchy)

        self._should_retry_api()

        if self.should_try_api:
            endpoint = f'/api/courses/department/{department_name}' if department_name else '/api/courses/all'

            api_result = self._api_request_with_retry(endpoint, {
                'availability': availability,
                'hierarchy': return_hierarchy
            })

            if api_result is not None:
                return api_result

        if not self.is_initialized() or self.get_course_count() == 0:
            self._scrape_and_store_locally()
        elif not self._is_local_data_fresh():
            self._scrape_and_store_locally()

        return self._get_courses_local(department_name, availability, return_hierarchy)

    def search_courses(self, search_term: str, search_in: str = 'both',
                      availability: str = 'both', return_hierarchy: bool = False) -> Union[List[Dict], Dict]:
        """
        Search courses by name or instructor.

        Args:
            search_term: Search query
            search_in: 'course', 'instructor', or 'both'
            availability: 'available', 'unavailable', or 'both'
            return_hierarchy: Return as hierarchy or flat list
        """
        if self.force_local_scrape:
            return self._search_courses_local(search_term, search_in, availability, return_hierarchy)

        self._should_retry_api()

        if self.should_try_api:
            api_result = self._api_request_with_retry('/api/courses/search', {
                'q': search_term,
                'search_in': search_in,
                'availability': availability,
                'hierarchy': return_hierarchy
            })

            if api_result is not None:
                return api_result

        if not self.is_initialized() or self.get_course_count() == 0:
            self._scrape_and_store_locally()
        elif not self._is_local_data_fresh():
            self._scrape_and_store_locally()

        return self._search_courses_local(search_term, search_in, availability, return_hierarchy)

    def get_faculties_with_departments(self) -> Dict[str, List[str]]:
        """Get all faculties with their departments."""
        if self.force_local_scrape:
            return self._get_faculties_with_departments_local()

        self._should_retry_api()

        if self.should_try_api:
            api_result = self._api_request_with_retry('/api/faculties')

            if api_result is not None:
                return api_result

        if not self.is_initialized() or self.get_course_count() == 0:
            self._scrape_and_store_locally()
        elif not self._is_local_data_fresh():
            self._scrape_and_store_locally()

        return self._get_faculties_with_departments_local()

    def _scrape_and_store_locally(self):
        """Scrape courses from Golestan and store in local DB."""
        print("🔄 Scraping courses from Golestan...")

        from app.scrapers.requests_scraper.fetch_data import scrape_and_store_courses
        scrape_and_store_courses(db=self)

    def _get_courses_local(self, department_name: Optional[str], availability: str,
                          return_hierarchy: bool) -> Union[List[Dict], Dict]:
        """Query courses from local database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            where_conditions = []
            params = []

            if department_name:
                where_conditions.append("d.name = ?")
                params.append(department_name)

            if availability != 'both':
                bool_value = '1' if availability == 'available' else '0'
                where_conditions.append(f"c.is_available = {bool_value}")

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            query = f"""
                SELECT 
                    c.code, c.name, c.credits, d.name as department, f.name as faculty,
                    i.name as instructor, g.name as gender, c.capacity,
                    c.enrollment_conditions, c.exam_time, c.is_available, c.updated_at,
                    GROUP_CONCAT(
                        ts.day || '|' || ts.start_time || '|' || ts.end_time || '|' || 
                        COALESCE(se.parity, '') || '|' || COALESCE(l.name, ''), ';;'
                    ) as schedule_data
                FROM courses c
                JOIN departments d ON c.department_id = d.id
                JOIN faculties f ON d.faculty_id = f.id
                LEFT JOIN instructors i ON c.instructor_id = i.id
                LEFT JOIN genders g ON c.gender_id = g.id
                LEFT JOIN course_schedules cs ON c.code = cs.course_code
                LEFT JOIN schedule_entries se ON cs.schedule_entry_id = se.id
                LEFT JOIN time_slots ts ON se.time_slot_id = ts.id
                LEFT JOIN locations l ON se.location_id = l.id
                {where_clause}
                GROUP BY c.code
                ORDER BY f.name, d.name, c.name
            """

            cursor.execute(query, params)
            results = self._parse_schedule_results(cursor)

            return self._build_hierarchy(results) if return_hierarchy else results
        finally:
            cursor.close()
            conn.close()

    def _search_courses_local(self, search_term: str, search_in: str,
                             availability: str, return_hierarchy: bool) -> Union[List[Dict], Dict]:
        """Search courses in local database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            search_parts = [
                part.replace(' ', '').replace('\u200c', '')
                for part in search_term.replace('\u200c', ' ').split()
                if part.strip()
            ]

            if not search_parts:
                return {} if return_hierarchy else []

            search_conditions = []
            params = []

            for part in search_parts:
                part_conditions = []
                pattern = f"%{part}%"

                if search_in in ['course', 'both']:
                    part_conditions.append("c.name LIKE ?")
                    params.append(pattern)

                if search_in in ['instructor', 'both']:
                    part_conditions.append("i.name LIKE ?")
                    params.append(pattern)

                if part_conditions:
                    search_conditions.append(f"({' OR '.join(part_conditions)})")

            where_clause = "WHERE " + " AND ".join(search_conditions)

            if availability != 'both':
                bool_value = '1' if availability == 'available' else '0'
                where_clause += f" AND c.is_available = {bool_value}"

            query = f"""
                SELECT 
                    c.code, c.name, c.credits, d.name as department, f.name as faculty,
                    i.name as instructor, g.name as gender, c.capacity,
                    c.enrollment_conditions, c.exam_time, c.is_available, c.updated_at,
                    GROUP_CONCAT(
                        ts.day || '|' || ts.start_time || '|' || ts.end_time || '|' || 
                        COALESCE(se.parity, '') || '|' || COALESCE(l.name, ''), ';;'
                    ) as schedule_data
                FROM courses c
                JOIN departments d ON c.department_id = d.id
                JOIN faculties f ON d.faculty_id = f.id
                LEFT JOIN instructors i ON c.instructor_id = i.id
                LEFT JOIN genders g ON c.gender_id = g.id
                LEFT JOIN course_schedules cs ON c.code = cs.course_code
                LEFT JOIN schedule_entries se ON cs.schedule_entry_id = se.id
                LEFT JOIN time_slots ts ON se.time_slot_id = ts.id
                LEFT JOIN locations l ON se.location_id = l.id
                {where_clause}
                GROUP BY c.code
                ORDER BY f.name, d.name, c.name
            """

            cursor.execute(query, params)
            results = self._parse_schedule_results(cursor)

            return self._build_hierarchy(results) if return_hierarchy else results
        finally:
            cursor.close()
            conn.close()

    def _get_faculties_with_departments_local(self) -> Dict[str, List[str]]:
        """Get faculties and departments from local database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT f.name as faculty, d.name as department
                FROM departments d
                JOIN faculties f ON d.faculty_id = f.id
                ORDER BY f.name, d.name
            """

            cursor.execute(query)

            result = {}
            for row in cursor.fetchall():
                faculty = row[0]
                department = row[1]

                if faculty not in result:
                    result[faculty] = []
                result[faculty].append(department)

            return result
        finally:
            cursor.close()
            conn.close()

    def _parse_schedule_results(self, cursor) -> List[Dict]:
        """Parse SQLite results with schedule data."""
        cursor.row_factory = sqlite3.Row
        results = []
        for row in cursor.fetchall():
            course = dict(row)
            schedule_data = course.pop('schedule_data', None)
            course['schedule'] = []
            if schedule_data:
                for entry in schedule_data.split(';;'):
                    parts = entry.split('|')
                    if len(parts) == 5:
                        course['schedule'].append({
                            'day': parts[0],
                            'start': parts[1],
                            'end': parts[2],
                            'parity': parts[3],
                            'location': parts[4]
                        })
            results.append(course)
        return results

    def _build_hierarchy(self, courses: List[Dict]) -> Dict:
        """Convert flat course list to hierarchical structure."""
        hierarchy = {}
        for course in courses:
            faculty = course['faculty']
            department = course['department']

            if faculty not in hierarchy:
                hierarchy[faculty] = {}

            if department not in hierarchy[faculty]:
                hierarchy[faculty][department] = []

            course_data = {k: v for k, v in course.items() if k not in ['faculty', 'department']}
            hierarchy[faculty][department].append(course_data)

        return hierarchy

    def get_course_count(self) -> int:
        """
        Get total number of courses.
        Uses API if available, otherwise queries local database.
        """
        # If force local mode, skip API
        if self.force_local_scrape:
            return self._get_course_count_local()

        # Check if we should retry API
        self._should_retry_api()

        # Try API first
        if self.should_try_api:
            api_result = self._api_request_with_retry('/api/stats')

            if api_result is not None and 'total_courses' in api_result:
                return api_result['total_courses']

        # Fall back to local database
        return self._get_course_count_local()

    def _get_course_count_local(self) -> int:
        """Get course count from local database."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM courses")
            count = cursor.fetchone()[0]
            return count
        finally:
            cursor.close()
            conn.close()

    def is_initialized(self) -> bool:
        """Check if all required database tables exist."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            required_tables = ['faculties', 'departments', 'courses', 'instructors',
                               'genders', 'time_slots', 'locations', 'schedule_entries',
                               'course_schedules']

            for table in required_tables:
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type = 'table' AND name = ?
                """, (table,))

                result = cursor.fetchone()
                if not result:
                    return False

            return True
        except Exception:
            return False
        finally:
            cursor.close()
            conn.close()

    def initialize_if_needed(self, force: bool = False) -> bool:
        """Initialize database tables if they don't exist."""
        if force or not self.is_initialized():
            if force:
                self.drop_all_tables()
            self.create_tables()
            return True
        return False

    def store_courses(self, available_courses: Dict = None, unavailable_courses: Dict = None,
                      auto_init: bool = True, force_reinit: bool = False):
        """Store parsed course data to database."""
        if auto_init:
            self.initialize_if_needed(force=force_reinit)

        total_courses = 0

        if available_courses:
            count = self.upsert_courses(available_courses, is_available=True)
            total_courses += count

        if unavailable_courses:
            count = self.upsert_courses(unavailable_courses, is_available=False)
            total_courses += count

        print(f"✓ Total: {total_courses} courses")
        return total_courses


# Singleton pattern
_instance = None

def get_db(use_api: bool = True, force_local_scrape: bool = False) -> CourseDatabase:
    """
    Get the shared singleton database instance.

    Args:
        use_api: Try API first (only used on first call)
        force_local_scrape: Force immediate scraping (only used on first call)

    Returns:
        CourseDatabase singleton instance
    """
    global _instance
    if _instance is None:
        _instance = CourseDatabase(use_api=use_api, force_local_scrape=force_local_scrape)
    return _instance

def reset_db():
    """Reset the singleton instance (useful for testing)."""
    global _instance
    _instance = None