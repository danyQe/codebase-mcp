"""
Response helper functions for API endpoints
"""

from typing import Union, Dict, Any
from datetime import datetime
from fastapi.responses import JSONResponse

from schemas.responses import APIResponse


def create_success_response(result: Union[str, Dict[str, Any]]) -> APIResponse:
    """
    Create successful API response

    Args:
        result: Response data (string or dict)

    Returns:
        APIResponse object with success=True
    """
    return APIResponse(result=result, success=True)


def create_error_response(message: str, status_code: int = 400) -> JSONResponse:
    """
    Create error response

    Args:
        message: Error message
        status_code: HTTP status code (default: 400)

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "success": False,
            "timestamp": datetime.now().isoformat(),
        },
    )
