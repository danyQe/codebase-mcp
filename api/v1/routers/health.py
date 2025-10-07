"""
Health and status endpoints for system monitoring
"""

import os
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from core import get_settings, get_services_status
from core.dependencies import (
    get_search_engine,
    get_write_pipeline,
    get_edit_pipeline,
    get_memory_manager,
    get_git_manager,
)
from utils import create_success_response

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    settings = get_settings()
    services = get_services_status()

    return create_success_response(
        {
            "status": "healthy",
            "working_directory": settings.WORKING_DIR,
            "components": services,
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.get("/status")
async def get_status():
    """Get detailed server status"""
    settings = get_settings()

    status_info = {
        "server": "FastAPI Codebase Manager",
        "version": "1.0.0",
        "working_directory": settings.WORKING_DIR,
        "features": [
            "semantic_search",
            "intelligent_write",
            "ai_assisted_edit",
            "memory_system",
            "git_operations",
            "file_management",
        ],
    }

    # Add component statistics
    search_engine = get_search_engine()
    if search_engine:
        status_info["search_stats"] = search_engine.get_stats()

    write_pipeline = get_write_pipeline()
    if write_pipeline:
        status_info["write_pipeline_stats"] = write_pipeline.get_stats()

    edit_pipeline = get_edit_pipeline()
    if edit_pipeline:
        status_info["edit_pipeline_stats"] = edit_pipeline.get_stats()

    memory_manager = get_memory_manager()
    if memory_manager:
        status_info["memory_stats"] = memory_manager.get_stats().dict()

    git_manager = get_git_manager()
    if git_manager:
        status_info["git_stats"] = git_manager.get_stats()

    return create_success_response(status_info)


@router.get("/")
async def read_index():
    """Serve the new component-based dashboard HTML"""
    return FileResponse("templates/index.html")


# Static file routes for templates
@router.get("/templates/components/{file_path:path}")
async def serve_component(file_path: str):
    """Serve HTML component files"""
    component_path = Path("templates/components") / file_path
    if component_path.exists() and component_path.suffix == ".html":
        return FileResponse(component_path)
    return {"error": "Component not found"}


@router.get("/static/{file_type}/{file_path:path}")
async def serve_static(file_type: str, file_path: str):
    """Serve static JS/CSS files"""
    static_path = Path(f"templates/static/{file_type}") / file_path
    if static_path.exists():
        return FileResponse(static_path)
    return {"error": "Static file not found"}


@router.get("/working-directory")
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
        from utils import create_error_response

        return create_error_response(
            f"Failed to get working directory info: {str(e)}", 500
        )
