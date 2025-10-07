"""
Response models for API endpoints
"""

from typing import Union, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """Standard API response model"""

    result: Union[str, Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = True
