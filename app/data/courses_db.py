from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from psycopg2.extras import execute_values, Json

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
import sqlite3


class CourseDatabase:
    """Manages database operations with PostgreSQL or SQLite fallback."""

    def __init__(self, db_config: Optional[Dict] = None, force_sqlite: bool = False):
        """
        Initialize database connection configuration.

        Args:
            db_config: Dictionary with keys: host, database, user, password.
                      If None, loads from environment variables.
            force_sqlite: If True, use SQLite even if PostgreSQL is available.
        """
        self.use_postgres = False
        self.use_sqlite = False

        # Try PostgreSQL first unless forced to use SQLite
        if not force_sqlite and POSTGRES_AVAILABLE:
            try:
                if db_config is None:
                    load_dotenv()
                    db_config = {
                        'host': os.getenv('DB_HOST', 'localhost'),
                        'database': os.getenv('DB_NAME', 'golestan_courses'),
                        'user': os.getenv('DB_USER', 'postgres'),
                        'password': os.getenv('DB_PASSWORD', 'password')
                    }

                self.config = db_config
                self._create_database_if_not_exists()
                self.use_postgres = True
                print("✓ Using PostgreSQL database")

            except Exception as e:
                print(f"⚠ PostgreSQL connection failed: {e}")
                print("✓ Falling back to SQLite database")
                self._setup_sqlite()
        else:
            # Use SQLite (either forced or PostgreSQL not available)
            if not POSTGRES_AVAILABLE:
                print("⚠ psycopg2 not installed (run: pip install psycopg2-binary)")
            print("✓ Using SQLite database")
            self._setup_sqlite()

    def _setup_sqlite(self):
        """Setup SQLite database."""
        self.use_sqlite = True
        self.sqlite_path = os.path.join(os.path.dirname(__file__), 'golestan_courses.db')
        print(f"  Database file: {self.sqlite_path}")

    def _create_database_if_not_exists(self):
        """Create the PostgreSQL database if it doesn't exist."""
        try:
            # Connect to default 'postgres' database to create our database
            conn = psycopg2.connect(
                host=self.config['host'],
                user=self.config['user'],
                password=self.config['password'],
                database='postgres'  # Connect to default database
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            try:
                # Check if database exists
                cursor.execute(
                    "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
                    (self.config['database'],)
                )
                exists = cursor.fetchone()

                if not exists:
                    # Create database
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {}").format(
                            sql.Identifier(self.config['database'])
                        )
                    )
                    print(f"  Database '{self.config['database']}' created successfully")
                else:
                    print(f"  Database '{self.config['database']}' already exists")

            finally:
                cursor.close()
                conn.close()

        except Exception as e:
            print(f"✗ Error with database setup: {e}")
            raise  # Re-raise to be caught in __init__

    def get_connection(self):
        """Create and return appropriate database connection."""
        if self.use_postgres:
            return psycopg2.connect(**self.config)
        else:
            # SQLite connection with foreign key support enabled
            conn = sqlite3.connect(self.sqlite_path)
            conn.execute("PRAGMA foreign_keys = ON")
            return conn

    def _get_placeholder(self):
        """Return appropriate placeholder for SQL queries."""
        return "%s" if self.use_postgres else "?"


    def _adapt_create_table_syntax(self, postgres_sql: str) -> str:
        """Convert PostgreSQL CREATE TABLE syntax to SQLite."""
        if self.use_postgres:
            return postgres_sql

        # Convert SERIAL to INTEGER PRIMARY KEY AUTOINCREMENT
        sqlite_sql = postgres_sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")

        # Convert TIMESTAMP to TEXT (SQLite doesn't have native timestamp)
        sqlite_sql = sqlite_sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                                        "TEXT DEFAULT (datetime('now'))")

        return sqlite_sql

    def drop_all_tables(self):
        """Drop all tables - USE WITH CAUTION! This deletes all data."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if self.use_postgres:
                # PostgreSQL supports CASCADE
                cursor.execute("DROP TABLE IF EXISTS course_schedules CASCADE")
                cursor.execute("DROP TABLE IF EXISTS schedule_entries CASCADE")
                cursor.execute("DROP TABLE IF EXISTS time_slots CASCADE")
                cursor.execute("DROP TABLE IF EXISTS locations CASCADE")
                cursor.execute("DROP TABLE IF EXISTS courses CASCADE")
                cursor.execute("DROP TABLE IF EXISTS instructors CASCADE")
                cursor.execute("DROP TABLE IF EXISTS genders CASCADE")
                cursor.execute("DROP TABLE IF EXISTS departments CASCADE")
                cursor.execute("DROP TABLE IF EXISTS faculties CASCADE")
            else:
                # SQLite doesn't support CASCADE in DROP TABLE
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
            print("✓ All tables dropped successfully")

        except Exception as e:
            conn.rollback()
            print(f"✗ Error dropping tables: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def create_tables(self):
        """Create fully normalized database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create faculties table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS faculties (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create departments table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS departments (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    faculty_id INTEGER NOT NULL,
                    FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE CASCADE,
                    UNIQUE(name, faculty_id)
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create genders table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS genders (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(6) UNIQUE NOT NULL
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Pre-populate genders
            if self.use_postgres:
                cursor.execute("""
                    INSERT INTO genders (name)
                    VALUES ('مرد'), ('زن'), ('مختلط')
                    ON CONFLICT (name) DO NOTHING
                """)
            else:
                cursor.execute("INSERT OR IGNORE INTO genders (name) VALUES ('مرد')")
                cursor.execute("INSERT OR IGNORE INTO genders (name) VALUES ('زن')")
                cursor.execute("INSERT OR IGNORE INTO genders (name) VALUES ('مختلط')")

            # Create instructors table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS instructors (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create courses table
            sql_statement = """
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
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
                    FOREIGN KEY (instructor_id) REFERENCES instructors(id) ON DELETE SET NULL,
                    FOREIGN KEY (gender_id) REFERENCES genders(id) ON DELETE SET NULL
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create locations table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS locations (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create time_slots table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS time_slots (
                    id SERIAL PRIMARY KEY,
                    day VARCHAR(10) NOT NULL,
                    start_time VARCHAR(5) NOT NULL,
                    end_time VARCHAR(5) NOT NULL,
                    UNIQUE(day, start_time, end_time)
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create schedule_entries table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS schedule_entries (
                    id SERIAL PRIMARY KEY,
                    time_slot_id INTEGER NOT NULL,
                    parity VARCHAR(1),
                    location_id INTEGER,
                    FOREIGN KEY (time_slot_id) REFERENCES time_slots(id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL,
                    UNIQUE(time_slot_id, parity, location_id)
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))

            # Create junction table
            sql_statement = """
                CREATE TABLE IF NOT EXISTS course_schedules (
                    course_code VARCHAR(10) NOT NULL,
                    schedule_entry_id INTEGER NOT NULL,
                    PRIMARY KEY (course_code, schedule_entry_id),
                    FOREIGN KEY (course_code) REFERENCES courses(code) ON DELETE CASCADE,
                    FOREIGN KEY (schedule_entry_id) REFERENCES schedule_entries(id) ON DELETE CASCADE
                )
            """
            cursor.execute(self._adapt_create_table_syntax(sql_statement))


            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_name ON courses (name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_department ON courses (department_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_instructor ON courses (instructor_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_courses_gender ON courses (gender_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_departments_faculty ON departments (faculty_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_time_slots_day ON time_slots (day)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_schedule_entries_timeslot ON schedule_entries (time_slot_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedule_entries_location ON schedule_entries (location_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_instructors_name ON instructors (name)")

            conn.commit()
            print("✓ Database tables created successfully")

        except Exception as e:
            conn.rollback()
            print(f"✗ Error creating tables: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def upsert_courses(self, courses_data: Dict, is_available) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            course_count = 0
            placeholder = self._get_placeholder()

            for fac_name, departments in courses_data.items():
                # Insert or get faculty ID
                if self.use_postgres:
                    cursor.execute(f"""
                        INSERT INTO faculties (name)
                        VALUES ({placeholder}) ON CONFLICT (name) DO
                        UPDATE SET name = EXCLUDED.name
                        RETURNING id
                    """, (fac_name,))
                    faculty_id = cursor.fetchone()[0]
                else:
                    cursor.execute(f"""
                        INSERT INTO faculties (name)
                        VALUES ({placeholder}) ON CONFLICT (name) DO
                        UPDATE SET name = EXCLUDED.name
                    """, (fac_name,))
                    # Always SELECT to get ID (lastrowid unreliable with ON CONFLICT)
                    cursor.execute("SELECT id FROM faculties WHERE name = ?", (fac_name,))
                    faculty_id = cursor.fetchone()[0]

                for dept_name, courses in departments.items():
                    # Insert or get department ID
                    if self.use_postgres:
                        cursor.execute(f"""
                            INSERT INTO departments (name, faculty_id)
                            VALUES ({placeholder}, {placeholder}) ON CONFLICT (name, faculty_id) DO
                            UPDATE SET name = EXCLUDED.name
                            RETURNING id
                        """, (dept_name, faculty_id))
                        department_id = cursor.fetchone()[0]
                    else:
                        cursor.execute(f"""
                            INSERT INTO departments (name, faculty_id)
                            VALUES ({placeholder}, {placeholder}) ON CONFLICT (name, faculty_id) DO
                            UPDATE SET name = EXCLUDED.name
                        """, (dept_name, faculty_id))
                        # Always SELECT to get ID
                        cursor.execute("SELECT id FROM departments WHERE name = ? AND faculty_id = ?",
                                       (dept_name, faculty_id))
                        department_id = cursor.fetchone()[0]

                    for course in courses:
                        # Insert or get instructor ID
                        instructor_id = None
                        if course.get('instructor'):
                            if self.use_postgres:
                                cursor.execute(f"""
                                    INSERT INTO instructors (name)
                                    VALUES ({placeholder}) ON CONFLICT (name) DO
                                    UPDATE SET name = EXCLUDED.name
                                    RETURNING id
                                """, (course['instructor'],))
                                instructor_id = cursor.fetchone()[0]
                            else:
                                cursor.execute(f"""
                                    INSERT INTO instructors (name)
                                    VALUES ({placeholder}) ON CONFLICT (name) DO
                                    UPDATE SET name = EXCLUDED.name
                                """, (course['instructor'],))
                                # Always SELECT to get ID
                                cursor.execute("SELECT id FROM instructors WHERE name = ?",
                                               (course['instructor'],))
                                instructor_id = cursor.fetchone()[0]

                        # Get gender ID
                        gender_id = None
                        if course.get('gender'):
                            cursor.execute(f"""
                                SELECT id FROM genders WHERE name = {placeholder}
                            """, (course['gender'],))
                            result = cursor.fetchone()
                            if result:
                                gender_id = result[0]

                        # Insert or update course
                        cursor.execute(f"""
                            INSERT INTO courses (code, name, credits, department_id, instructor_id,
                                               gender_id, capacity, enrollment_conditions, exam_time, is_available)
                            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 
                                    {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}) 
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
                            course['code'],
                            course['name'],
                            course['credits'],
                            department_id,
                            instructor_id,
                            gender_id,
                            course['capacity'],
                            course['enrollment_conditions'],
                            course['exam_time'],
                            is_available,
                        ))

                        # Delete existing schedule associations
                        cursor.execute(f"""
                            DELETE FROM course_schedules WHERE course_code = {placeholder}
                        """, (course['code'],))

                        # Process schedule slots
                        for slot in course['schedule']:
                            # Insert time_slot
                            if self.use_postgres:
                                cursor.execute(f"""
                                    INSERT INTO time_slots (day, start_time, end_time)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}) 
                                    ON CONFLICT (day, start_time, end_time) DO
                                    UPDATE SET day = EXCLUDED.day
                                    RETURNING id
                                """, (slot['day'], slot['start'], slot['end']))
                                time_slot_id = cursor.fetchone()[0]
                            else:
                                cursor.execute(f"""
                                    INSERT INTO time_slots (day, start_time, end_time)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}) 
                                    ON CONFLICT (day, start_time, end_time) DO
                                    UPDATE SET day = EXCLUDED.day
                                """, (slot['day'], slot['start'], slot['end']))
                                # Always SELECT to get ID
                                cursor.execute(
                                    "SELECT id FROM time_slots WHERE day = ? AND start_time = ? AND end_time = ?",
                                    (slot['day'], slot['start'], slot['end']))
                                time_slot_id = cursor.fetchone()[0]

                            # Insert location (if exists)
                            location_id = None
                            if slot.get('location'):
                                if self.use_postgres:
                                    cursor.execute(f"""
                                        INSERT INTO locations (name)
                                        VALUES ({placeholder}) ON CONFLICT (name) DO
                                        UPDATE SET name = EXCLUDED.name
                                        RETURNING id
                                    """, (slot['location'],))
                                    location_id = cursor.fetchone()[0]
                                else:
                                    cursor.execute(f"""
                                        INSERT INTO locations (name)
                                        VALUES ({placeholder}) ON CONFLICT (name) DO
                                        UPDATE SET name = EXCLUDED.name
                                    """, (slot['location'],))
                                    # Always SELECT to get ID
                                    cursor.execute("SELECT id FROM locations WHERE name = ?",
                                                   (slot['location'],))
                                    location_id = cursor.fetchone()[0]

                            # Insert schedule_entry
                            parity = slot.get('parity', '') or ''

                            if self.use_postgres:
                                cursor.execute(f"""
                                    INSERT INTO schedule_entries (time_slot_id, parity, location_id)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}) 
                                    ON CONFLICT (time_slot_id, parity, location_id) DO
                                    UPDATE SET time_slot_id = EXCLUDED.time_slot_id
                                    RETURNING id
                                """, (time_slot_id, parity, location_id))
                                schedule_entry_id = cursor.fetchone()[0]
                            else:
                                cursor.execute(f"""
                                    INSERT INTO schedule_entries (time_slot_id, parity, location_id)
                                    VALUES ({placeholder}, {placeholder}, {placeholder}) 
                                    ON CONFLICT (time_slot_id, parity, location_id) DO
                                    UPDATE SET time_slot_id = EXCLUDED.time_slot_id
                                """, (time_slot_id, parity, location_id))

                                # Always SELECT to get ID with proper NULL handling
                                if location_id is None:
                                    cursor.execute(
                                        "SELECT id FROM schedule_entries WHERE time_slot_id = ? AND parity = ? AND location_id IS NULL",
                                        (time_slot_id, parity))
                                else:
                                    cursor.execute(
                                        "SELECT id FROM schedule_entries WHERE time_slot_id = ? AND parity = ? AND location_id = ?",
                                        (time_slot_id, parity, location_id))
                                schedule_entry_id = cursor.fetchone()[0]

                            # Link course to schedule
                            cursor.execute(f"""
                                INSERT INTO course_schedules (course_code, schedule_entry_id)
                                VALUES ({placeholder}, {placeholder}) ON CONFLICT DO NOTHING
                            """, (course['code'], schedule_entry_id))

                        course_count += 1

            conn.commit()
            print(f"✓ Successfully stored/updated {course_count} courses")
            return course_count

        except Exception as e:
            conn.rollback()
            print(f"✗ Error upserting courses: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def get_course_count(self) -> int:
        """Get total number of courses in database."""
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
        """
        Check if all required database tables exist.

        Returns:
            True if all tables exist, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            required_tables = ['faculties', 'departments', 'courses', 'instructors',
                               'genders', 'time_slots', 'locations', 'schedule_entries',
                               'course_schedules']

            for table in required_tables:
                if self.use_postgres:
                    cursor.execute("""
                                   SELECT EXISTS (SELECT
                                                  FROM information_schema.tables
                                                  WHERE table_name = %s)
                                   """, (table,))
                else:
                    cursor.execute("""
                                   SELECT name
                                   FROM sqlite_master
                                   WHERE type = 'table'
                                     AND name = ?
                                   """, (table,))

                result = cursor.fetchone()
                if not result or not result[0]:
                    return False

            return True

        except Exception:
            return False
        finally:
            cursor.close()
            conn.close()

    def initialize_if_needed(self, force: bool = False) -> bool:
        """
        Initialize database tables if they don't exist.

        Args:
            force: If True, drop existing tables and recreate

        Returns:
            True if initialization was performed, False if already initialized
        """
        if force or not self.is_initialized():
            print("🔄 Initializing database...")
            if force:
                self.drop_all_tables()
            self.create_tables()
            print("✓ Database initialized")
            return True
        else:
            print("✓ Database already initialized")
            return False

    def store_courses(self, available_courses: Dict = None, unavailable_courses: Dict = None,
                      auto_init: bool = True, force_reinit: bool = False):
        """
        Store parsed course data to database.

        Args:
            available_courses: Dictionary of available courses from parser
            unavailable_courses: Dictionary of unavailable courses from parser
            auto_init: If True, automatically initialize database if needed (default: True)
            force_reinit: If True, drop and recreate tables regardless of state
        """
        # Auto-initialize if needed
        if auto_init:
            self.initialize_if_needed(force=force_reinit)

        total_courses = 0

        # Store available courses
        if available_courses:
            count = self.upsert_courses(available_courses, is_available=True)
            total_courses += count

        # Store unavailable courses
        if unavailable_courses:
            count = self.upsert_courses(unavailable_courses, is_available=False)
            total_courses += count

        print(f"✓ Total courses in database: {total_courses}")

    def search_courses(self, search_term: str, search_in: str = 'both', availability: str = 'both') -> List[Dict]:
        """Search with support for multiple words in any order."""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Split search term by space/ZWNJ and normalize each part
            search_parts = [
                part.replace(' ', '').replace('\u200c', '')
                for part in search_term.replace('\u200c', ' ').split()
                if part.strip()
            ]

            if not search_parts:
                return []

            search_conditions = []
            params = []

            # For each search part, create conditions
            for part in search_parts:
                part_conditions = []
                pattern = f"%{part}%"

                if search_in in ['course', 'both']:
                    if self.use_postgres:
                        part_conditions.append(
                            "REPLACE(REPLACE(c.name, ' ', ''), CHR(8204), '') LIKE %s"
                        )
                    else:
                        part_conditions.append(
                            "REPLACE(REPLACE(c.name, ' ', ''), CHAR(8204), '') LIKE ?"
                        )
                    params.append(pattern)

                if search_in in ['instructor', 'both']:
                    if self.use_postgres:
                        part_conditions.append(
                            "REPLACE(REPLACE(i.name, ' ', ''), CHR(8204), '') LIKE %s"
                        )
                    else:
                        part_conditions.append(
                            "REPLACE(REPLACE(i.name, ' ', ''), CHAR(8204), '') LIKE ?"
                        )
                    params.append(pattern)

                if part_conditions:
                    search_conditions.append(f"({' OR '.join(part_conditions)})")

            # Combine with AND so all parts must match
            where_clause = " AND ".join(search_conditions)

            # Build availability filter
            availability_filter = ""
            if availability == 'available':
                availability_filter = "AND c.is_available = TRUE"
            elif availability == 'unavailable':
                availability_filter = "AND c.is_available = FALSE"

            query = f"""
                SELECT 
                    c.code,
                    c.name,
                    c.credits,
                    d.name as department,
                    f.name as faculty,
                    i.name as instructor,
                    g.name as gender,
                    c.capacity,
                    c.enrollment_conditions,
                    c.exam_time,
                    c.is_available,
                    c.updated_at
                FROM courses c
                JOIN departments d ON c.department_id = d.id
                JOIN faculties f ON d.faculty_id = f.id
                LEFT JOIN instructors i ON c.instructor_id = i.id
                LEFT JOIN genders g ON c.gender_id = g.id
                WHERE {where_clause}
                {availability_filter}
                ORDER BY c.name
            """

            cursor.execute(query, params)

            if self.use_postgres:
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            else:
                cursor.row_factory = sqlite3.Row
                results = [dict(row) for row in cursor.fetchall()]
            for course in results:
                print(course)
            return results

        finally:
            cursor.close()
            conn.close()

    def get_courses_by_department(self, department_name: str, availability: str = 'both') -> List[Dict]:
        """
        Get all courses for a specific department (works for both PostgreSQL and SQLite).
        Args:
            department_name: Name of the department
            availability: 'available', 'unavailable', or 'both' (default: 'both')
        Returns:
            List of course dictionaries with full details
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = [department_name]
            # Choose appropriate boolean based on backend
            if self.use_postgres:
                available_true = 'TRUE'
                available_false = 'FALSE'
            else:
                available_true = '1'
                available_false = '0'
            availability_filter = ""
            if availability == 'available':
                availability_filter = f"AND c.is_available = {available_true}"
            elif availability == 'unavailable':
                availability_filter = f"AND c.is_available = {available_false}"

            placeholder = self._get_placeholder()
            query = f"""
                SELECT
                    c.code,
                    c.name,
                    c.credits,
                    d.name as department,
                    f.name as faculty,
                    i.name as instructor,
                    g.name as gender,
                    c.capacity,
                    c.enrollment_conditions,
                    c.exam_time,
                    c.is_available,
                    c.updated_at
                FROM courses c
                JOIN departments d ON c.department_id = d.id
                JOIN faculties f ON d.faculty_id = f.id
                LEFT JOIN instructors i ON c.instructor_id = i.id
                LEFT JOIN genders g ON c.gender_id = g.id
                WHERE d.name = {placeholder}
                {availability_filter}
                ORDER BY c.name
            """
            cursor.execute(query, params)
            if self.use_postgres:
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            else:
                cursor.row_factory = sqlite3.Row
                results = [dict(row) for row in cursor.fetchall()]
            for course in results:
                print(course)
            return results
        finally:
            cursor.close()
            conn.close()

    def get_all_courses(self, availability: str = 'both', return_hierarchy: bool = False):
        """
        Get all courses from the database.

        Args:
            availability: 'available', 'unavailable', or 'both' (default: 'both')
            return_hierarchy: If True, returns hierarchical dict; if False, returns flat list (default: False)

        Returns:
            If return_hierarchy=False: List of course dictionaries
            If return_hierarchy=True: Dict in format {faculty: {department: [courses]}}

        Examples:
            db.get_all_courses()  # Returns list
            db.get_all_courses(return_hierarchy=True)  # Returns hierarchy
            db.get_all_courses(availability='available', return_hierarchy=True)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Determine correct boolean values
            bool_true = 'TRUE' if self.use_postgres else '1'
            bool_false = 'FALSE' if self.use_postgres else '0'

            # Build availability filter
            availability_filter = ""
            if availability == 'available':
                availability_filter = f"WHERE c.is_available = {bool_true}"
            elif availability == 'unavailable':
                availability_filter = f"WHERE c.is_available = {bool_false}"

            query = f"""
                SELECT 
                    c.code,
                    c.name,
                    c.credits,
                    d.name as department,
                    f.name as faculty,
                    i.name as instructor,
                    g.name as gender,
                    c.capacity,
                    c.enrollment_conditions,
                    c.exam_time,
                    c.is_available,
                    c.updated_at
                FROM courses c
                JOIN departments d ON c.department_id = d.id
                JOIN faculties f ON d.faculty_id = f.id
                LEFT JOIN instructors i ON c.instructor_id = i.id
                LEFT JOIN genders g ON c.gender_id = g.id
                {availability_filter}
                ORDER BY f.name, d.name, c.name
            """

            cursor.execute(query)

            if self.use_postgres:
                columns = [desc[0] for desc in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            else:
                cursor.row_factory = sqlite3.Row
                results = [dict(row) for row in cursor.fetchall()]

            # Return flat list if not hierarchy
            if not return_hierarchy:
                return results

            # Build hierarchy structure
            hierarchy = {}
            for course in results:
                faculty = course['faculty']
                department = course['department']

                # Initialize faculty if not exists
                if faculty not in hierarchy:
                    hierarchy[faculty] = {}

                # Initialize department if not exists
                if department not in hierarchy[faculty]:
                    hierarchy[faculty][department] = []

                # Add course to department (without faculty/department fields to avoid redundancy)
                course_data = {k: v for k, v in course.items() if k not in ['faculty', 'department']}
                hierarchy[faculty][department].append(course_data)

            return hierarchy

        finally:
            cursor.close()
            conn.close()

    def get_faculties_with_departments(self) -> Dict[str, List[str]]:
        """
        Get all faculties with their departments in a hierarchical structure.
        Perfect for GUI dropdowns and tree views.

        Returns:
            Dictionary where keys are faculty names and values are lists of department names

        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            query = """
                    SELECT f.name as faculty, \
                           d.name as department
                    FROM departments d
                             JOIN faculties f ON d.faculty_id = f.id
                    ORDER BY f.name, d.name \
                    """

            cursor.execute(query)

            # Build hierarchical structure
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
