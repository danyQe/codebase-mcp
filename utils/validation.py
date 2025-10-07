"""
Utility functions for path validation and file operations
"""

import os
from pathlib import Path
from fastapi import HTTPException, status


async def validate_file_path(file_path: str, working_dir: str) -> Path:
    """
    Validate and resolve file path within working directory

    Args:
        file_path: Path to validate
        working_dir: Working directory to check against

    Returns:
        Resolved Path object

    Raises:
        HTTPException: If path is invalid or outside working directory
    """
    try:
        if os.path.isabs(file_path):
            abs_path = Path(file_path).resolve()
        else:
            abs_path = Path(working_dir) / file_path
            abs_path = abs_path.resolve()

        # Ensure path is within working directory
        working_path = Path(working_dir).resolve()
        if not str(abs_path).startswith(str(working_path)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: path outside working directory",
            )

        return abs_path
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file path: {str(e)}",
        )
