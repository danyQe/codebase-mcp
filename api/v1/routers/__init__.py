"""
API v1 Routers
Exports all router instances for registration in main app
"""

from api.v1.routers.health import router as health_router
from api.v1.routers.search import router as search_router
from api.v1.routers.files import router as files_router
from api.v1.routers.git import router1 as git_router
from api.v1.routers.git import router2 as session_router
from api.v1.routers.memory import router as memory_router
from api.v1.routers.project import router as project_router
from api.v1.routers.logs import router as logs_router
from api.v1.routers.working_directory import router as working_directory_router
from api.v1.routers.static_files import router as static_files_router
from api.v1.routers.directory import router as directory_router

# List of all routers to register
all_routers = [
    static_files_router,  # Must be first to serve root /
    health_router,
    search_router,
    files_router,
    git_router,
    session_router,
    memory_router,
    project_router,
    directory_router,
    logs_router,
    working_directory_router,
]

__all__ = [
    "all_routers",
    "health_router",
    "search_router",
    "files_router",
    "git_router",
    "memory_router",
    "project_router",
    "logs_router",
    "working_directory_router",
    "static_files_router",
    "directory_router",
]
