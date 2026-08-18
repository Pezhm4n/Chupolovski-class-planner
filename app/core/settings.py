"""
Settings module for the Golestoon Class Planner application.
Centralizes all configuration settings including API URLs and database paths.
"""

import os
from pathlib import Path

class Settings:
    """Application settings class."""

    def __init__(self):
        # Cloud backend base URL. Read from environment variables (GOLESTOON_API_BASE_URL / API_URL).
        # When empty or not set, API_URL is None (standalone / local mode).
        api_url = (
            os.getenv('GOLESTOON_API_BASE_URL')
            or os.getenv('API_URL')
        )
        self.API_URL = api_url.strip().rstrip('/') if api_url and api_url.strip() else None
        self.DATABASE_PATH = Path(os.getenv('DATABASE_PATH', 'courses.db'))
        self.DATABASE_PATH = self.DATABASE_PATH if self.DATABASE_PATH.is_absolute() else Path(__file__).parent.parent / self.DATABASE_PATH

# Create a global settings instance
settings = Settings()
