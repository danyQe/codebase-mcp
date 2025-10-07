"""
File operation endpoints
Handles intelligent write, AI-assisted edit, and read operations
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from core import get_write_pipeline, get_edit_pipeline, get_search_engine
from core.config import get_settings
from schemas.requests import WriteRequest, EditRequestAPI, FileRequest
from code_tools import EditRequest
from utils import (
    create_success_response,
    create_error_response,
    create_detailed_error_response,
    validate_file_path,
)

router = APIRouter(tags=["files"])


@router.post("/write")
async def intelligent_write(request: WriteRequest):
    """Intelligent write operation with formatting and dependency checking"""
    try:
        write_pipeline = get_write_pipeline()
        settings = get_settings()
        print("relative filepath:",request.file_path)
        if not write_pipeline:
            return create_detailed_error_response(
                "Write pipeline not initialized",
                500,
                "ServiceNotAvailable",
                {"service": "WritePipeline"},
                "WritePipeline",
                "initialization",
                settings.WORKING_DIR,
            )

        # Validate file path
        try:
            file_path = await validate_file_path(
                request.file_path, settings.WORKING_DIR
            )
            print("after file path:",file_path)
        except HTTPException as e:
            return create_detailed_error_response(
                f"Invalid file path: {request.file_path}",
                e.status_code,
                "FilePathValidationError",
                {"file_path": request.file_path, "validation_error": e.detail},
                "WritePipeline",
                "file_validation",
                settings.WORKING_DIR,
            )

        if not request.content.strip():
            return create_detailed_error_response(
                "Empty content provided for write operation",
                400,
                "EmptyContent",
                {
                    "file_path": request.file_path,
                    "content_length": len(request.content),
                },
                "WritePipeline",
                "content_validation",
                settings.WORKING_DIR,
            )

        try:
            result = await write_pipeline.process_write(
                content=request.content,
                file_path=str(file_path),
                purpose=request.purpose,
                language=request.language,
                save_to_file=request.save_to_file,
            )
        except Exception as pipeline_error:
            return create_detailed_error_response(
                f"Write pipeline processing failed: {str(pipeline_error)}",
                500,
                "WritePipelineError",
                {
                    "file_path": request.file_path,
                    "content_preview": (
                        request.content[:200] + "..."
                        if len(request.content) > 200
                        else request.content
                    ),
                    "language": request.language,
                    "pipeline_error": str(pipeline_error),
                    "error_type": type(pipeline_error).__name__,
                },
                "WritePipeline",
                "process_write",
                settings.WORKING_DIR,
            )

        # Convert result to API response format
        response_data = {
            "file_path": result.file_path,
            "success": result.success,
            "quality_score": result.quality_score,
            "summary": result.summary,
            "formatting": {
                "success": (
                    result.format_result.success
                    if hasattr(result, "format_result")
                    else True
                ),
                "changes_made": (
                    result.format_result.changes_made
                    if hasattr(result, "format_result")
                    else []
                ),
                "errors": (
                    result.format_result.errors
                    if hasattr(result, "format_result")
                    else []
                ),
                "warnings": (
                    result.format_result.warnings
                    if hasattr(result, "format_result")
                    else []
                ),
            },
            "dependencies": {
                "success": (
                    result.dependency_result.success
                    if hasattr(result, "dependency_result")
                    else True
                ),
                "imports_found": (
                    len(result.dependency_result.imports_found)
                    if hasattr(result, "dependency_result")
                    else 0
                ),
                "missing_dependencies": (
                    result.dependency_result.missing_dependencies
                    if hasattr(result, "dependency_result")
                    else []
                ),
                "resolved_symbols": (
                    result.dependency_result.resolved_symbols
                    if hasattr(result, "dependency_result")
                    else []
                ),
                "duplicate_definitions": (
                    result.dependency_result.duplicate_definitions
                    if hasattr(result, "dependency_result")
                    else []
                ),
                "suggestions": (
                    result.dependency_result.suggestions
                    if hasattr(result, "dependency_result")
                    else []
                ),
            },
            "errors": result.errors if hasattr(result, "errors") else [],
            "warnings": result.warnings if hasattr(result, "warnings") else [],
        }

        if result.success:
            return create_success_response(response_data)
        else:
            # Analyze why it failed
            failure_reasons = []
            suggested_fixes = []

            if hasattr(result, "format_result") and not result.format_result.success:
                failure_reasons.append("Code formatting failed")
                suggested_fixes.extend(
                    [
                        "Check for syntax errors in the code",
                        "Ensure proper indentation and structure",
                        "Verify the programming language is correctly detected",
                    ]
                )

            if result.quality_score < 0.6:
                failure_reasons.append(
                    f"Quality score too low: {result.quality_score:.1%}"
                )
                suggested_fixes.extend(
                    [
                        "Review code for completeness and correctness",
                        "Add proper documentation and comments",
                        "Ensure all imports and dependencies are included",
                    ]
                )

            if (
                hasattr(result, "dependency_result")
                and result.dependency_result.missing_dependencies
            ):
                failure_reasons.append(
                    f"Missing dependencies: {', '.join(result.dependency_result.missing_dependencies)}"
                )
                suggested_fixes.append(
                    "Add required imports or install missing packages"
                )

            if not failure_reasons:
                failure_reasons.append("Unknown quality issue")
                suggested_fixes.append("Check write pipeline logs for more details")

            response_data["failure_analysis"] = {
                "failure_reasons": failure_reasons,
                "suggested_fixes": suggested_fixes,
                "quality_threshold": 0.6,
            }

            return create_detailed_error_response(
                "Write operation failed quality checks",
                422,
                "WriteQualityFailure",
                response_data,
                "WritePipeline",
                "quality_validation",
                settings.WORKING_DIR,
            )

    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Unexpected error in write operation: {str(e)}",
            500,
            "UnexpectedError",
            {
                "file_path": request.file_path if "request" in locals() else "unknown",
                "exception_type": type(e).__name__,
                "full_error": str(e),
            },
            "WritePipeline",
            "write_operation",
            settings.WORKING_DIR,
        )


@router.get("/write/stats")
async def get_write_stats():
    """Get write pipeline statistics"""
    try:
        write_pipeline = get_write_pipeline()
        if not write_pipeline:
            return create_error_response("Write pipeline not initialized", 500)

        stats = write_pipeline.get_stats()
        return create_success_response(stats)

    except Exception as e:
        return create_error_response(f"Failed to get write stats: {str(e)}", 500)


@router.post("/edit")
async def intelligent_edit(request: EditRequestAPI):
    """AI-assisted code editing with comprehensive error reporting"""
    try:
        edit_pipeline = get_edit_pipeline()
        settings = get_settings()

        if not edit_pipeline:
            return create_detailed_error_response(
                "Edit pipeline not initialized",
                500,
                "ServiceNotAvailable",
                {"service": "EditPipeline"},
                "EditPipeline",
                "initialization",
                settings.WORKING_DIR,
            )

        # Validate file path
        try:
            file_path = await validate_file_path(
                request.target_file, settings.WORKING_DIR
            )
        except HTTPException as e:
            return create_detailed_error_response(
                f"Invalid target file path: {request.target_file}",
                e.status_code,
                "FilePathValidationError",
                {"target_file": request.target_file, "validation_error": e.detail},
                "EditPipeline",
                "file_validation",
                settings.WORKING_DIR,
            )

        # Check if file exists
        if not file_path.exists():
            return create_detailed_error_response(
                f"Target file does not exist: {request.target_file}",
                404,
                "FileNotFound",
                {
                    "target_file": request.target_file,
                    "resolved_path": str(file_path),
                    "suggestion": "Ensure the file exists before attempting to edit it",
                },
                "EditPipeline",
                "file_existence_check",
                settings.WORKING_DIR,
            )

        # Convert API request to internal EditRequest
        edit_request = EditRequest(
            target_file=str(file_path),
            instructions=request.instructions,
            code_edit=request.code_edit,
            language=request.language,
        )

        # Process through edit pipeline
        try:
            result = await edit_pipeline.process_edit(
                request=edit_request, save_to_file=request.save_to_file
            )
        except Exception as pipeline_error:
            return create_detailed_error_response(
                f"Edit pipeline processing failed: {str(pipeline_error)}",
                500,
                "EditPipelineError",
                {
                    "target_file": request.target_file,
                    "instructions": (
                        request.instructions[:100] + "..."
                        if len(request.instructions) > 100
                        else request.instructions
                    ),
                    "pipeline_error": str(pipeline_error),
                    "error_type": type(pipeline_error).__name__,
                },
                "EditPipeline",
                "process_edit",
                settings.WORKING_DIR,
            )

        # Create detailed response data
        response_data = {
            "file_path": result.file_path,
            "success": result.success,
            "instructions": result.instructions,
            "summary": result.summary,
            "quality_score": result.quality_score,
            "processing": {
                "gemini_edit_success": result.gemini_edit_success,
                "format_success": result.format_success,
                "error_correction_attempts": result.error_correction_attempts,
                "total_gemini_calls": result.total_gemini_calls,
                "processing_time_seconds": result.processing_time_seconds,
            },
            "content_info": {
                "original_length": len(result.original_content),
                "final_length": len(result.final_content),
                "content_changed": result.original_content != result.final_content,
            },
            "errors": {
                "gemini_errors": result.gemini_errors,
                "format_errors": result.format_errors,
                "warnings": result.warnings,
            },
        }

        if result.success:
            return create_success_response(response_data)
        else:
            # Edit failed - provide detailed analysis
            failure_analysis = {
                "failure_stage": "unknown",
                "root_cause": "unknown",
                "suggested_fixes": [],
            }

            if not result.gemini_edit_success:
                failure_analysis["failure_stage"] = "gemini_edit"
                failure_analysis["root_cause"] = "Gemini API call failed"
                failure_analysis["suggested_fixes"].append(
                    "Check Gemini API key and rate limits"
                )

            elif not result.format_success:
                failure_analysis["failure_stage"] = "formatting_validation"
                failure_analysis["root_cause"] = "Code formatting or validation failed"
                failure_analysis["suggested_fixes"].append(
                    "Check for syntax errors in the edit"
                )
                failure_analysis["suggested_fixes"].append(
                    "Verify the edit follows proper code structure"
                )

            elif result.quality_score < 0.6:
                failure_analysis["failure_stage"] = "quality_check"
                failure_analysis["root_cause"] = (
                    f"Quality score too low: {result.quality_score:.2f}"
                )
                failure_analysis["suggested_fixes"].append(
                    "Review edit instructions for clarity"
                )
                failure_analysis["suggested_fixes"].append(
                    "Check if the target file has complex dependencies"
                )

            response_data["failure_analysis"] = failure_analysis

            return create_detailed_error_response(
                "Edit operation failed quality checks",
                422,
                "EditQualityFailure",
                response_data,
                "EditPipeline",
                "quality_validation",
                settings.WORKING_DIR,
            )

    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Unexpected error in edit operation: {str(e)}",
            500,
            "UnexpectedError",
            {
                "target_file": (
                    request.target_file if "request" in locals() else "unknown"
                ),
                "exception_type": type(e).__name__,
                "full_error": str(e),
            },
            "EditPipeline",
            "edit_operation",
            settings.WORKING_DIR,
        )


@router.get("/edit/stats")
async def get_edit_stats():
    """Get edit pipeline statistics"""
    try:
        edit_pipeline = get_edit_pipeline()
        if not edit_pipeline:
            return create_error_response("Edit pipeline not initialized", 500)

        stats = edit_pipeline.get_stats()
        return create_success_response(stats)

    except Exception as e:
        return create_error_response(f"Failed to get edit stats: {str(e)}", 500)


@router.post("/read")
async def read_code_content(
    file_path: str = Query(..., description="Path to the file"),
    symbol_name: Optional[str] = Query(None, description="Symbol name to read"),
    occurrence: int = Query(
        1, description="Which occurrence of the symbol (default: 1)"
    ),
    start_line: Optional[int] = Query(
        None, description="Start line number (1-indexed)"
    ),
    end_line: Optional[int] = Query(None, description="End line number (inclusive)"),
    with_line_numbers: bool = Query(True, description="Include line numbers in output"),
):
    """Read code content with enhanced error handling for line ranges"""
    try:
        search_engine = get_search_engine()
        settings = get_settings()

        if not search_engine:
            return create_detailed_error_response(
                "Search engine not initialized",
                500,
                "ServiceNotAvailable",
                {"service": "SearchEngine"},
                "SearchEngine",
                "initialization",
                settings.WORKING_DIR,
            )

        # Validate file path
        try:
            await validate_file_path(file_path, settings.WORKING_DIR)
        except HTTPException as e:
            return create_detailed_error_response(
                f"Invalid file path: {file_path}",
                e.status_code,
                "FilePathValidationError",
                {"file_path": file_path, "validation_error": e.detail},
                "SearchEngine",
                "file_validation",
                settings.WORKING_DIR,
            )

        # Validate line range parameters
        if start_line is not None and end_line is not None:
            if start_line < 1:
                return create_detailed_error_response(
                    f"Invalid start_line: {start_line}. Line numbers must be >= 1",
                    400,
                    "InvalidLineRange",
                    {"start_line": start_line, "end_line": end_line},
                    "SearchEngine",
                    "line_validation",
                    settings.WORKING_DIR,
                )

            if end_line < start_line:
                return create_detailed_error_response(
                    f"Invalid line range: end_line ({end_line}) < start_line ({start_line})",
                    400,
                    "InvalidLineRange",
                    {
                        "start_line": start_line,
                        "end_line": end_line,
                        "suggestion": "Ensure end_line >= start_line",
                    },
                    "SearchEngine",
                    "line_validation",
                    settings.WORKING_DIR,
                )

        # Validate occurrence parameter
        if occurrence < 1:
            return create_detailed_error_response(
                f"Invalid occurrence: {occurrence}. Must be >= 1",
                400,
                "InvalidOccurrence",
                {"occurrence": occurrence},
                "SearchEngine",
                "occurrence_validation",
                settings.WORKING_DIR,
            )

        try:
            result = await search_engine.read_symbol_content(
                file_path=file_path,
                symbol_name=symbol_name,
                occurrence=occurrence,
                start_line=start_line,
                end_line=end_line,
                with_line_numbers=with_line_numbers,
            )
        except Exception as read_error:
            return create_detailed_error_response(
                f"Failed to read content: {str(read_error)}",
                500,
                "ReadContentError",
                {
                    "file_path": file_path,
                    "symbol_name": symbol_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "read_error": str(read_error),
                },
                "SearchEngine",
                "read_content",
                settings.WORKING_DIR,
            )

        if result.get("success"):
            return create_success_response(result)
        else:
            return create_detailed_error_response(
                result.get("error", "Unknown read error"),
                400,
                "ReadOperationFailed",
                {
                    "file_path": file_path,
                    "symbol_name": symbol_name,
                    "line_range": (
                        f"{start_line}-{end_line}" if start_line and end_line else None
                    ),
                    "occurrence": occurrence,
                    "with_line_numbers": with_line_numbers,
                },
                "SearchEngine",
                "read_operation",
                settings.WORKING_DIR,
            )

    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"Unexpected error in read operation: {str(e)}",
            500,
            "UnexpectedError",
            {
                "file_path": file_path,
                "exception_type": type(e).__name__,
                "full_error": str(e),
            },
            "SearchEngine",
            "read_operation",
            settings.WORKING_DIR,
        )


@router.get("/read/{file_path:path}")
async def read_file_content(
    file_path: str,
    start_line: Optional[int] = Query(None, description="Start line number"),
    end_line: Optional[int] = Query(None, description="End line number"),
    with_line_numbers: bool = Query(True, description="Include line numbers"),
):
    """Read file content with optional line range"""
    try:
        search_engine = get_search_engine()
        settings = get_settings()

        if not search_engine:
            return create_error_response("Search engine not initialized", 500)

        # Validate file path
        await validate_file_path(file_path, settings.WORKING_DIR)

        result = await search_engine.read_symbol_content(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            with_line_numbers=with_line_numbers,
        )

        if result.get("success"):
            return create_success_response(result)
        else:
            return create_error_response(result.get("error", "Unknown error"), 400)

    except HTTPException:
        raise
    except Exception as e:
        return create_error_response(f"Read operation failed: {str(e)}", 500)


@router.post("/file")
async def file_operations(request: FileRequest):
    """Handle legacy file operations"""
    try:
        settings = get_settings()

        try:
            file_path = await validate_file_path(
                request.file_path, settings.WORKING_DIR
            )
        except HTTPException as e:
            return create_detailed_error_response(
                f"Invalid file path: {request.file_path}",
                e.status_code,
                "FilePathValidationError",
                {"file_path": request.file_path, "validation_error": e.detail},
                "FileOperations",
                "path_validation",
                settings.WORKING_DIR,
            )

        operation = request.operation.lower()

        if operation == "read":
            if not file_path.exists():
                return create_detailed_error_response(
                    f"File not found: {request.file_path}",
                    404,
                    "FileNotFound",
                    {
                        "file_path": request.file_path,
                        "resolved_path": str(file_path),
                    },
                    "FileOperations",
                    "read",
                    settings.WORKING_DIR,
                )

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Extract specific lines if requested
                if request.start_line is not None and request.end_line is not None:
                    lines = content.split("\n")
                    if request.start_line < 1 or request.end_line < request.start_line:
                        return create_detailed_error_response(
                            f"Invalid line range: {request.start_line}-{request.end_line}",
                            400,
                            "InvalidLineRange",
                            {
                                "start_line": request.start_line,
                                "end_line": request.end_line,
                                "total_lines": len(lines),
                            },
                            "FileOperations",
                            "line_range_validation",
                            settings.WORKING_DIR,
                        )

                    if request.end_line > len(lines):
                        return create_detailed_error_response(
                            f"End line {request.end_line} exceeds file length {len(lines)}",
                            400,
                            "LineRangeExceeded",
                            {
                                "end_line": request.end_line,
                                "file_length": len(lines),
                                "suggestion": f"Use end_line <= {len(lines)}",
                            },
                            "FileOperations",
                            "line_range_check",
                            settings.WORKING_DIR,
                        )

                    selected_lines = lines[request.start_line - 1 : request.end_line]
                    content = "\n".join(selected_lines)

                return create_success_response(
                    {
                        "operation": "read",
                        "file_path": request.file_path,
                        "content": content,
                        "total_lines": len(content.split("\n")),
                        "line_range": (
                            f"{request.start_line}-{request.end_line}"
                            if request.start_line
                            else "full_file"
                        ),
                    }
                )
            except Exception as e:
                return create_detailed_error_response(
                    f"Read error: {str(e)}",
                    500,
                    "FileReadError",
                    {"file_path": request.file_path, "error_details": str(e)},
                    "FileOperations",
                    "file_read",
                    settings.WORKING_DIR,
                )

        elif operation == "write":
            if not request.content:
                return create_error_response(
                    "Content required for write operation", 400
                )

            # Use intelligent write pipeline if available
            write_pipeline = get_write_pipeline()
            if write_pipeline:
                result = await write_pipeline.process_write(
                    content=request.content,
                    file_path=request.file_path,
                    save_to_file=True,
                )

                if result.success:
                    return create_success_response(
                        {
                            "operation": "write",
                            "file_path": request.file_path,
                            "summary": result.summary,
                            "quality_score": result.quality_score,
                        }
                    )
                else:
                    return create_error_response(
                        f"Write failed: {'; '.join(result.errors)}", 422
                    )
            else:
                # Fallback to simple write
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(request.content)
                return create_success_response(
                    {
                        "operation": "write",
                        "file_path": request.file_path,
                        "message": "File written (without intelligent processing)",
                    }
                )

        elif operation == "create":
            if file_path.exists():
                return create_detailed_error_response(
                    f"File already exists: {request.file_path}",
                    409,
                    "FileExists",
                    {
                        "file_path": request.file_path,
                        "resolved_path": str(file_path),
                        "suggestion": "Use 'write' operation to overwrite or choose a different filename",
                    },
                    "FileOperations",
                    "create",
                    settings.WORKING_DIR,
                )

            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                content = request.content or ""

                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                return create_success_response(
                    {
                        "operation": "create",
                        "file_path": request.file_path,
                        "message": "File created successfully",
                        "content_length": len(content),
                        "lines_written": len(content.split("\n")) if content else 0,
                    }
                )
            except Exception as e:
                return create_detailed_error_response(
                    f"Create error: {str(e)}",
                    500,
                    "FileCreateError",
                    {"file_path": request.file_path, "error_details": str(e)},
                    "FileOperations",
                    "file_create",
                    settings.WORKING_DIR,
                )

        elif operation == "delete":
            if not file_path.exists():
                return create_error_response(
                    f"File not found: {request.file_path}", 404
                )

            file_path.unlink()
            return create_success_response(
                {
                    "operation": "delete",
                    "file_path": request.file_path,
                    "message": "File deleted successfully",
                }
            )

        else:
            return create_error_response(
                f"Unsupported file operation: {operation}", 400
            )

    except HTTPException:
        raise
    except Exception as e:
        settings = get_settings()
        return create_detailed_error_response(
            f"File operation failed: {str(e)}",
            500,
            "FileOperationError",
            {
                "operation": request.operation,
                "file_path": request.file_path,
                "exception_type": type(e).__name__,
            },
            "FileOperations",
            request.operation,
            settings.WORKING_DIR,
        )
