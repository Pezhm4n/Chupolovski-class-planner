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
class TranscriptSyncStatusModel:
    """Golestan transcript sync status DTO.

    Mirrors the backend contract of `POST /api/transcript/sync` and
    `GET /api/transcript` (see golestan-web server/index.ts):
    statuses: done | queued | syncing | too_recent | needs_login | ok | error.
    """

    status: str
    message: str = ""
    last_synced_at: Optional[str] = None
    is_syncing: bool = False
    sync_progress: int = 0
    sync_step: Optional[str] = None
    minutes_left: Optional[int] = None
    job_id: Optional[int] = None
    mode: Optional[str] = None
    student: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ApiErrorResponseModel:
    """Standard server error response payload DTO."""

    message: str
    code: str = "SERVER_ERROR"
    failed_attempts: Optional[int] = None
    locked_until: Optional[int] = None
    retry_after: Optional[int] = None
