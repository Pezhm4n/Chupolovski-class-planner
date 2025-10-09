"""Storage module for saving course data to database."""
import os
from pathlib import Path
from typing import Dict
from app.data.database import CourseDatabase


def _is_first_run() -> bool:
    """Check if this is the first time the database is being initialized."""
    # Create a marker file to track initialization
    app_root = Path(__file__).resolve().parent
    marker_file = app_root / '.db_initialized'

    if marker_file.exists():
        return False
    else:
        # Create marker file
        marker_file.touch()
        return True


def store_courses_to_db(available_courses: Dict = None, unavailable_courses: Dict = None,
                        force_reinit: bool = False) -> int:
    """
    Store parsed course data to database.

    Args:
        available_courses: Dictionary of available courses from parser
        unavailable_courses: Dictionary of unavailable courses from parser
        force_reinit: If True, drop and recreate tables regardless of first run status

    Returns:
        Total number of courses stored
    """
    db = CourseDatabase()

    # Only drop tables on first run or if forced
    if force_reinit or _is_first_run():
        print("🔄 First run detected - initializing database...")
        db.drop_all_tables()
        db.create_tables()
        print("✓ Database initialized")
    else:
        # Just ensure tables exist (won't drop if they already exist)
        db.create_tables()

    total_courses = 0

    # Store available courses
    if available_courses:
        count = db.upsert_courses(available_courses, is_available=True)
        print(f"✓ Stored {count} available courses")
        total_courses += count

    # Store unavailable courses
    if unavailable_courses:
        count = db.upsert_courses(unavailable_courses, is_available=False)
        print(f"✓ Stored {count} unavailable courses")
        total_courses += count

    print(f"✓ Total courses in database: {total_courses}")
    return total_courses


def initialize_database(force: bool = False):
    """
    Initialize database by dropping and recreating all tables.

    Args:
        force: If True, reinitialize even if not first run
    """
    if not force and not _is_first_run():
        print("⚠ Database already initialized. Use force=True to reinitialize.")
        return

    db = CourseDatabase()
    db.drop_all_tables()
    db.create_tables()
    print("✓ Database initialized")


def reset_first_run_marker():
    """Delete the first run marker file to trigger reinitialization on next run."""
    app_root = Path(__file__).resolve().parent.parent
    marker_file = app_root / '.db_initialized'
    if marker_file.exists():
        marker_file.unlink()
        print("✓ First run marker reset")
