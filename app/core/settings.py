"""
Settings module for the Golestoon Class Planner application.
Centralizes all configuration settings including API URLs and database paths.
"""

import os
from pathlib import Path

class Settings:
    """Application settings class."""
    
    def __init__(self):
        # Load environment variables
        api_url = os.getenv('API_URL', '')
        # Use default only if API_URL is not set in environment
        if not api_url:
            # If API_URL is empty, set it to None to skip API calls
            self.API_URL = None
        else:
            self.API_URL = api_url
        self.DATABASE_PATH = Path(os.getenv('DATABASE_PATH', 'courses.db'))
        self.DATABASE_PATH = self.DATABASE_PATH if self.DATABASE_PATH.is_absolute() else Path(__file__).parent.parent / self.DATABASE_PATH

# Create a global settings instance
settings = Settings()