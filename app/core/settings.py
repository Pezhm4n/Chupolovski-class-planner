"""
Settings module for the Golestoon Class Planner application.
Centralizes all configuration settings including API URLs and database paths.
"""

import os
from pathlib import Path

# Production backend — same default as NetworkConfig (app/core/network/config.py).
DEFAULT_PRODUCTION_BASE_URL = "https://api.example.com"


class Settings:
    """Application settings class."""

    def __init__(self):
        # Cloud backend base URL. Resolution order:
        #   1. GOLESTOON_API_BASE_URL env (dev override)
        #   2. API_URL env (legacy override)
        #   3. Production default
        api_url = (
            os.getenv('GOLESTOON_API_BASE_URL')
            or os.getenv('API_URL')
            or DEFAULT_PRODUCTION_BASE_URL
        )
        self.API_URL = api_url.rstrip('/')
        self.DATABASE_PATH = Path(os.getenv('DATABASE_PATH', 'courses.db'))
        self.DATABASE_PATH = self.DATABASE_PATH if self.DATABASE_PATH.is_absolute() else Path(__file__).parent.parent / self.DATABASE_PATH

# Create a global settings instance
settings = Settings()
