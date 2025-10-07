from pathlib import Path
from fastapi import APIRouter, Query, HTTPException

from core import  get_directory_lister, get_git_manager
from core.config import get_settings
from utils import (
    create_success_response,
    create_error_response,
    create_detailed_error_response,
    validate_file_path,
)
router =APIRouter(prefix="/directory")

@router.get("/list")
async def list_directory(
    directory_path: str = Query(
        ".", description="Directory path relative to working directory"
    ),
    max_depth: int = Query(2, description="Maximum depth to traverse", ge=0, le=10),
    include_hidden: bool = Query(
        False, description="Include hidden files and directories"
    ),
    show_metadata: bool = Query(
        True, description="Include file metadata (size, lines, etc.)"
    ),
    respect_gitignore: bool = Query(
        True, description="Filter based on .gitignore patterns"
    ),
    files_only: bool = Query(False, description="Show only files, not directories"),
    dirs_only: bool = Query(False, description="Show only directories, not files"),
):
    """List directory contents with configurable depth and filtering"""
    try:
        directory_lister = get_directory_lister()
        settings = get_settings()

        if not directory_lister:
            return create_error_response("Directory lister not initialized", 500)

        # Validate directory path
        if directory_path != ".":
            await validate_file_path(directory_path, settings.WORKING_DIR)

        result = directory_lister.list_directory(
            directory_path=directory_path,
            max_depth=max_depth,
            include_hidden=include_hidden,
            show_metadata=show_metadata,
            respect_gitignore=respect_gitignore,
            files_only=files_only,
            dirs_only=dirs_only,
        )

        if "error" in result:
            return create_error_response(result["error"], 400)

        return create_success_response(result)

    except HTTPException:
        raise
    except Exception as e:
        return create_error_response(f"Directory listing failed: {str(e)}", 500)


@router.get("/tree/{directory_path:path}")
async def get_directory_tree(
    directory_path: str,
    max_depth: int = Query(
        3, description="Maximum depth for tree display", ge=1, le=10
    ),
):
    """Get directory tree structure for a specific path"""
    try:
        directory_lister = get_directory_lister()
        settings = get_settings()

        if not directory_lister:
            return create_detailed_error_response(
                "Directory lister not initialized",
                500,
                "ServiceNotAvailable",
                {"service": "DirectoryLister"},
                "DirectoryLister",
                "initialization",
                settings.WORKING_DIR,
            )

        # Clean up path
        if directory_path.endswith("/") and directory_path != "/":
            directory_path = directory_path.rstrip("/")

        if not directory_path or directory_path == "":
            directory_path = "."

        try:
            await validate_file_path(directory_path, settings.WORKING_DIR)
        except HTTPException as e:
            return create_detailed_error_response(
                f"Invalid directory path: {directory_path}",
                e.status_code,
                "DirectoryPathError",
                {"requested_path": directory_path, "validation_error": e.detail},
                "DirectoryLister",
                "path_validation",
                settings.WORKING_DIR,
            )

        result = directory_lister.list_directory(
            directory_path=directory_path,
            max_depth=max_depth,
            include_hidden=False,
            show_metadata=True,
            respect_gitignore=True,
        )

        if "error" in result:
            return create_detailed_error_response(
                result["error"],
                400,
                "DirectoryListingError",
                {
                    "directory_path": directory_path,
                    "max_depth": max_depth,
                    "lister_error": result["error"],
                },
                "DirectoryLister",
                "list_directory",
                settings.WORKING_DIR,
            )

        # Format as tree structure
        tree_lines = []
        for item in result["items"]:
            prefix = item.get("tree_prefix", "")
            name = item["name"]

            if item.get("is_directory", False):
                tree_lines.append(f"{prefix}{name}/  # directory")
            else:
                size_info = (
                    f" [{directory_lister.format_size(item.get('size', 0))}]"
                    if item.get("size")
                    else ""
                )
                line_info = (
                    f" ({item.get('line_count', 0)} lines)"
                    if item.get("line_count")
                    else ""
                )
                tree_lines.append(f"{prefix}{name}{size_info}{line_info}  # file")

        return create_success_response(
            {
                "directory": result["directory"],
                "tree": "\n".join(tree_lines),
                "summary": result["summary"],
                "max_depth": max_depth,
                "total_items": len(result["items"]),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Failed to generate directory tree: {str(e)}",
            500,
            "DirectoryTreeError",
            {
                "directory_path": directory_path,
                "max_depth": max_depth,
                "exception_type": type(e).__name__,
            },
            "DirectoryLister",
            "tree_generation",
            settings.WORKING_DIR,
        )


@router.get("/tree/enhanced/{directory_path:path}")
async def get_enhanced_directory_tree(
    directory_path: str,
    max_depth: int = Query(3, description="Maximum depth", ge=1, le=10),
    include_hidden: bool = Query(False, description="Include hidden files"),
    show_sizes: bool = Query(True, description="Show file sizes"),
    show_git_status: bool = Query(True, description="Show git status indicators"),
):
    """Get enhanced directory tree with git status and file metadata"""
    try:
        directory_lister = get_directory_lister()
        git_manager = get_git_manager()
        settings = get_settings()

        if not directory_lister:
            return create_error_response("Directory lister not initialized", 500)

        # Validate path
        if directory_path != ".":
            await validate_file_path(directory_path, settings.WORKING_DIR)

        # Get directory listing
        result = directory_lister.list_directory(
            directory_path=directory_path,
            max_depth=max_depth,
            include_hidden=include_hidden,
            show_metadata=show_sizes,
            respect_gitignore=True,
        )

        if "error" in result:
            return create_error_response(result["error"], 400)

        # Enhanced tree formatting
        tree_lines = []
        git_status = {}

        # Get git status if requested
        if show_git_status and git_manager:
            try:
                status_result = await git_manager.get_status()
                if status_result.success:
                    status_data = status_result.data.get("status", {})

                    for file in status_data.get("modified_files", []):
                        git_status[file] = "M"
                    for file in status_data.get("untracked_files", []):
                        git_status[file] = "?"
                    for file in status_data.get("staged_files", []):
                        git_status[file] = "A"
            except:
                pass

        # Build enhanced tree
        for item in result["items"]:
            prefix = item.get("tree_prefix", "")
            name = item["name"]
            file_path = item.get("path", name)

            git_indicator = ""
            if show_git_status:
                status = git_status.get(file_path, "")
                if status:
                    git_indicator = f"[{status}] "

            if item.get("is_directory", False):
                file_count = item.get("file_count", "")
                count_info = f" ({file_count} items)" if file_count else ""
                tree_lines.append(f"{prefix}📁 {git_indicator}{name}/{count_info}")
            else:
                size_info = ""
                if show_sizes and item.get("size") is not None:
                    size = item["size"]
                    if size > 1024 * 1024:
                        size_info = f" [{size // (1024*1024)}MB]"
                    elif size > 1024:
                        size_info = f" [{size // 1024}KB]"
                    else:
                        size_info = f" [{size}B]"

                    if item.get("line_count"):
                        size_info += f" ({item['line_count']} lines)"

                ext = Path(name).suffix.lower()
                type_indicators = {
                    ".py": "🐍",
                    ".js": "🟨",
                    ".ts": "🔷",
                    ".html": "🌐",
                    ".css": "🎨",
                    ".json": "📋",
                    ".md": "📝",
                    ".txt": "📄",
                    ".yml": "⚙️",
                    ".yaml": "⚙️",
                }

                icon = type_indicators.get(ext, "📄")
                tree_lines.append(f"{prefix}{icon} {git_indicator}{name}{size_info}")

        enhanced_tree = "\n".join(tree_lines)

        return create_success_response(
            {
                "directory": result["directory"],
                "tree": enhanced_tree,
                "summary": result["summary"],
                "max_depth": max_depth,
                "total_items": len(result["items"]),
                "git_status_shown": show_git_status and bool(git_status),
                "options": {
                    "include_hidden": include_hidden,
                    "show_sizes": show_sizes,
                    "show_git_status": show_git_status,
                },
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        return create_error_response(
            f"Failed to generate directory tree: {str(e)}", 500
        )
