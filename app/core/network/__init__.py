# -*- coding: utf-8 -*-
"""
Golestoon Core Network Package.

This package provides the core leaf network infrastructure, exception hierarchy,
endpoint route registries, DTO data models, sanitized network logging, central configuration,
HTTP session management, and modular domain sub-clients.

Architecture Layer: Layer 1 & Layer 2 (Network Infrastructure & Clients)
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
    TranscriptSyncStatusModel,
    ApiErrorResponseModel,
)
from .clients.professor_client import ProfessorStats, ProfessorReview
from .logger import SensitiveDataRedactor, get_network_logger
from .config import NetworkConfig
from .session import NetworkSession, SessionFactory
from .clients import (
    BaseClient,
    AuthClient,
    ScheduleClient,
    ProfessorClient,
    TranscriptClient,
    ProxyClient,
)

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
    "TranscriptSyncStatusModel",
    "ApiErrorResponseModel",
    "ProfessorStats",
    "ProfessorReview",
    # Logger
    "SensitiveDataRedactor",
    "get_network_logger",
    # Config & Session
    "NetworkConfig",
    "NetworkSession",
    "SessionFactory",
    # Sub-Clients
    "BaseClient",
    "AuthClient",
    "ScheduleClient",
    "ProfessorClient",
    "TranscriptClient",
    "ProxyClient",
]
