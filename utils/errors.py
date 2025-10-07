"""
Error handling and detailed error response utilities
"""

from typing import Optional, Dict, Any
from datetime import datetime
from fastapi.responses import JSONResponse


def create_detailed_error_response(
    message: str,
    status_code: int = 400,
    error_type: str = "ValidationError",
    details: Optional[Dict[str, Any]] = None,
    component: str = "Unknown",
    operation: str = "Unknown",
    working_dir: Optional[str] = None,
) -> JSONResponse:
    """
    Create detailed error response that provides actionable debugging info

    Args:
        message: Error message
        status_code: HTTP status code
        error_type: Type of error (ValidationError, FileNotFound, etc.)
        details: Additional error details
        component: Component where error occurred
        operation: Operation being performed
        working_dir: Current working directory

    Returns:
        JSONResponse with comprehensive error information
    """
    error_details = details or {}
    error_details.update(
        {
            "component": component,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
            "server_version": "1.0.0",
        }
    )

    if working_dir:
        error_details["working_directory"] = working_dir

    return JSONResponse(
        status_code=status_code,
        content={
            "error": message,
            "error_type": error_type,
            "success": False,
            "details": error_details,
            "debug_help": _get_debug_help(error_type, component, operation),
        },
    )


def _get_debug_help(error_type: str, component: str, operation: str) -> str:
    """
    Provide debugging hints based on error context

    Args:
        error_type: Type of error
        component: Component name
        operation: Operation name

    Returns:
        Debug help message string
    """
    debug_hints = {
        "GitManager": "Check if .codebase directory exists and is properly initialized. Verify file paths are within working directory.",
        "EditPipeline": "Verify target file exists and is readable. Check if Gemini API key is set. Ensure file has proper syntax.",
        "WritePipeline": "Verify file path permissions and syntax. Check if dependencies can be resolved.",
        "MemorySystem": "Check if memory database is initialized and accessible.",
        "SearchEngine": "Verify search index is built and up to date. Check file patterns and search queries.",
        "FileOperations": "Ensure file paths are valid and within working directory. Check file permissions.",
    }

    error_hints = {
        "FileNotFound": "Verify file path is correct and file exists within the working directory.",
        "InitializationError": "Check if all required components are properly initialized during startup.",
        "PermissionDenied": "Ensure you have read/write permissions for the specified path.",
        "ValidationError": "Check that all required parameters are provided with correct types.",
    }

    # Component-specific hint
    if component in debug_hints:
        return debug_hints[component]

    # Error type-specific hint
    if error_type in error_hints:
        return error_hints[error_type]

    # Default hint
    return (
        "Check server logs for more details. Verify all required services are running."
    )


def add_system_log(
    level: str,
    component: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    log_list: Optional[list] = None,
) -> None:
    """
    Add a log entry to the system logs

    Args:
        level: Log level (debug, info, warning, error, critical)
        component: Component name
        message: Log message
        details: Additional log details
        log_list: List to append logs to (optional, for testing)
    """
    from schemas.common import SystemLog, LogLevel

    log_entry = SystemLog(
        timestamp=datetime.now(),
        level=LogLevel(level),
        component=component,
        message=message,
        details=details or {},
    )

    if log_list is not None:
        log_list.append(log_entry)

        # Keep only last 1000 logs
        if len(log_list) > 1000:
            log_list.pop(0)
