"""
Application lifespan management
Handles initialization and shutdown of services
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.config import get_settings
from core.dependencies import (
    set_search_engine,
    set_write_pipeline,
    set_edit_pipeline,
    set_memory_manager,
    set_git_manager,
    set_project_manager,
    set_directory_lister,
)
from semantic_search import SemanticSearchEngine
from semantic_search.directory_lister import DirectoryLister
from code_tools import WritePipeline, EditPipeline
from code_tools.git_manager import GitManager
from memory_system import MemoryManager
from project_structure.project_manager import ProjectStructureManager

logger = logging.getLogger(__name__)


async def initialize_services() -> None:
    """Initialize all application services"""
    settings = get_settings()
    working_dir = settings.WORKING_DIR

    logger.info(f"FastAPI Server starting - Working directory: {working_dir}")

    try:
        # Initialize semantic search engine
        search_engine = SemanticSearchEngine(working_dir)
        await search_engine.initialize()
        set_search_engine(search_engine)
        logger.info("✅ Semantic search engine initialized")

        # Initialize write pipeline with search engine
        write_pipeline = WritePipeline(search_engine)
        set_write_pipeline(write_pipeline)
        logger.info("✅ Write pipeline initialized")

        # Initialize edit pipeline with write pipeline
        edit_pipeline = EditPipeline(write_pipeline)
        set_edit_pipeline(edit_pipeline)
        logger.info("✅ Edit pipeline initialized")

        # Initialize memory manager
        memory_manager = MemoryManager(working_dir + "/.data")
        await memory_manager.initialize()
        set_memory_manager(memory_manager)
        logger.info("✅ Memory manager initialized")

        # Initialize git manager
        try:
            logger.info(f"🔍 Initializing GitManager with WORKING_DIR: {working_dir}")
            git_manager = GitManager(working_dir)
            result = await git_manager.initialize_codebase_repo()
            set_git_manager(git_manager)
            logger.info("✅ Git manager initialized")
        except Exception as e:
            logger.warning(f"⚠️ Git manager initialization failed: {e}")
            set_git_manager(None)

        # Initialize project manager
        project_manager = ProjectStructureManager(working_dir)
        set_project_manager(project_manager)
        logger.info("✅ Project structure manager initialized")

        # Initialize directory lister
        directory_lister = DirectoryLister(working_dir)
        set_directory_lister(directory_lister)
        logger.info("✅ Directory lister initialized")

        logger.info("🚀 All services initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise


async def shutdown_services() -> None:
    """Shutdown all application services"""
    logger.info("🛑 FastAPI Server shutting down...")
    # Add any cleanup logic here if needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager

    Handles initialization on startup and cleanup on shutdown
    """
    # Startup
    await initialize_services()

    yield

    # Shutdown
    await shutdown_services()


async def reinitialize_services(new_working_dir: str) -> None:
    """
    Reinitialize all services with new working directory

    Args:
        new_working_dir: New working directory path

    Raises:
        Exception: If reinitialization fails
    """
    from core.dependencies import (
        get_search_engine,
        get_memory_manager,
    )

    logger.info(f"🔄 Reinitializing services with working directory: {new_working_dir}")

    # Store old instances for cleanup
    old_search_engine = get_search_engine()
    old_memory_manager = get_memory_manager()

    try:
        # Update settings
        settings = get_settings()
        settings.update_working_directory(new_working_dir)

        # Initialize all services with new directory
        await initialize_services()

        logger.info("🎉 All services reinitialized successfully")

        # Cleanup old instances if needed
        if old_search_engine:
            try:
                # Add any cleanup logic here if needed
                pass
            except Exception as e:
                logger.warning(f"Warning during old search engine cleanup: {e}")

        if old_memory_manager:
            try:
                # Add any cleanup logic here if needed
                pass
            except Exception as e:
                logger.warning(f"Warning during old memory manager cleanup: {e}")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to reinitialize services: {e}")

        # Try to restore old settings if possible
        if old_search_engine:
            set_search_engine(old_search_engine)
        if old_memory_manager:
            set_memory_manager(old_memory_manager)

        raise
