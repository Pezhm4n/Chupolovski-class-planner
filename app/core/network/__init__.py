# -*- coding: utf-8 -*-
"""
Golestoon Core Network Package.

This package provides the core leaf network infrastructure, exception hierarchy,
endpoint route registries, DTO data models, and sanitized network logging.

Architecture Layer: Layer 1 (Network Leaf Infrastructure)
"""

from .exceptions import (
    GolestoonNetworkError,
    ConnectionFailedError,
    TimeoutError,
    OfflineError,
    GolestanProxyError,
    ApiHttpError,
    ValidationApiError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from .routes import ApiRoutes, AuthRoutes, ScheduleRoutes, ProfessorRoutes, ProxyRoutes
from .models import (
    UserMetadataModel,
    UserModel,
    AuthResponseModel,
    ScheduleModel,
    ProfessorStatsModel,
    ProfessorReviewModel,
    TranscriptSyncStatusModel,
    ApiErrorResponseModel,
)
from .logger import SensitiveDataRedactor, get_network_logger

__all__ = [
    # Exceptions
    "GolestoonNetworkError",
    "ConnectionFailedError",
    "TimeoutError",
    "OfflineError",
    "GolestanProxyError",
    "ApiHttpError",
    "ValidationApiError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    # Routes
    "ApiRoutes",
    "AuthRoutes",
    "ScheduleRoutes",
    "ProfessorRoutes",
    "ProxyRoutes",
    # Models
    "UserMetadataModel",
    "UserModel",
    "AuthResponseModel",
    "ScheduleModel",
    "ProfessorStatsModel",
    "ProfessorReviewModel",
    "TranscriptSyncStatusModel",
    "ApiErrorResponseModel",
    # Logger
    "SensitiveDataRedactor",
    "get_network_logger",
]
