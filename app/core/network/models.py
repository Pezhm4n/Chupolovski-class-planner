# -*- coding: utf-8 -*-
"""
Golestoon Core Network Data Transfer Objects (DTO Models).

This module defines immutable dataclass structures (`frozen=True`) representing
request and response payloads for Golestoon REST API communication.

Architecture Layer: Layer 1 (Network Leaf Infrastructure)
Dependencies: Python Standard Library ONLY (`dataclasses`, `datetime`, `typing`).
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass(frozen=True)
class UserMetadataModel:
    """User Metadata profile representation."""

    full_name: Optional[str] = None
    google_id: Optional[str] = None
    avatar: Optional[str] = None
    password_set: bool = True
    auth_methods: List[str] = field(default_factory=list)
    has_contributed: bool = False
    review_count: int = 0


@dataclass(frozen=True)
class UserModel:
    """Authenticated user account DTO."""

    id: str
    email: str
    user_metadata: UserMetadataModel


@dataclass(frozen=True)
class AuthResponseModel:
    """Response DTO for login and signup API endpoints."""

    token: str
    user: UserModel


@dataclass(frozen=True)
class ScheduleModel:
    """Cloud saved schedule configuration DTO."""

    id: str
    name: str
    courses: List[Dict[str, Any]]
    created_at: int


@dataclass(frozen=True)
class ProfessorStatsModel:
    """Aggregated professor review statistics DTO."""

    department_name: str
    instructor_name: str
    teaching_score: float = 0.0
    ethics_score: float = 0.0
    assignments_score: float = 0.0
    grading_score: float = 0.0
    overall_score: float = 0.0
    exam_difficulty_score: float = 0.0
    exam_source_score: float = 0.0
    interaction_score: float = 0.0
    attendance_sensitivity: str = "normal"
    time_sensitivity: str = "normal"
    total_reviews: int = 0
    total_voters: int = 0
    telegram_has_data: bool = False
    telegram_overall_avg: Optional[float] = None
    telegram_effective_voters: int = 0


@dataclass(frozen=True)
class ProfessorReviewModel:
    """Single pseudonymous professor review DTO."""

    reviewer_hash: str
    department_name: str
    instructor_name: str
    teaching_score: float
    assignments_score: float
    grading_score: float
    exam_difficulty_score: float
    attendance_sensitivity: str
    updated_at: str


@dataclass(frozen=True)
class TranscriptSyncStatusModel:
    """Golestan transcript sync status DTO."""

    status: str
    message: str
    last_synced_at: Optional[str] = None
    is_syncing: bool = False
    job_id: Optional[int] = None
    student: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ApiErrorResponseModel:
    """Standard server error response payload DTO."""

    message: str
    code: str = "SERVER_ERROR"
    failed_attempts: Optional[int] = None
    locked_until: Optional[int] = None
    retry_after: Optional[int] = None
