# -*- coding: utf-8 -*-
"""
Golestoon Core Network API Routes Registry.

This module defines immutable dataclasses containing all relative REST API endpoint
paths matching the Golestoon backend specification (`golestan-web`).

Architecture Layer: Layer 1 (Network Leaf Infrastructure)
Dependencies: Python Standard Library ONLY (`dataclasses`).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthRoutes:
    """Authentication and User Account Endpoints."""

    LOGIN: str = "/api/auth/login"
    SIGNUP: str = "/api/auth/signup"
    UPDATE_PROFILE: str = "/api/auth/profile"          # PUT (JWT)
    FORGOT_PASSWORD: str = "/api/auth/forgot-password"  # POST
    RESET_PASSWORD: str = "/api/auth/reset-password"    # POST
    SET_PASSWORD: str = "/api/auth/set-password"        # POST (JWT)
    # NOTE: the backend intentionally has no GET /api/auth/me — the user
    # model rides inline in login/signup responses, and tokens are validated
    # implicitly via auth-protected endpoints (see AuthClient.validate_token).


@dataclass(frozen=True)
class ScheduleRoutes:
    """Saved Schedules Endpoints."""

    BASE: str = "/api/schedules"
    BY_ID: str = "/api/schedules/{schedule_id}"


@dataclass(frozen=True)
class ProfessorRoutes:
    """Professor Reviews and Ratings Endpoints (golestan-web contracts)."""

    STATS: str = "/api/professor-reviews/stats"                 # GET ?department&instructor → {stats}
    MY_REVIEW: str = "/api/professor-reviews/my-review"         # GET/DELETE ?department&instructor
    SUBMIT_REVIEW: str = "/api/professor-reviews"               # POST {department_name, instructor_name, *_score}
    DEPARTMENTS: str = "/api/professor-reviews/departments"     # GET → {departments: []}
    SUMMARY: str = "/api/professor-reviews/summary"             # GET (auth) → {departmentCount, instructorCount, userReviewCount, hasContributed}
    POPULAR_BY_VIEWS: str = "/api/professor-reviews/popular-by-views"
    POPULAR_BY_SCORE: str = "/api/professor-reviews/popular-by-score"
    POPULAR_BY_VOTERS: str = "/api/professor-reviews/popular-by-voters"
    TRACK_VIEW: str = "/api/professor-reviews/track-view"       # POST
    INSTRUCTOR_EXISTS: str = "/api/instructors/exists"          # GET ?department_name&instructor_name
    SUGGEST_INSTRUCTOR: str = "/api/instructors/suggest"        # POST (auth)
    APPROVED_INSTRUCTORS: str = "/api/instructors/approved"     # GET ?department → {instructors: []}


@dataclass(frozen=True)
class ProxyRoutes:
    """Scraper Proxy, Captcha and Golestan Student Endpoints."""

    COURSES_ALL: str = "/scraper-proxy/api/courses/all"
    STUDENT_PROFILE: str = "/api/student/profile"
    # GET — sync metadata only (lastSyncedAt / isSyncing / syncProgress / syncStep).
    TRANSCRIPT_STATUS: str = "/api/transcript"
    # POST — trigger a transcript sync job (body: {mode, wait, force} +
    # x-username / x-password headers; response carries the full student
    # record when wait=true and status == 'done').
    TRANSCRIPT_SYNC: str = "/api/transcript/sync"
    HEALTH_CHECK: str = "/health"


@dataclass(frozen=True)
class ApiRoutes:
    """
    Master Registry for all Golestoon REST API Endpoint Groups.

    Usage:
        ApiRoutes.AUTH.LOGIN -> "/api/auth/login"
        ApiRoutes.SCHEDULES.BASE -> "/api/schedules"
        ApiRoutes.SCHEDULES.BY_ID.format(schedule_id="123") -> "/api/schedules/123"
    """

    AUTH: AuthRoutes = AuthRoutes()
    SCHEDULES: ScheduleRoutes = ScheduleRoutes()
    PROFESSORS: ProfessorRoutes = ProfessorRoutes()
    PROXY: ProxyRoutes = ProxyRoutes()
