"""
Common types and enums shared across schemas
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class LogLevel(str, Enum):
    """System log levels"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SystemLog(BaseModel):
    """System log entry model"""

    timestamp: datetime
    level: LogLevel
    component: str
    message: str
    details: Optional[Dict[str, Any]] = None
