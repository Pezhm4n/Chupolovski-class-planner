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
    ME: str = "/api/auth/me"
    UPDATE_PROFILE: str = "/api/auth/profile"
    FORGOT_PASSWORD: str = "/api/auth/forgot-password"
    RESET_PASSWORD: str = "/api/auth/reset-password"
    SET_PASSWORD: str = "/api/auth/set-password"


@dataclass(frozen=True)
class ScheduleRoutes:
    """Saved Schedules Endpoints."""

    BASE: str = "/api/schedules"
    BY_ID: str = "/api/schedules/{schedule_id}"


@dataclass(frozen=True)
class ProfessorRoutes:
    """Professor Reviews and Ratings Endpoints."""

    STATS: str = "/api/professor-reviews/stats"
    MY_REVIEW: str = "/api/professor-reviews/my-review"
    SUBMIT_REVIEW: str = "/api/professor-reviews"


@dataclass(frozen=True)
class ProxyRoutes:
    """Scraper Proxy, Captcha and Golestan Student Endpoints."""

    COURSES_ALL: str = "/scraper-proxy/api/courses/all"
    STUDENT_PROFILE: str = "/api/student/profile"
    TRANSCRIPT_SYNC: str = "/api/transcript"
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
