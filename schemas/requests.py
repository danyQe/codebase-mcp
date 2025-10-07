"""
Request models for API endpoints
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class WriteRequest(BaseModel):
    """Request model for write operations"""

    file_path: str = Field(..., description="Path to file to write")
    content: str = Field(..., description="Code content to write")
    purpose: Optional[str] = Field(None, description="Purpose/description of the code")
    language: Optional[str] = Field(
        None, description="Programming language (python, javascript, typescript)"
    )
    save_to_file: bool = Field(
        True, description="Whether to save to file after processing"
    )


class EditRequestAPI(BaseModel):
    """Request model for edit operations"""

    target_file: str = Field(..., description="The target file to modify")
    instructions: str = Field(
        ..., description="Instructions describing what you are going to do"
    )
    code_edit: str = Field(
        ...,
        description="Precise lines of code to edit with // ... existing code ... markers",
    )
    language: Optional[str] = Field(
        None, description="Programming language (auto-detected if not provided)"
    )
    save_to_file: bool = Field(
        True, description="Whether to save to file after processing"
    )


class FileRequest(BaseModel):
    """Request model for legacy file operations"""

    operation: str = Field(..., description="File operation")
    file_path: str = Field(..., description="Path to file")
    content: Optional[str] = Field(None, description="File content")
    start_line: Optional[int] = Field(None, description="Start line number")
    end_line: Optional[int] = Field(None, description="End line number")


class GitOperationRequest(BaseModel):
    """Request model for git operations"""

    operation: str = Field(
        ...,
        description="Git operation (status, branches, log, diff, commit, add, blame)",
    )
    file_path: Optional[str] = Field(
        None, description="File path for file-specific operations"
    )
    message: Optional[str] = Field(None, description="Commit message")
    files: Optional[List[str]] = Field(None, description="Files to add/commit")
    max_results: Optional[int] = Field(
        10, description="Maximum results for log operations"
    )
    cached: Optional[bool] = Field(
        False, description="Show cached/staged changes for diff"
    )


class SessionRequest(BaseModel):
    """Request model for session operations"""

    operation: str = Field(
        ..., description="Session operation (start, end, switch, list, merge, delete)"
    )
    session_name: Optional[str] = Field(None, description="Session name")
    message: Optional[str] = Field(None, description="Message for session operations")
    auto_merge: Optional[bool] = Field(
        False, description="Auto merge when ending session"
    )


class WorkingDirectoryRequest(BaseModel):
    """Request model for working directory changes"""

    working_directory: str = Field(..., description="New working directory path")
