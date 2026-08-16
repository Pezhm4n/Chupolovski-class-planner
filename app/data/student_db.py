import sqlite3
import os
import decimal
from pathlib import Path
from typing import Optional
from decimal import Decimal
from datetime import datetime
from app.scrapers.requests_scraper.models import Student, SemesterRecord, CourseEnrollment

import logging
logger = logging.getLogger("app.data.student_db")



class StudentDatabase:
    """Manages per-user SQLite database for student academic records"""

    def __init__(self, student_id: str):
        """
        Initialize database for a specific student.

        Args:
            student_id: Unique student identifier
        """
        self.student_id = student_id
        data_dir = Path(__file__).resolve().parent
        self.db_path = os.path.join(data_dir, f"student_{student_id}.db")

    def _create_tables(self, cursor):
        """Create necessary tables if they don't exist"""

        # Students table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS students
                       (
                           student_id              TEXT PRIMARY KEY,
                           name                    TEXT NOT NULL,
                           father_name             TEXT,
                           faculty                 TEXT,
                           department              TEXT,
                           major                   TEXT,
                           degree_level            TEXT,
                           study_type              TEXT,
                           enrollment_status       TEXT,
                           registration_permission INTEGER,
                           overall_gpa             TEXT,
                           total_units_passed      TEXT,
                           total_probation         INTEGER,
                           consecutive_probation   INTEGER,
                           special_probation       INTEGER,
                           updated_at              TEXT,
                           image_b64               TEXT
                       )
                       """)

        # Semesters table - semester_id as PRIMARY KEY
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS semesters
                       (
                           semester_id             INTEGER PRIMARY KEY,
                           semester_description    TEXT,
                           semester_gpa            TEXT,
                           units_taken             TEXT,
                           units_passed            TEXT,
                           units_failed            TEXT,
                           units_dropped           TEXT,
                           cumulative_gpa          TEXT,
                           cumulative_units_passed TEXT,
                           semester_status         TEXT,
                           semester_type           TEXT,
                           probation_status        TEXT
                       )
                       """)

        # Courses table - composite key (semester_id, course_code)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS courses
                       (
                           semester_id  INTEGER NOT NULL,
                           course_code  TEXT    NOT NULL,
                           course_name  TEXT,
                           course_units TEXT,
                           course_type  TEXT,
                           grade_state  TEXT,
                           grade        TEXT,
                           PRIMARY KEY (semester_id, course_code),
                           FOREIGN KEY (semester_id) REFERENCES semesters (semester_id)
                       )
                       """)

        # Report 272 degree progress summary (one row per student)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS degree_status
                       (
                           student_id         TEXT PRIMARY KEY,
                           total_passed       TEXT,
                           total_required_min TEXT,
                           total_required_max TEXT,
                           incomplete_units   TEXT,
                           remaining_units    TEXT,
                           updated_at         TEXT
                       )
                       """)

        # Report 272 per-category progress rows (General / Basic / Specialized / ...)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS degree_categories
                       (
                           student_id   TEXT    NOT NULL,
                           category_ix  INTEGER NOT NULL,
                           category_name TEXT,
                           min_units    TEXT,
                           max_units    TEXT,
                           passed_units TEXT,
                           PRIMARY KEY (student_id, category_ix)
                       )
                       """)

    def save_student(self, student: 'Student'):
        """Save or update complete student record including semesters and courses."""

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables if they don't exist
        self._create_tables(cursor)

        # Save/update student info
        cursor.execute("""
            INSERT OR REPLACE INTO students (
                student_id, name, father_name, faculty, department, major,
                degree_level, study_type, enrollment_status, registration_permission,
                overall_gpa, total_units_passed, total_probation, consecutive_probation,
                special_probation, updated_at, image_b64
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            student.student_id,
            student.name,
            student.father_name,
            student.faculty,
            student.department,
            student.major,
            student.degree_level,
            student.study_type,
            student.enrollment_status,
            1 if student.registration_permission else 0,
            str(student.overall_gpa) if student.overall_gpa else None,
            str(student.total_units_passed),
            student.total_probation,
            student.consecutive_probation,
            student.special_probation,
            student.updated_at.isoformat(),
            student.image_b64
        ))

        # Save semesters (INSERT OR REPLACE handles updates automatically)
        for semester in student.semesters:
            cursor.execute("""
                INSERT OR REPLACE INTO semesters (
                    semester_id, semester_description, semester_gpa,
                    units_taken, units_passed, units_failed, units_dropped,
                    cumulative_gpa, cumulative_units_passed, semester_status,
                    semester_type, probation_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                semester.semester_id,
                semester.semester_description,
                str(semester.semester_gpa),
                str(semester.units_taken),
                str(semester.units_passed),
                str(semester.units_failed),
                str(semester.units_dropped),
                str(semester.cumulative_gpa),
                str(semester.cumulative_units_passed),
                semester.semester_status,
                semester.semester_type,
                semester.probation_status
            ))

            # Save courses
            for course in semester.courses:
                cursor.execute("""
                    INSERT OR REPLACE INTO courses (
                        semester_id, course_code, course_name,
                        course_units, course_type, grade_state, grade
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    semester.semester_id,
                    course.course_code,
                    course.course_name,
                    str(course.course_units),
                    course.course_type,
                    course.grade_state,
                    str(course.grade) if course.grade else None
                ))

        # Save Report 272 degree progress (summary + categories)
        self._save_degree_status(cursor, student)

        # Commit and close
        conn.commit()
        conn.close()
        logger.debug(f"✅ Successfully saved student {student.student_id} to {self.db_path}")

    def _save_degree_status(self, cursor, student: 'Student') -> None:
        """Persist Report 272 summary and category rows for a student."""
        cursor.execute("DELETE FROM degree_status WHERE student_id = ?", (student.student_id,))
        cursor.execute("DELETE FROM degree_categories WHERE student_id = ?", (student.student_id,))

        ds = getattr(student, 'degree_status', None)
        if ds is None:
            return

        cursor.execute("""
            INSERT INTO degree_status (
                student_id, total_passed, total_required_min, total_required_max,
                incomplete_units, remaining_units, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            student.student_id,
            str(ds.total_passed), str(ds.total_required_min), str(ds.total_required_max),
            str(ds.incomplete_units), str(ds.remaining_units),
            datetime.now().isoformat()
        ))

        for ix, cat in enumerate(ds.categories or []):
            cursor.execute("""
                INSERT INTO degree_categories (
                    student_id, category_ix, category_name, min_units, max_units, passed_units
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                student.student_id, ix, cat.category_name,
                str(cat.min_units), str(cat.max_units), str(cat.passed_units)
            ))

    def _load_degree_status(self, cursor, student_id: str) -> Optional['DegreeStatus']:
        """Load Report 272 summary + categories; returns None when never synced."""
        from app.scrapers.requests_scraper.models import DegreeStatus, CourseCategoryResult

        cursor.execute("""
            SELECT total_passed, total_required_min, total_required_max,
                   incomplete_units, remaining_units
            FROM degree_status WHERE student_id = ?
        """, (student_id,))
        row = cursor.fetchone()
        if not row:
            return None

        cursor.execute("""
            SELECT category_name, min_units, max_units, passed_units
            FROM degree_categories WHERE student_id = ? ORDER BY category_ix
        """, (student_id,))

        categories = [
            CourseCategoryResult(
                category_name=cat_row[0] or '',
                min_units=self._safe_decimal(cat_row[1]),
                max_units=self._safe_decimal(cat_row[2]),
                passed_units=self._safe_decimal(cat_row[3]),
            )
            for cat_row in cursor.fetchall()
        ]

        return DegreeStatus(
            total_passed=self._safe_decimal(row[0]),
            total_required_min=self._safe_decimal(row[1]),
            total_required_max=self._safe_decimal(row[2]),
            incomplete_units=self._safe_decimal(row[3]),
            remaining_units=self._safe_decimal(row[4]),
            categories=categories,
        )

    @staticmethod
    def _safe_decimal(value, default=None):
        """Tolerant Decimal conversion for stored TEXT numeric columns."""
        if value is None or value == '':
            return default
        try:
            return Decimal(str(value))
        except (ValueError, decimal.InvalidOperation):
            return default

    def load_student(self) -> Optional['Student']:
        """Load student record from database."""

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables if they don't exist
        self._create_tables(cursor)

        # Load student info
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (self.student_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # Helper function to safely convert to Decimal
        def safe_decimal(value, default=None):
            if value is None or value == '':
                return default
            try:
                return Decimal(str(value))
            except (ValueError, decimal.InvalidOperation):
                logger.warning(f"Warning: Could not convert '{value}' to Decimal, using default")
                return default

        # Parse student data
        student_data = {
            'student_id': row[0],
            'name': row[1],
            'father_name': row[2],
            'faculty': row[3],
            'department': row[4],
            'major': row[5],
            'degree_level': row[6],
            'study_type': row[7],
            'enrollment_status': row[8],
            'registration_permission': bool(row[9]),
            'overall_gpa': safe_decimal(row[10]),
            'total_units_passed': safe_decimal(row[11], Decimal('0.00')),
            'total_probation': row[12] if row[12] is not None else 0,
            'consecutive_probation': row[13] if row[13] is not None else 0,
            'special_probation': row[14] if row[14] is not None else 0,
            'updated_at': datetime.fromisoformat(row[15]) if row[15] else datetime.now(),
            'image_b64': row[16],
            'semesters': []
        }

        # Load semesters
        cursor.execute("""
                       SELECT semester_id,
                              semester_description,
                              semester_gpa,
                              units_taken,
                              units_passed,
                              units_failed,
                              units_dropped,
                              cumulative_gpa,
                              cumulative_units_passed,
                              semester_status,
                              semester_type,
                              probation_status
                       FROM semesters
                       ORDER BY semester_id
                       """)

        semesters = []
        for sem_row in cursor.fetchall():
            semester_id = sem_row[0]

            # Load courses for this semester
            cursor.execute("""
                           SELECT course_code,
                                  course_name,
                                  course_units,
                                  course_type,
                                  grade_state,
                                  grade
                           FROM courses
                           WHERE semester_id = ?
                           """, (semester_id,))

            courses = []
            for course_row in cursor.fetchall():
                course = CourseEnrollment(
                    course_code=course_row[0],
                    course_name=course_row[1],
                    course_units=safe_decimal(course_row[2], Decimal('0.00')),
                    course_type=course_row[3],
                    grade_state=course_row[4],
                    grade=safe_decimal(course_row[5])
                )
                courses.append(course)

            semester = SemesterRecord(
                semester_id=semester_id,
                semester_description=sem_row[1],
                semester_gpa=safe_decimal(sem_row[2], Decimal('0.00')),
                units_taken=safe_decimal(sem_row[3], Decimal('0.00')),
                units_passed=safe_decimal(sem_row[4], Decimal('0.00')),
                units_failed=safe_decimal(sem_row[5], Decimal('0.00')),
                units_dropped=safe_decimal(sem_row[6], Decimal('0.00')),
                cumulative_gpa=safe_decimal(sem_row[7], Decimal('0.00')),
                cumulative_units_passed=safe_decimal(sem_row[8], Decimal('0.00')),
                semester_status=sem_row[9],
                semester_type=sem_row[10],
                probation_status=sem_row[11],
                courses=courses
            )
            semesters.append(semester)

        student_data['semesters'] = semesters

        # Load Report 272 degree progress (None when never synced)
        student_data['degree_status'] = self._load_degree_status(cursor, self.student_id)

        # Close connection
        conn.close()

        return Student(**student_data)

    def student_exists(self) -> bool:
        """Check if student record exists in database"""

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables if they don't exist
        self._create_tables(cursor)

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (self.student_id,))
        count = cursor.fetchone()[0]

        # Close connection
        conn.close()

        return count > 0
