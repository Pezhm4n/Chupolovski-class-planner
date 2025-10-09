"""
Database module for storing and retrieving Golestan course data.
Handles PostgreSQL operations including table creation, upsert, and queries.
"""

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
                    name VARCHAR(20) UNIQUE NOT NULL
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
                    code VARCHAR(50) PRIMARY KEY,
                    name TEXT NOT NULL,
                    credits INTEGER DEFAULT 0,
                    department_id INTEGER NOT NULL,
                    instructor_id INTEGER,
                    gender_id INTEGER,
                    capacity VARCHAR(20),
                    enrollment_conditions TEXT,
                    exam_time VARCHAR(100),
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
                    day VARCHAR(20) NOT NULL,
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
                    course_code VARCHAR(50) NOT NULL,
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

            for fac_name, departments in courses_data.items():
                # Insert or get faculty ID
                cursor.execute("""
                               INSERT INTO faculties (name)
                               VALUES (%s) ON CONFLICT (name) DO
                               UPDATE SET name = EXCLUDED.name
                                   RETURNING id
                               """, (fac_name,))
                faculty_id = cursor.fetchone()[0]

                for dept_name, courses in departments.items():
                    # Insert or get department ID
                    cursor.execute("""
                                   INSERT INTO departments (name, faculty_id)
                                   VALUES (%s, %s) ON CONFLICT (name, faculty_id) DO
                                   UPDATE SET name = EXCLUDED.name
                                       RETURNING id
                                   """, (dept_name, faculty_id))
                    department_id = cursor.fetchone()[0]

                    for course in courses:
                        # Insert or get instructor ID
                        instructor_id = None
                        if course.get('instructor'):
                            cursor.execute("""
                                           INSERT INTO instructors (name)
                                           VALUES (%s) ON CONFLICT (name) DO
                                           UPDATE SET name = EXCLUDED.name
                                               RETURNING id
                                           """, (course['instructor'],))
                            instructor_id = cursor.fetchone()[0]

                        # Get gender ID
                        gender_id = None
                        if course.get('gender'):
                            cursor.execute("""
                                           SELECT id
                                           FROM genders
                                           WHERE name = %s
                                           """, (course['gender'],))
                            result = cursor.fetchone()
                            if result:
                                gender_id = result[0]


                        # Insert or update course (now references course_template only)
                        cursor.execute("""
                                       INSERT INTO courses (code, name, credits, department_id, instructor_id,
                                                            gender_id, capacity,
                                                            enrollment_conditions, exam_time, is_available)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (code)
                            DO
                                       UPDATE SET
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
                        cursor.execute("""
                                       DELETE
                                       FROM course_schedules
                                       WHERE course_code = %s
                                       """, (course['code'],))

                        # Process schedule slots (same as before)
                        for slot in course['schedule']:
                            cursor.execute("""
                                           INSERT INTO time_slots (day, start_time, end_time)
                                           VALUES (%s, %s, %s) ON CONFLICT (day, start_time, end_time)
                                DO
                                           UPDATE SET day = EXCLUDED.day
                                               RETURNING id
                                           """, (slot['day'], slot['start'], slot['end']))
                            time_slot_id = cursor.fetchone()[0]

                            location_id = None
                            if slot.get('location'):
                                cursor.execute("""
                                               INSERT INTO locations (name)
                                               VALUES (%s) ON CONFLICT (name) DO
                                               UPDATE SET name = EXCLUDED.name
                                                   RETURNING id
                                               """, (slot['location'],))
                                location_id = cursor.fetchone()[0]

                            cursor.execute("""
                                           INSERT INTO schedule_entries (time_slot_id, parity, location_id)
                                           VALUES (%s, %s, %s) ON CONFLICT (time_slot_id, parity, location_id)
                                DO
                                           UPDATE SET time_slot_id = EXCLUDED.time_slot_id
                                               RETURNING id
                                           """, (time_slot_id, slot.get('parity', ''), location_id))
                            schedule_entry_id = cursor.fetchone()[0]

                            cursor.execute("""
                                           INSERT INTO course_schedules (course_code, schedule_entry_id)
                                           VALUES (%s, %s) ON CONFLICT DO NOTHING
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
