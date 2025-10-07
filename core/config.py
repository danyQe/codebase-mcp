"""
Application configuration and settings
"""

import os
import sys
from pathlib import Path
from typing import Optional


class Settings:
    """Application settings and configuration"""

    def __init__(self):
        # Server configuration
        self.API_TITLE = "Codebase Manager API"
        self.API_DESCRIPTION = "REST API for codebase management operations"
        self.API_VERSION = "1.0.0"

        # Get working directory from command line or default
        self.WORKING_DIR = (
            os.path.abspath(sys.argv[1])
            if len(sys.argv) > 1
            else "C:/Users/HP/Desktop/FORGRIDE/CODE/MVP"
        )

        # HTTP Configuration
        self.HTTP_TIMEOUT = 30.0

        # CORS Configuration
        self.CORS_ORIGINS = ["*"]
        self.CORS_CREDENTIALS = True
        self.CORS_METHODS = ["*"]
        self.CORS_HEADERS = ["*"]

    def update_working_directory(self, new_dir: str) -> None:
        """Update working directory"""
        self.WORKING_DIR = new_dir


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance"""
    return settings
