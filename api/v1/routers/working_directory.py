"""
Working directory management endpoints
Handles working directory validation, changes, and reinitialization
"""

import os
from pathlib import Path
from fastapi import APIRouter

from core.config import get_settings
from core.lifespan import reinitialize_services
from core import get_services_status
from schemas.requests import WorkingDirectoryRequest
from utils import (
    create_success_response,
    create_error_response,
    create_detailed_error_response,
)

router = APIRouter(prefix="/working-directory", tags=["working-directory"])


@router.get("")
async def get_working_directory():
    """Get current working directory and service status"""
    try:
        settings = get_settings()
        services = get_services_status()

        return create_success_response(
            {
                "working_directory": settings.WORKING_DIR,
                "services_status": services,
                "directory_exists": os.path.exists(settings.WORKING_DIR),
                "directory_readable": os.access(settings.WORKING_DIR, os.R_OK),
                "directory_writable": os.access(settings.WORKING_DIR, os.W_OK),
            }
        )
    except Exception as e:
        return create_error_response(
            f"Failed to get working directory info: {str(e)}", 500
        )


@router.put("")
async def change_working_directory(request: WorkingDirectoryRequest):
    """Change working directory and reinitialize all services"""
    try:
        settings = get_settings()
        new_dir = request.working_directory.strip()

        # Validate new directory
        if not new_dir:
            return create_detailed_error_response(
                "Working directory cannot be empty",
                400,
                "EmptyDirectory",
                {"provided_path": new_dir},
                "WorkingDirectoryManager",
                "validation",
                settings.WORKING_DIR,
            )

        # Convert to absolute path
        try:
            new_dir_path = Path(new_dir).resolve()
            new_dir = str(new_dir_path)
        except Exception as e:
            return create_detailed_error_response(
                f"Invalid directory path: {new_dir}",
                400,
                "InvalidPath",
                {"provided_path": new_dir, "path_error": str(e)},
                "WorkingDirectoryManager",
                "path_resolution",
                settings.WORKING_DIR,
            )

        # Check if directory exists
        if not new_dir_path.exists():
            return create_detailed_error_response(
                f"Directory does not exist: {new_dir}",
                404,
                "DirectoryNotFound",
                {
                    "requested_path": new_dir,
                    "resolved_path": str(new_dir_path),
                    "suggestion": "Create the directory first or check the path",
                },
                "WorkingDirectoryManager",
                "existence_check",
                settings.WORKING_DIR,
            )

        # Check if it's actually a directory
        if not new_dir_path.is_dir():
            return create_detailed_error_response(
                f"Path is not a directory: {new_dir}",
                400,
                "NotADirectory",
                {
                    "requested_path": new_dir,
                    "path_type": "file" if new_dir_path.is_file() else "unknown",
                },
                "WorkingDirectoryManager",
                "directory_check",
                settings.WORKING_DIR,
            )

        # Check permissions
        if not os.access(new_dir, os.R_OK):
            return create_detailed_error_response(
                f"Directory is not readable: {new_dir}",
                403,
                "PermissionDenied",
                {"requested_path": new_dir, "required_permission": "read"},
                "WorkingDirectoryManager",
                "permission_check",
                settings.WORKING_DIR,
            )

        if not os.access(new_dir, os.W_OK):
            return create_detailed_error_response(
                f"Directory is not writable: {new_dir}",
                403,
                "PermissionDenied",
                {
                    "requested_path": new_dir,
                    "required_permission": "write",
                    "suggestion": "Ensure you have write permissions to this directory",
                },
                "WorkingDirectoryManager",
                "permission_check",
                settings.WORKING_DIR,
            )

        # Same directory check
        if new_dir == settings.WORKING_DIR:
            return create_success_response(
                {
                    "message": "Already using the specified working directory",
                    "working_directory": settings.WORKING_DIR,
                    "changed": False,
                }
            )

        old_working_dir = settings.WORKING_DIR

        try:
            # Reinitialize all services
            await reinitialize_services(new_dir)

            return create_success_response(
                {
                    "message": "Successfully changed working directory",
                    "old_working_directory": old_working_dir,
                    "new_working_directory": settings.WORKING_DIR,
                    "changed": True,
                    "services_reinitialized": get_services_status(),
                }
            )

        except Exception as reinit_error:
            # Rollback working directory on failure
            settings.update_working_directory(old_working_dir)

            return create_detailed_error_response(
                f"Failed to reinitialize services with new directory: {str(reinit_error)}",
                500,
                "ServiceReinitializationFailed",
                {
                    "attempted_directory": new_dir,
                    "rolled_back_to": old_working_dir,
                    "reinit_error": str(reinit_error),
                    "error_type": type(reinit_error).__name__,
                },
                "WorkingDirectoryManager",
                "service_reinitialization",
                old_working_dir,
            )

    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Unexpected error changing working directory: {str(e)}",
            500,
            "UnexpectedError",
            {
                "requested_directory": request.working_directory,
                "current_directory": settings.WORKING_DIR,
                "exception_type": type(e).__name__,
            },
            "WorkingDirectoryManager",
            "change_directory",
            settings.WORKING_DIR,
        )


@router.post("/validate")
async def validate_working_directory(request: WorkingDirectoryRequest):
    """Validate a directory path without changing to it"""
    try:
        settings = get_settings()
        new_dir = request.working_directory.strip()

        # Validation results
        validation = {
            "path": new_dir,
            "is_valid": False,
            "exists": False,
            "is_directory": False,
            "readable": False,
            "writable": False,
            "resolved_path": None,
            "errors": [],
            "warnings": [],
        }

        if not new_dir:
            validation["errors"].append("Directory path cannot be empty")
            return create_success_response(validation)

        try:
            new_dir_path = Path(new_dir).resolve()
            validation["resolved_path"] = str(new_dir_path)
        except Exception as e:
            validation["errors"].append(f"Invalid path: {str(e)}")
            return create_success_response(validation)

        validation["exists"] = new_dir_path.exists()
        if not validation["exists"]:
            validation["errors"].append("Directory does not exist")
            return create_success_response(validation)

        validation["is_directory"] = new_dir_path.is_dir()
        if not validation["is_directory"]:
            validation["errors"].append("Path is not a directory")
            return create_success_response(validation)

        validation["readable"] = os.access(str(new_dir_path), os.R_OK)
        if not validation["readable"]:
            validation["errors"].append("Directory is not readable")

        validation["writable"] = os.access(str(new_dir_path), os.W_OK)
        if not validation["writable"]:
            validation["errors"].append("Directory is not writable")

        # Check if same as current
        if str(new_dir_path) == settings.WORKING_DIR:
            validation["warnings"].append(
                "This is already the current working directory"
            )

        validation["is_valid"] = (
            validation["exists"]
            and validation["is_directory"]
            and validation["readable"]
            and validation["writable"]
        )

        return create_success_response(validation)

    except Exception as e:
        return create_error_response(f"Failed to validate directory: {str(e)}", 500)
