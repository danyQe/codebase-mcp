#ruff: noqa
#type:ignore
"""
Git operations and session management endpoints
Handles git commands, branch operations, and AI session management
"""

from typing import Optional
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException

from core import get_git_manager
from core.config import get_settings
from schemas.requests import GitOperationRequest, SessionRequest
from utils import (
    create_success_response,
    create_error_response,
    create_detailed_error_response,
    validate_file_path,
)

router1 = APIRouter(prefix="/git", tags=["git"])
router2=APIRouter(prefix="/session",tags=["session"])

@router1.post("")
async def git_operations(request: GitOperationRequest):
    """Handle git operations with comprehensive error reporting"""
    try:
        git_manager = get_git_manager()
        settings = get_settings()

        if not git_manager:
            return create_detailed_error_response(
                "Git manager not initialized - service startup may have failed",
                500,
                "ServiceNotAvailable",
                {"initialization_status": "failed"},
                "GitManager",
                "initialization",
                settings.WORKING_DIR,
            )

        operation = request.operation.lower()

        # Pre-flight checks
        if not git_manager.is_git_repo:
            init_result = await git_manager.initialize_codebase_repo()
            if not init_result.success:
                return create_detailed_error_response(
                    f"Cannot initialize .codebase repository: {init_result.error}",
                    400,
                    "GitInitializationError",
                    {
                        "git_dir": str(git_manager.git_dir),
                        "init_output": init_result.output,
                        "suggested_fix": "Ensure working directory has write permissions and is a valid project directory",
                    },
                    "GitManager",
                    "repository_init",
                    settings.WORKING_DIR,
                )

        # Execute operation
        result = None
        try:
            if operation == "status":
                result = await git_manager.get_status()
            elif operation == "branches":
                result = await git_manager.get_branches()
            elif operation == "log":
                result = await git_manager.get_log(
                    max_commits=request.max_results or 10, file_path=request.file_path
                )
            elif operation == "diff":
                result = await git_manager.get_diff(
                    file_path=request.file_path, cached=request.cached or False
                )
            elif operation == "add":
                if not request.files and not request.file_path:
                    return create_detailed_error_response(
                        "Files or file_path required for add operation",
                        400,
                        "MissingParameter",
                        {
                            "required_fields": ["files", "file_path"],
                            "provided_request": request.dict(),
                        },
                        "GitManager",
                        "add",
                        settings.WORKING_DIR,
                    )

                files_to_add = [
                    f for f in (request.files or [request.file_path]) if f is not None
                ]
                result = await git_manager.add_files(files_to_add)

            elif operation == "commit":
                if not request.message:
                    return create_detailed_error_response(
                        "Commit message required for commit operation",
                        400,
                        "MissingParameter",
                        {
                            "required_field": "message",
                            "provided_request": request.dict(),
                        },
                        "GitManager",
                        "commit",
                        settings.WORKING_DIR,
                    )

                result = await git_manager.commit(
                    message=request.message, files=request.files
                )

            elif operation == "blame":
                if not request.file_path:
                    return create_detailed_error_response(
                        "File path required for blame operation",
                        400,
                        "MissingParameter",
                        {"required_field": "file_path"},
                        "GitManager",
                        "blame",
                        settings.WORKING_DIR,
                    )

                # Validate file exists
                try:
                    await validate_file_path(request.file_path, settings.WORKING_DIR)
                except HTTPException as e:
                    return create_detailed_error_response(
                        f"Invalid file path for blame: {request.file_path}",
                        400,
                        "FilePathError",
                        {"file_path": request.file_path, "validation_error": str(e)},
                        "GitManager",
                        "blame",
                        settings.WORKING_DIR,
                    )

                result = await git_manager.get_file_blame(request.file_path)
            else:
                return create_detailed_error_response(
                    f"Unsupported git operation: {operation}",
                    400,
                    "UnsupportedOperation",
                    {
                        "requested_operation": operation,
                        "supported_operations": [
                            "status",
                            "branches",
                            "log",
                            "diff",
                            "add",
                            "commit",
                            "blame",
                        ],
                    },
                    "GitManager",
                    operation,
                    settings.WORKING_DIR,
                )

        except Exception as op_error:
            return create_detailed_error_response(
                f"Git operation {operation} failed with exception: {str(op_error)}",
                500,
                "GitOperationException",
                {
                    "operation": operation,
                    "exception_type": type(op_error).__name__,
                    "exception_details": str(op_error),
                    "git_dir": str(git_manager.git_dir),
                },
                "GitManager",
                operation,
                settings.WORKING_DIR,
            )

        # Handle operation result
        if result and result.success:
            response_data = {
                "operation": operation,
                "output": result.output,
                "data": result.data,
                "git_dir": str(git_manager.git_dir),
                "working_dir": settings.WORKING_DIR,
            }
            return create_success_response(response_data)
        elif result:
            return create_detailed_error_response(
                f"Git {operation} failed: {result.error or 'Unknown error'}",
                400 if result.return_code not in [128, 129] else 500,
                "GitCommandFailed",
                {
                    "operation": operation,
                    "return_code": result.return_code,
                    "git_output": result.output,
                    "git_error": result.error,
                    "git_dir": str(git_manager.git_dir),
                    "command_suggestion": f"Try running: cd {settings.WORKING_DIR} && git {operation}",
                },
                "GitManager",
                operation,
                settings.WORKING_DIR,
            )
        else:
            return create_detailed_error_response(
                f"Git operation {operation} returned no result",
                500,
                "NoResult",
                {"operation": operation},
                "GitManager",
                operation,
                settings.WORKING_DIR,
            )

    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Unexpected error in git operations: {str(e)}",
            500,
            "UnexpectedError",
            {
                "operation": request.operation,
                "exception_type": type(e).__name__,
                "full_traceback": str(e),
            },
            "GitManager",
            request.operation,
            settings.WORKING_DIR,
        )


# Convenience endpoints
@router1.get("/status")
async def git_status():
    """Get git repository status"""
    return await git_operations(GitOperationRequest(operation="status"))


@router1.get("/branches")
async def git_branches():
    """Get all git branches"""
    return await git_operations(GitOperationRequest(operation="branches"))


@router1.get("/log")
async def git_log(
    max_commits: int = Query(10, description="Maximum number of commits"),
    file_path: Optional[str] = Query(
        None, description="File path for file-specific log"
    ),
):
    """Get git commit history"""
    return await git_operations(
        GitOperationRequest(
            operation="log", max_results=max_commits, file_path=file_path
        )
    )


@router1.post("/tree")
async def get_git_tree_visualization():
    """Get comprehensive git repository tree view"""
    try:
        git_manager = get_git_manager()
        if not git_manager:
            return create_error_response("Git manager not initialized", 500)

        # Get status and branches for tree view
        status_result = await git_manager.get_status()
        branches_result = await git_manager.get_branches()

        output = []
        output.append("🌳 Git Repository Tree View")
        output.append("=" * 40)

        if status_result.success:
            status_data = status_result.data.get("status", {})
            current_branch = status_data.get("current_branch", "unknown")
            output.append(f"📍 Current Branch: {current_branch}")

            # Show modified files
            modified = status_data.get("modified_files", [])
            if modified:
                output.append(f"📝 Modified Files ({len(modified)}):")
                for file in modified[:10]:
                    output.append(f"   ├── {file}")
                if len(modified) > 10:
                    output.append(f"   └── ... and {len(modified) - 10} more")

            # Show untracked files
            untracked = status_data.get("untracked_files", [])
            if untracked:
                output.append(f"❓ Untracked Files ({len(untracked)}):")
                for file in untracked[:5]:
                    output.append(f"   ├── {file}")
                if len(untracked) > 5:
                    output.append(f"   └── ... and {len(untracked) - 5} more")

        if branches_result.success:
            branches = branches_result.data.get("branches", [])
            output.append(f"🌿 Branches ({len(branches)}):")

            for branch in branches[:10]:
                is_current = branch.get("is_current", False)
                is_session = branch.get("name", "").startswith(
                    ("ai-session-", "session-")
                )

                prefix = "├── "
                if is_current:
                    prefix += "👉 "
                if is_session:
                    prefix += "🤖 "

                output.append(f"   {prefix}{branch.get('name', 'unknown')}")

            if len(branches) > 10:
                output.append(f"   └── ... and {len(branches) - 10} more branches")

        tree_output = "\n".join(output)

        return create_success_response(
            {
                "tree_view": tree_output,
                "current_branch": (
                    status_data.get("current_branch") if status_result.success else None
                ),
                "total_branches": len(branches) if branches_result.success else 0,
                "modified_files": len(modified) if status_result.success else 0,
                "untracked_files": len(untracked) if status_result.success else 0,
            }
        )

    except Exception as e:
        return create_error_response(f"Failed to generate git tree: {str(e)}", 500)


# Session management endpoints
@router2.post("")
async def session_operations(request: SessionRequest):
    """Handle session branch operations"""
    try:
        git_manager = get_git_manager()
        settings = get_settings()

        if not git_manager:
            return create_detailed_error_response(
                "Git manager not initialized - service startup may have failed",
                500,
                "ServiceNotAvailable",
                {"initialization_status": "failed"},
                "GitManager",
                "initialization",
                settings.WORKING_DIR,
            )

        # Pre-flight checks
        if not git_manager.is_git_repo:
            init_result = await git_manager.initialize_codebase_repo()
            if not init_result.success:
                return create_detailed_error_response(
                    f"Cannot initialize .codebase repository: {init_result.error}",
                    400,
                    "GitInitializationError",
                    {
                        "git_dir": str(git_manager.git_dir),
                        "init_output": init_result.output,
                        "suggested_fix": "Ensure working directory has write permissions",
                    },
                    "GitManager",
                    "repository_init",
                    settings.WORKING_DIR,
                )

        operation = request.operation.lower()

        if operation == "start":
            # Generate session name if not provided
            if not request.session_name:
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                request.session_name = f"ai-session-{timestamp}"

            result = await git_manager.create_branch(
                request.session_name, switch_to=True
            )

            if result.success:
                return create_success_response(
                    {
                        "operation": "start",
                        "session_name": request.session_name,
                        "message": f"Started new session: {request.session_name}",
                        "output": result.output,
                    }
                )
            else:
                return create_error_response(
                    f"Failed to start session: {result.error}", 400
                )

        elif operation == "end":
            current_branch_result = await git_manager.get_current_branch()
            if not current_branch_result.success:
                return create_error_response("Could not determine current branch", 400)

            current_branch = current_branch_result.data.get("current_branch")

            # Switch back to master
            checkout_result = await git_manager.checkout_branch("master")
            if not checkout_result.success:
                return create_error_response(
                    f"Failed to switch to master: {checkout_result.error}", 400
                )

            response_data = {
                "operation": "end",
                "session_name": current_branch,
                "message": f"Ended session: {current_branch}, switched to master",
            }

            # Auto-merge if requested
            if request.auto_merge:
                merge_msg = request.message or f"Merge session: {current_branch}"
                merge_result = await git_manager.merge_branch(current_branch, merge_msg)
                if merge_result.success:
                    response_data["merged"] = True
                    response_data["message"] += ", merged to master"
                else:
                    response_data["merge_error"] = merge_result.error

            return create_success_response(response_data)

        elif operation == "switch":
            if not request.session_name:
                return create_error_response(
                    "Session name required for switch operation", 400
                )

            result = await git_manager.checkout_branch(request.session_name)

            if result.success:
                return create_success_response(
                    {
                        "operation": "switch",
                        "session_name": request.session_name,
                        "message": f"Switched to session: {request.session_name}",
                        "output": result.output,
                    }
                )
            else:
                return create_error_response(
                    f"Failed to switch to session: {result.error}", 400
                )

        elif operation == "list":
            result = await git_manager.list_session_branches()

            if result.success:
                return create_success_response(
                    {"operation": "list", "output": result.output, "data": result.data}
                )
            else:
                return create_error_response(
                    f"Failed to list sessions: {result.error}", 500
                )

        elif operation == "merge":
            if not request.session_name:
                return create_error_response(
                    "Session name required for merge operation", 400
                )

            merge_msg = request.message or f"Merge session: {request.session_name}"
            result = await git_manager.merge_branch(request.session_name, merge_msg)

            if result.success:
                return create_success_response(
                    {
                        "operation": "merge",
                        "session_name": request.session_name,
                        "message": f"Merged session {request.session_name}",
                        "output": result.output,
                    }
                )
            else:
                return create_error_response(
                    f"Failed to merge session: {result.error}", 400
                )

        elif operation == "delete":
            if not request.session_name:
                return create_detailed_error_response(
                    "Must provide branch or session name to delete the branch",
                    400,
                    "MissingParameter",
                    {"required_field": "session_name"},
                    "GitManager",
                    "delete",
                    settings.WORKING_DIR,
                )

            result = await git_manager.get_current_branch()
            if result.data.get("current_branch") == request.session_name:
                switch_result = await git_manager.checkout_branch("master")
                print(
                    f"Switched to master branch to delete the session. Result: {switch_result.output}"
                )

            result = await git_manager.delete_branch(request.session_name, force=True)
            if result.success:
                return create_success_response(
                    {
                        "operation": "delete",
                        "session_name": request.session_name,
                        "message": f"Branch deleted successfully: {request.session_name}",
                        "output": result.output,
                    }
                )
            else:
                return create_error_response(
                    f"Failed to delete session: {result.error}", 400
                )

        else:
            return create_error_response(
                f"Unsupported session operation: {operation}", 400
            )

    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Session operation failed: {str(e)}",
            500,
            "SessionOperationError",
            {"operation": request.operation, "exception_type": type(e).__name__},
            "SessionManager",
            request.operation,
            settings.WORKING_DIR,
        )


@router2.get("/current")
async def get_current_session():
    """Get current session information"""
    try:
        git_manager = get_git_manager()
        if not git_manager:
            return create_error_response("Git manager not initialized", 500)

        result = await git_manager.get_current_branch()

        if result.success:
            current_branch = result.data.get("current_branch")
            is_session = current_branch.startswith(
                "ai-session-"
            ) or current_branch.startswith("session-")

            return create_success_response(
                {
                    "current_branch": current_branch,
                    "is_session_branch": is_session,
                    "session_name": current_branch if is_session else None,
                }
            )
        else:
            return create_error_response(
                f"Failed to get current branch: {result.error}", 500
            )

    except Exception as e:
        return create_error_response(f"Failed to get current session: {str(e)}", 500)


@router2.post("/auto-commit")
async def auto_commit_change(
    file_path: str = Query(..., description="File that was changed"),
    operation: str = Query(..., description="Operation performed (write/edit)"),
    purpose: Optional[str] = Query(None, description="Purpose of the change"),
    quality_score: Optional[float] = Query(None, description="Quality score"),
):
    """Auto-commit a change made by AI"""
    try:
        git_manager = get_git_manager()
        if not git_manager:
            return create_error_response("Git manager not initialized", 500)

        # Only auto-commit if quality is good enough
        min_quality = 0.8
        if quality_score is not None and quality_score < min_quality:
            return create_success_response(
                {
                    "auto_commit": False,
                    "reason": f"Quality score {quality_score:.1%} below threshold {min_quality:.1%}",
                }
            )

        # Add the file
        add_result = await git_manager.add_files([file_path])
        if not add_result.success:
            return create_error_response(f"Failed to add file: {add_result.error}", 400)

        # Create commit message
        file_name = Path(file_path).name
        commit_msg = f"AI: {operation.title()} {file_name}"

        if purpose:
            commit_msg += f" - {purpose[:100]}"

        if quality_score:
            commit_msg += f" (Q: {quality_score:.1%})"

        # Commit
        commit_result = await git_manager.commit(commit_msg)

        if commit_result.success:
            commit_hash = (
                commit_result.data.get("commit_hash") if commit_result.data else None
            )
            return create_success_response(
                {
                    "auto_commit": True,
                    "commit_hash": commit_hash,
                    "commit_message": commit_msg,
                    "file_path": file_path,
                }
            )
        else:
            return create_error_response(
                f"Failed to commit: {commit_result.error}", 400
            )

    except Exception as e:
        return create_error_response(f"Auto-commit failed: {str(e)}", 500)
