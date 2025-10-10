from dataclasses import dataclass, field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


@dataclass
class CourseEnrollment:
    """Individual course enrollment and grade"""
    course_code: str
    course_group: str
    course_name: str
    course_units: Decimal
    course_type: str
    grade_state: str
    grade: Optional[Decimal] = None
    pass_status: bool = False

    def __repr__(self) -> str:
        return f"CourseEnrollment({self.course_code}-{self.course_group}: {self.course_name}, {self.grade}, {self.course_units} units)"

@dataclass
class SemesterRecord:
    """Semester-level academic record"""
    semester_id: int
    semester_description: str
    semester_gpa: Decimal = field(default=Decimal('0.00'))
    units_taken: Decimal = field(default=Decimal('0.00'))
    units_passed: Decimal = field(default=Decimal('0.00'))
    cumulative_gpa: Decimal = field(default=Decimal('0.00'))
    cumulative_units_passed: Decimal = field(default=Decimal('0.00'))
    # probation_status: bool = False
    courses: List[CourseEnrollment] = field(default_factory=list)

    def __repr__(self) -> str:
        return (f"SemesterRecord(id={self.semester_id}, "
                f"desc='{self.semester_description}', "
                f"gpa={self.semester_gpa}, "
                f"units={self.units_passed}/{self.units_taken}, "
                f"courses={len(self.courses)})")

@dataclass
class Student:
    """Main student information model"""
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

    def __repr__(self) -> str:
        return (f"Student(id={self.student_id}, "
                f"name='{self.name}', "
                f"major='{self.major}', "
                f"gpa={self.overall_gpa}, "
                f"units={self.total_units_passed}, "
                f"semesters={len(self.semesters)})")