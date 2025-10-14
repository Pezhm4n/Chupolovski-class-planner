import sqlite3
import os
from pathlib import Path
from typing import Optional
from decimal import Decimal
from datetime import datetime
from app.scrapers.requests_scraper.models import Student, SemesterRecord, CourseEnrollment


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

        # Commit and close
        conn.commit()
        conn.close()
        print(f"✅ Successfully saved student {student.student_id} to {self.db_path}")

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
            'overall_gpa': Decimal(row[10]) if row[10] else None,
            'total_units_passed': Decimal(row[11]),
            'total_probation': row[12],
            'consecutive_probation': row[13],
            'special_probation': row[14],
            'updated_at': datetime.fromisoformat(row[15]),
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
                    course_units=Decimal(course_row[2]),
                    course_type=course_row[3],
                    grade_state=course_row[4],
                    grade=Decimal(course_row[5]) if course_row[5] else None
                )
                courses.append(course)

            semester = SemesterRecord(
                semester_id=semester_id,
                semester_description=sem_row[1],
                semester_gpa=Decimal(sem_row[2]),
                units_taken=Decimal(sem_row[3]),
                units_passed=Decimal(sem_row[4]),
                units_failed=Decimal(sem_row[5]),
                units_dropped=Decimal(sem_row[6]),
                cumulative_gpa=Decimal(sem_row[7]),
                cumulative_units_passed=Decimal(sem_row[8]),
                semester_status=sem_row[9],
                semester_type=sem_row[10],
                probation_status=sem_row[11],
                courses=courses
            )
            semesters.append(semester)

        student_data['semesters'] = semesters

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
