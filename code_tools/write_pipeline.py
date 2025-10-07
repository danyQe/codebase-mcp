"""Write pipeline that orchestrates code formatting and dependency checking"""

from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .formatter import CodeFormatter, FormatResult
from .dependency_checker import DependencyChecker, DependencyCheckResult
from semantic_search.core import SemanticSearchEngine


@dataclass
class WriteResult:
    """Result of the complete write pipeline"""

    success: bool
    file_path: str
    original_content: str
    final_content: str
    format_result: FormatResult
    dependency_result: DependencyCheckResult
    quality_score: float
    errors: list
    warnings: list
    summary: str


class WritePipeline:
    """Orchestrates the complete write pipeline with formatting and dependency checking"""

    def __init__(
        self,
        search_engine: Optional[SemanticSearchEngine] = None,
        quality_threshold: float = 0.6,
    ):
        self.formatter = CodeFormatter()
        self.dependency_checker = DependencyChecker(search_engine)
        self.search_engine = search_engine
        self.quality_threshold = quality_threshold

    async def process_write(
        self,
        content: str,
        file_path: str,
        purpose: Optional[str] = None,
        language: Optional[str] = None,
        save_to_file: bool = True,
    ) -> WriteResult:
        """Process code through the complete write pipeline"""

        original_content = content
        errors = []
        warnings = []

        try:
            # Step 1: Format the code
            print(f"🎨 Formatting code for {file_path}")
            format_result = self.formatter.format_code(
                content, file_path, language
            )

            if not format_result.success:
                errors.extend(format_result.errors)

            warnings.extend(format_result.warnings)
            current_content = format_result.formatted_code

            # Step 2: Check dependencies
            print(f"🔍 Checking dependencies for {file_path}")
            dependency_result = await self.dependency_checker.check_dependencies(
                current_content, file_path, language
            )

            if not dependency_result.success:
                errors.extend(dependency_result.errors)

            warnings.extend(dependency_result.warnings)

            # Step 3: Calculate quality score
            quality_score = self._calculate_quality_score(
                format_result, dependency_result, current_content, purpose
            )

            # Step 4: Create summary
            summary = self._create_summary(
                file_path, format_result, dependency_result, quality_score, purpose
            )

            # Step 5: Save file if quality passes threshold and save is enabled
            final_content = current_content
            pipeline_success = (
                len(errors) == 0 and quality_score >= self.quality_threshold
            )

            if save_to_file and pipeline_success:
                try:
                    await self._save_file(file_path, final_content)
                    print(f"✅ File saved: {file_path}")

                    # Update search index if available
                    if self.search_engine:
                        await self.search_engine.update_file(file_path)
                        print(f"🔄 Updated search index for {file_path}")

                except Exception as e:
                    errors.append(f"Failed to save file: {str(e)}")
                    pipeline_success = False
            elif not pipeline_success:
                if quality_score < self.quality_threshold:
                    warnings.append(
                        f"Quality score {quality_score:.1%} below threshold {self.quality_threshold:.1%}"
                    )

            return WriteResult(
                success=pipeline_success,
                file_path=file_path,
                original_content=original_content,
                final_content=final_content,
                format_result=format_result,
                dependency_result=dependency_result,
                quality_score=quality_score,
                errors=errors,
                warnings=warnings,
                summary=summary,
            )

        except Exception as e:
            errors.append(f"Pipeline error: {str(e)}")

            return WriteResult(
                success=False,
                file_path=file_path,
                original_content=original_content,
                final_content=content,
                format_result=FormatResult(False, content, [str(e)], [], False),
                dependency_result=DependencyCheckResult(
                    success=False,
                    imports_found=[],
                    resolved_symbols=[],  # Fixed: Added missing parameter
                    missing_dependencies=[],
                    duplicate_definitions=[],
                    suggestions=[],
                    warnings=[],
                    errors=[str(e)],
                ),
                quality_score=0.0,
                errors=errors,
                warnings=warnings,
                summary=f"❌ Pipeline failed: {str(e)}",
            )

    def _calculate_quality_score(
        self,
        format_result: FormatResult,
        dependency_result: DependencyCheckResult,
        content: str,
        purpose: Optional[str],
    ) -> float:
        """Calculate overall quality score (0.0 to 1.0)"""

        score = 1.0

        # Formatting penalties
        if not format_result.success:
            score -= 0.3  # Major penalty for formatting failures

        if format_result.errors:
            score -= min(0.2, len(format_result.errors) * 0.05)  # Up to -0.2 for errors

        if format_result.warnings:
            score -= min(
                0.1, len(format_result.warnings) * 0.02
            )  # Up to -0.1 for warnings

        # Dependency penalties
        if not dependency_result.success:
            score -= 0.2  # Penalty for dependency check failures

        if dependency_result.missing_dependencies:
            score -= min(
                0.15, len(dependency_result.missing_dependencies) * 0.05
            )  # Up to -0.15

        if dependency_result.errors:
            score -= min(0.1, len(dependency_result.errors) * 0.03)  # Up to -0.1

        # Code quality heuristics
        lines = content.split("\n")

        # Penalty for very long functions (basic heuristic)
        in_function = False
        function_length = 0
        for line in lines:
            stripped = line.strip()
            if any(
                stripped.startswith(keyword)
                for keyword in ["def ", "function ", "class "]
            ):
                if function_length > 50:  # Long function detected
                    score -= 0.05
                function_length = 0
                in_function = True
            elif in_function and (stripped == "" or not stripped.startswith(" ")):
                if function_length > 50:
                    score -= 0.05
                function_length = 0
                in_function = False
            elif in_function:
                function_length += 1

        # Bonus for having docstrings/comments
        comment_lines = sum(
            1 for line in lines if line.strip().startswith(("#", "//", '"""', "'''"))
        )
        if comment_lines > len(lines) * 0.1:  # More than 10% comments
            score += 0.05

        # Ensure score stays in bounds
        return max(0.0, min(1.0, score))

    def _create_summary(
        self,
        file_path: str,
        format_result: FormatResult,
        dependency_result: DependencyCheckResult,
        quality_score: float,
        purpose: Optional[str],
    ) -> str:
        """Create a human-readable summary of the write operation"""

        summary_lines = []

        # Header
        summary_lines.append(f"📝 Write Summary: {Path(file_path).name}")
        if purpose:
            summary_lines.append(f"Purpose: {purpose}")

        summary_lines.append(f"Quality Score: {quality_score:.1%}")

        # Formatting results
        if format_result.changes_made:
            summary_lines.append("✅ Code formatted successfully")
        else:
            summary_lines.append("ℹ️  No formatting changes needed")

        if format_result.errors:
            summary_lines.append(f"❌ {len(format_result.errors)} formatting errors")

        if format_result.warnings:
            summary_lines.append(
                f"⚠️  {len(format_result.warnings)} formatting warnings"
            )

        # Dependency results
        if dependency_result.imports_found:
            summary_lines.append(
                f"📦 {len(dependency_result.imports_found)} imports analyzed"
            )

        if dependency_result.resolved_symbols:
            summary_lines.append(
                f"✅ {len(dependency_result.resolved_symbols)} symbols found in codebase"
            )

        if dependency_result.missing_dependencies:
            summary_lines.append(
                f"❌ {len(dependency_result.missing_dependencies)} missing dependencies"
            )

        if dependency_result.suggestions:
            summary_lines.append(
                f"💡 {len(dependency_result.suggestions)} suggestions available"
            )

        # Final status
        if quality_score >= self.quality_threshold:
            summary_lines.append("✅ Ready to save")
        else:
            summary_lines.append(
                f"❌ Quality below threshold ({self.quality_threshold:.1%})"
            )

        return "\n".join(summary_lines)

    async def _save_file(self, file_path: str, content: str):
        """Save content to file, creating directories as needed"""

        file_obj = Path(file_path)

        # Create parent directories if they don't exist
        file_obj.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(file_obj, "w", encoding="utf-8") as f:
            f.write(content)

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            "quality_threshold": self.quality_threshold,
            "formatter_available": self.formatter is not None,
            "dependency_checker_available": self.dependency_checker is not None,
            "search_engine_available": self.search_engine is not None,
        }

    def set_quality_threshold(self, threshold: float):
        """Update quality threshold"""
        self.quality_threshold = max(0.0, min(1.0, threshold))
