"""
Edit Pipeline for Intelligent Code Editing
Orchestrates the complete edit process using Gemini AI and existing validation tools.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

from .gemini_client import GeminiClient
from .write_pipeline import WritePipeline

logger = logging.getLogger(__name__)


@dataclass
class EditRequest:
    """Request for code editing"""

    target_file: str
    instructions: str
    code_edit: str
    language: Optional[str] = None


@dataclass
class EditResult:
    """Result of edit operation"""

    file_path: str
    success: bool
    original_content: str
    final_content: str
    instructions: str
    code_edit: str

    # Processing steps
    gemini_edit_success: bool
    format_success: bool
    error_correction_attempts: int

    # Quality metrics
    quality_score: float
    summary: str

    # Detailed results
    gemini_errors: List[str]
    format_errors: List[str]
    warnings: List[str]

    # Stats
    total_gemini_calls: int
    processing_time_seconds: float


class EditPipeline:
    """Pipeline for intelligent code editing with AI assistance and validation"""

    def __init__(
        self, write_pipeline: WritePipeline, gemini_api_key: Optional[str] = None
    ):
        """
        Initialize edit pipeline

        Args:
            write_pipeline: Existing write pipeline for formatting/validation
            gemini_api_key: Gemini API key (uses env var if None)
        """
        self.write_pipeline = write_pipeline
        self.gemini_client = GeminiClient(api_key=gemini_api_key)

        # Configuration
        self.max_error_correction_attempts = 3
        self.min_quality_threshold = 0.6

        # Statistics
        self.total_edits = 0
        self.successful_edits = 0
        self.failed_edits = 0
        self.total_gemini_calls = 0
        self.total_error_corrections = 0

    async def process_edit(
        self, request: EditRequest, save_to_file: bool = True
    ) -> EditResult:
        """
        Process an edit request through the complete pipeline

        Args:
            request: Edit request details
            save_to_file: Whether to save the final result to file

        Returns:
            EditResult with complete processing information
        """
        start_time = asyncio.get_event_loop().time()

        # Initialize result
        result = EditResult(
            file_path=request.target_file,
            success=False,
            original_content="",
            final_content="",
            instructions=request.instructions,
            code_edit=request.code_edit,
            gemini_edit_success=False,
            format_success=False,
            error_correction_attempts=0,
            quality_score=0.0,
            summary="",
            gemini_errors=[],
            format_errors=[],
            warnings=[],
            total_gemini_calls=0,
            processing_time_seconds=0.0,
        )

        try:
            self.total_edits += 1

            # Step 1: Read the original file
            original_content = await self._read_file(request.target_file)
            result.original_content = original_content

            if not original_content:
                result.gemini_errors.append("File not found or empty")
                result.summary = "Failed: File not found or empty"
                return result

            # Step 2: Apply edit using Gemini
            logger.info(f"Applying edit to {request.target_file} using Gemini")

            edited_content = await self.gemini_client.edit_code(
                file_content=original_content,
                edit_instructions=request.instructions,
                code_edit=request.code_edit,
                file_path=request.target_file,
                language=request.language,
            )

            result.total_gemini_calls += 1
            self.total_gemini_calls += 1
            result.gemini_edit_success = True
            result.final_content = edited_content

            # Step 3: Validate and format using existing write pipeline
            logger.info("Validating and formatting edited content")

            write_result = await self.write_pipeline.process_write(
                content=edited_content,
                file_path=request.target_file,
                purpose=f"Edit: {request.instructions}",
                language=request.language,
                save_to_file=False,  # Don't save yet, we might need error correction
            )

            # Step 4: Handle formatting/validation results
            if (
                write_result.success
                and write_result.quality_score >= self.min_quality_threshold
            ):
                # Success! Use the formatted content
                result.final_content = (
                    write_result.final_content or write_result.original_content
                )
                result.format_success = True
                result.quality_score = write_result.quality_score
                result.summary = f"Edit successful: {write_result.summary}"
                result.success = True

            else:
                # Formatting/validation failed - attempt error correction
                logger.info(
                    "Formatting/validation failed, attempting error correction with Gemini"
                )

                correction_result = await self._attempt_error_correction(
                    edited_content=edited_content,
                    write_result=write_result,
                    request=request,
                    result=result,
                )

                if correction_result:
                    result.final_content = correction_result
                    result.format_success = True
                    result.success = True
                    result.summary = "Edit successful after error correction"

                    # Re-validate the corrected content
                    final_write_result = await self.write_pipeline.process_write(
                        content=correction_result,
                        file_path=request.target_file,
                        purpose=f"Edit (corrected): {request.instructions}",
                        language=request.language,
                        save_to_file=False,
                    )

                    result.quality_score = final_write_result.quality_score
                    result.final_content = (
                        final_write_result.final_content or correction_result
                    )

                else:
                    # Error correction failed
                    result.format_errors.extend(write_result.errors)
                    result.summary = f"Edit failed: Unable to correct errors after {result.error_correction_attempts} attempts"
                    result.quality_score = write_result.quality_score

            # Step 5: Save to file if requested and successful
            if save_to_file and result.success:
                await self._save_file(request.target_file, result.final_content)
                result.summary += " (saved to file)"

            # Update statistics
            if result.success:
                self.successful_edits += 1
            else:
                self.failed_edits += 1

            result.processing_time_seconds = (
                asyncio.get_event_loop().time() - start_time
            )

            return result

        except Exception as e:
            logger.error(f"Edit pipeline error: {e}")
            result.gemini_errors.append(str(e))
            result.summary = f"Edit failed: {str(e)}"
            result.processing_time_seconds = (
                asyncio.get_event_loop().time() - start_time
            )
            self.failed_edits += 1
            return result

    async def _attempt_error_correction(
        self,
        edited_content: str,
        write_result,
        request: EditRequest,
        result: EditResult,
    ) -> Optional[str]:
        """
        Attempt to correct errors using Gemini

        Returns:
            Corrected content if successful, None if failed
        """

        # Collect all errors
        all_errors = []
        all_errors.extend(write_result.errors)

        if hasattr(write_result, "format_result") and write_result.format_result:
            all_errors.extend(write_result.format_result.errors)

        if (
            hasattr(write_result, "dependency_result")
            and write_result.dependency_result
        ):
            all_errors.extend(write_result.dependency_result.missing_dependencies)

        if not all_errors:
            result.warnings.append("No specific errors found for correction")
            return None

        # Attempt correction with limited retries
        for attempt in range(self.max_error_correction_attempts):
            try:
                result.error_correction_attempts += 1
                logger.info(
                    f"Error correction attempt {attempt + 1}/{self.max_error_correction_attempts}"
                )

                corrected_content = await self.gemini_client.fix_code_errors(
                    file_content=edited_content,
                    errors=all_errors,
                    file_path=request.target_file,
                    language=request.language,
                    original_edit_context=request.instructions,
                )

                result.total_gemini_calls += 1
                self.total_gemini_calls += 1
                self.total_error_corrections += 1

                # Quick validation of corrected content
                validation_result = await self.write_pipeline.process_write(
                    content=corrected_content,
                    file_path=request.target_file,
                    purpose=f"Edit validation (attempt {attempt + 1})",
                    language=request.language,
                    save_to_file=False,
                )

                if (
                    validation_result.success
                    and validation_result.quality_score >= self.min_quality_threshold
                ):
                    logger.info(f"Error correction successful on attempt {attempt + 1}")
                    return corrected_content

                # Update errors for next attempt
                edited_content = corrected_content
                all_errors = validation_result.errors.copy()

                if (
                    hasattr(validation_result, "format_result")
                    and validation_result.format_result
                ):
                    all_errors.extend(validation_result.format_result.errors)

            except Exception as e:
                logger.error(f"Error correction attempt {attempt + 1} failed: {e}")
                result.gemini_errors.append(
                    f"Correction attempt {attempt + 1}: {str(e)}"
                )

        logger.warning(
            f"Error correction failed after {self.max_error_correction_attempts} attempts"
        )
        return None

    async def _read_file(self, file_path: str) -> str:
        """Read file content safely"""
        try:
            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                path = Path(file_path)
            else:
                # Assume relative to current working directory
                path = Path(os.getenv('WORKING_DIR', '.'))/file_path

            if not path.exists():
                logger.error(f"File not found: {file_path}")
                return ""

            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""

    async def _save_file(self, file_path: str, content: str) -> bool:
        """Save file content safely"""
        try:
            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                path = Path(file_path)
            else:
                path = Path.cwd() / file_path

            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"File saved: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        success_rate = self.successful_edits / max(self.total_edits, 1)

        return {
            "total_edits": self.total_edits,
            "successful_edits": self.successful_edits,
            "failed_edits": self.failed_edits,
            "success_rate": success_rate,
            "total_gemini_calls": self.total_gemini_calls,
            "total_error_corrections": self.total_error_corrections,
            "gemini_client_stats": self.gemini_client.get_stats(),
            "write_pipeline_stats": (
                self.write_pipeline.get_stats()
                if hasattr(self.write_pipeline, "get_stats")
                else {}
            ),
        }
