"""
Dependency injection for services
Manages global service instances and provides dependency injection
"""

from typing import Optional
from semantic_search import SemanticSearchEngine
from semantic_search.directory_lister import DirectoryLister
from code_tools import WritePipeline, EditPipeline
from code_tools.git_manager import GitManager
from memory_system import MemoryManager
from project_structure.project_manager import ProjectStructureManager


# Global service instances
_search_engine: Optional[SemanticSearchEngine] = None
_write_pipeline: Optional[WritePipeline] = None
_edit_pipeline: Optional[EditPipeline] = None
_memory_manager: Optional[MemoryManager] = None
_git_manager: Optional[GitManager] = None
_project_manager: Optional[ProjectStructureManager] = None
_directory_lister: Optional[DirectoryLister] = None


def set_search_engine(engine: SemanticSearchEngine) -> None:
    """Set search engine instance"""
    global _search_engine
    _search_engine = engine


def get_search_engine() -> Optional[SemanticSearchEngine]:
    """Get search engine instance"""
    return _search_engine


def set_write_pipeline(pipeline: WritePipeline) -> None:
    """Set write pipeline instance"""
    global _write_pipeline
    _write_pipeline = pipeline


def get_write_pipeline() -> Optional[WritePipeline]:
    """Get write pipeline instance"""
    return _write_pipeline


def set_edit_pipeline(pipeline: EditPipeline) -> None:
    """Set edit pipeline instance"""
    global _edit_pipeline
    _edit_pipeline = pipeline


def get_edit_pipeline() -> Optional[EditPipeline]:
    """Get edit pipeline instance"""
    return _edit_pipeline


def set_memory_manager(manager: MemoryManager) -> None:
    """Set memory manager instance"""
    global _memory_manager
    _memory_manager = manager


def get_memory_manager() -> Optional[MemoryManager]:
    """Get memory manager instance"""
    return _memory_manager


def set_git_manager(manager: GitManager) -> None:
    """Set git manager instance"""
    global _git_manager
    _git_manager = manager


def get_git_manager() -> Optional[GitManager]:
    """Get git manager instance"""
    return _git_manager


def set_project_manager(manager: ProjectStructureManager) -> None:
    """Set project manager instance"""
    global _project_manager
    _project_manager = manager


def get_project_manager() -> Optional[ProjectStructureManager]:
    """Get project manager instance"""
    return _project_manager


def set_directory_lister(lister: DirectoryLister) -> None:
    """Set directory lister instance"""
    global _directory_lister
    _directory_lister = lister


def get_directory_lister() -> Optional[DirectoryLister]:
    """Get directory lister instance"""
    return _directory_lister


def get_services_status() -> dict:
    """Get status of all services"""
    return {
        "search_engine": _search_engine is not None,
        "write_pipeline": _write_pipeline is not None,
        "edit_pipeline": _edit_pipeline is not None,
        "memory_manager": _memory_manager is not None,
        "git_manager": _git_manager is not None,
        "project_manager": _project_manager is not None,
        "directory_lister": _directory_lister is not None,
    }
