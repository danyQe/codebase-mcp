"""
Project and directory operation endpoints
Handles project context, directory listing, and tree views
"""

from fastapi import APIRouter, Query

from core import get_project_manager
from utils import (
    create_success_response,
    create_error_response
)

router = APIRouter(prefix="/project", tags=["project"])


@router.get("/context")
async def get_project_context(
    operation: str = Query(
        "info", description="Context operation: info, structure, dependencies"
    ),
    max_depth: int = Query(5, description="Maximum depth for structure"),
    include_hidden: bool = Query(False, description="Include hidden files"),
):
    """Get enhanced project context information"""
    try:
        project_manager = get_project_manager()
        if not project_manager:
            return create_error_response("Project manager not initialized", 500)

        if operation == "info":
            info = project_manager.get_project_info()

            result = {
                "operation": "info",
                "working_directory": info["working_directory"],
                "summary": {
                    "total_files": info["total_files"],
                    "total_size": project_manager.format_size(info["total_size"]),
                    "total_lines": f"{info['total_lines']:,}",
                },
                "project_files": info["project_files"],
                "file_types": info["top_file_types"],
                "detailed_info": info,
            }

            return create_success_response(result)

        elif operation == "structure":
            structure = project_manager.get_project_structure(max_depth, include_hidden)
            info = project_manager.get_project_info()

            result = {
                "operation": "structure",
                "max_depth": max_depth,
                "include_hidden": include_hidden,
                "summary": {
                    "total_files": info["total_files"],
                    "total_size": project_manager.format_size(info["total_size"]),
                    "total_lines": f"{info['total_lines']:,}",
                },
                "tree_structure": structure,
            }

            return create_success_response(result)

        elif operation == "dependencies":
            deps = project_manager.get_dependencies_info()

            result = {
                "operation": "dependencies",
                "dependency_files": list(deps.keys()),
                "dependencies": deps,
            }

            return create_success_response(result)

        else:
            return create_error_response(
                f"Unknown operation: {operation}. Valid: info, structure, dependencies",
                400,
            )

    except Exception as e:
        return create_error_response(f"Failed to get project context: {str(e)}", 500)

