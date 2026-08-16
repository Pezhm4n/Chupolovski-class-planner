# -*- coding: utf-8 -*-
"""
Golestoon API JSON → Domain Model Converters.

This module converts camelCase JSON payloads returned by the Golestan backend
(`POST /api/transcript/sync` → `student` object, shaped by
`server/golestan/golestanStudent.ts`) into the desktop app's snake_case
dataclass models (`app/scrapers/requests_scraper/models.py`).

Architecture Layer: Layer 2 (Network ↔ Domain Boundary)
Dependencies: Standard library + scraper dataclass models only.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from app.scrapers.requests_scraper.models import (
    Student,
    SemesterRecord,
    CourseEnrollment,
    DegreeStatus,
    CourseCategoryResult,
)


def _to_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Coerce a JSON number/string into Decimal, tolerating None/''."""
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    """Coerce a JSON number/string into int, tolerating None/''."""
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default


def _to_float(value: Any) -> Optional[float]:
    """Coerce a JSON number/string into float, returning None when absent."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_updated_at(value: Any) -> datetime:
    """Parse an ISO-8601 timestamp ('2026-08-16T10:00:00.000Z' or local)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed
        except ValueError:
            pass
    return datetime.now()


def course_from_api(data: Dict[str, Any]) -> CourseEnrollment:
    """Convert a server CourseEnrollment JSON node into the desktop model."""
    return CourseEnrollment(
        course_code=str(data.get("courseCode", "") or ""),
        course_name=str(data.get("courseName", "") or ""),
        course_units=_to_decimal(data.get("courseUnits"), Decimal("0.00")),
        course_type=str(data.get("courseType", "") or ""),
        grade_state=str(data.get("gradeState", "") or ""),
        grade=_to_decimal(data.get("grade")),
    )


def semester_from_api(data: Dict[str, Any]) -> SemesterRecord:
    """Convert a server SemesterRecord JSON node into the desktop model."""
    courses_raw = data.get("courses") or []
    return SemesterRecord(
        semester_id=_to_int(data.get("semesterId")),
        semester_description=str(data.get("semesterDescription", "") or ""),
        semester_gpa=_to_decimal(data.get("semesterGpa"), Decimal("0.00")),
        units_taken=_to_decimal(data.get("unitsTaken"), Decimal("0.00")),
        units_passed=_to_decimal(data.get("unitsPassed"), Decimal("0.00")),
        units_failed=_to_decimal(data.get("unitsFailed"), Decimal("0.00")),
        units_dropped=_to_decimal(data.get("unitsDropped"), Decimal("0.00")),
        cumulative_gpa=_to_decimal(data.get("cumulativeGpa"), Decimal("0.00")),
        cumulative_units_passed=_to_decimal(
            data.get("cumulativeUnitsPassed"), Decimal("0.00")
        ),
        semester_status=data.get("semesterStatus"),
        semester_type=data.get("semesterType"),
        probation_status=data.get("probationStatus"),
        courses=[course_from_api(c) for c in courses_raw if isinstance(c, dict)],
    )


def degree_status_from_api(data: Dict[str, Any]) -> DegreeStatus:
    """Convert the Report 272 `degreeStatus` JSON node into the desktop model."""
    categories_raw = data.get("categories") or []
    categories: List[CourseCategoryResult] = [
        CourseCategoryResult(
            category_name=str(cat.get("categoryName", "") or ""),
            min_units=_to_decimal(cat.get("minUnits"), Decimal("0")),
            max_units=_to_decimal(cat.get("maxUnits"), Decimal("0")),
            passed_units=_to_decimal(cat.get("passedUnits"), Decimal("0")),
        )
        for cat in categories_raw
        if isinstance(cat, dict)
    ]
    return DegreeStatus(
        total_passed=_to_decimal(data.get("totalPassed"), Decimal("0")),
        total_required_min=_to_decimal(data.get("totalRequiredMin"), Decimal("0")),
        total_required_max=_to_decimal(data.get("totalRequiredMax"), Decimal("0")),
        incomplete_units=_to_decimal(data.get("incompleteUnits"), Decimal("0")),
        remaining_units=_to_decimal(data.get("remainingUnits"), Decimal("0")),
        categories=categories,
    )


def student_from_api(data: Dict[str, Any]) -> Student:
    """Convert the full server Student JSON record into the desktop model."""
    semesters_raw = data.get("semesters") or []
    degree_raw = data.get("degreeStatus")

    overall_gpa = _to_decimal(data.get("overallGpa"))
    registration_permission = bool(data.get("registrationPermission", False))

    return Student(
        student_id=str(data.get("studentId", "") or ""),
        name=str(data.get("name", "") or ""),
        father_name=str(data.get("fatherName", "") or ""),
        faculty=str(data.get("faculty", "") or ""),
        department=str(data.get("department", "") or ""),
        major=str(data.get("major", "") or ""),
        degree_level=str(data.get("degreeLevel", "") or ""),
        study_type=str(data.get("studyType", "") or ""),
        enrollment_status=str(data.get("enrollmentStatus", "") or ""),
        registration_permission=registration_permission,
        overall_gpa=overall_gpa,
        total_units_passed=_to_decimal(
            data.get("totalUnitsPassed"), Decimal("0.00")
        ),
        total_probation=_to_int(data.get("totalProbation")),
        consecutive_probation=_to_int(data.get("consecutiveProbation")),
        special_probation=_to_int(data.get("specialProbation")),
        semesters=[
            semester_from_api(s) for s in semesters_raw if isinstance(s, dict)
        ],
        updated_at=_parse_updated_at(data.get("updatedAt")),
        image_b64=data.get("imageB64"),
        degree_status=(
            degree_status_from_api(degree_raw)
            if isinstance(degree_raw, dict)
            else None
        ),
    )
