from dataclasses import dataclass, field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


@dataclass
class CourseEnrollment:
    """Individual course enrollment and grade"""
    course_code: str
    course_name: str
    course_units: Decimal
    course_type: str
    grade_state: str
    grade: Optional[Decimal] = None

    def __repr__(self) -> str:
        return f"CourseEnrollment({self.course_code}: {self.course_name}, {self.grade}, {self.course_units} units)"

@dataclass
class SemesterRecord:
    """Semester-level academic record"""
    semester_id: int
    semester_description: str
    semester_gpa: Decimal = field(default=Decimal('0.00'))
    units_taken: Decimal = field(default=Decimal('0.00'))
    units_passed: Decimal = field(default=Decimal('0.00'))
    units_failed: Decimal = field(default=Decimal('0.00'))
    units_dropped: Decimal = field(default=Decimal('0.00'))
    cumulative_gpa: Decimal = field(default=Decimal('0.00'))
    cumulative_units_passed: Decimal = field(default=Decimal('0.00'))
    semester_status: Optional[str] = None
    semester_type: Optional[str] = None
    probation_status: Optional[str] = None
    courses: List[CourseEnrollment] = field(default_factory=list)

    def __repr__(self) -> str:
        return (f"SemesterRecord(id={self.semester_id}, "
                f"desc='{self.semester_description}', "
                f"gpa={self.semester_gpa}, "
                f"units={self.units_passed}/{self.units_taken}, "
                f"courses={len(self.courses)})")

@dataclass
class CourseCategoryResult:
    """Progress for a specific course category (e.g., General, Basic, Specialized)"""
    category_name: str
    min_units: Decimal
    max_units: Decimal
    passed_units: Decimal

    def __repr__(self) -> str:
        return f"{self.category_name}: {self.passed_units}/{self.max_units}"


@dataclass
class DegreeStatus:
    """Overall degree progress summary"""
    total_passed: Decimal  # e.g., 85
    total_required_min: Decimal  # e.g., 140
    total_required_max: Decimal  # e.g., 142
    incomplete_units: Decimal  # e.g., 13
    remaining_units: Decimal  # e.g., 42
    categories: List[CourseCategoryResult] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"DegreeStatus(passed={self.total_passed}, remaining={self.remaining_units})"

@dataclass
class Student:
    """Main student information model"""
    # ... (existing fields) ...
    student_id: str
    name: str
    father_name: str
    faculty: str
    department: str
    major: str
    degree_level: str
    study_type: str
    enrollment_status: str
    registration_permission: bool
    overall_gpa: Optional[Decimal]
    total_units_passed: Decimal = field(default=Decimal('0.00'))
    total_probation: int = 0
    consecutive_probation: int = 0
    special_probation: int = 0
    semesters: List[SemesterRecord] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now)
    image_b64: Optional[str] = None

    degree_status: Optional[DegreeStatus] = None

    def __repr__(self) -> str:
        return (f"Student(id={self.student_id}, "
                f"name='{self.name}', "
                f"major='{self.major}', "
                f"gpa={self.overall_gpa}, "
                f"units={self.total_units_passed}, "
                f"semesters={len(self.semesters)})")