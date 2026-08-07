# -*- coding: utf-8 -*-
"""
Golestoon Modular Network Sub-Clients Package.

This package provides domain-specific REST clients (`AuthClient`, `ScheduleClient`,
`ProfessorClient`, `TranscriptClient`, `ProxyClient`) inheriting from `BaseClient`.

Architecture Layer: Layer 2 (Modular Network Sub-Clients)
"""

from .base_client import BaseClient
from .auth_client import AuthClient
from .schedule_client import ScheduleClient
from .professor_client import ProfessorClient
from .transcript_client import TranscriptClient
from .proxy_client import ProxyClient

__all__ = [
    "BaseClient",
    "AuthClient",
    "ScheduleClient",
    "ProfessorClient",
    "TranscriptClient",
    "ProxyClient",
]
