# ruff: noqa
"""Code formatting utilities"""

import subprocess
import tempfile
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class FormatResult:
    """Result of code formatting operation"""

    success: bool
    formatted_code: str
    errors: list
    warnings: list
    changes_made: bool


class CodeFormatter:
    """Handles code formatting for different languages"""

    def __init__(self):
        self.formatters = {
            ".py": self._format_python,
            ".js": self._format_javascript,
            ".jsx": self._format_javascript,
            ".ts": self._format_typescript,
            ".tsx": self._format_typescript,
        }

    def format_code(
        self, content: str, file_path: str, language: Optional[str] = None
    ) -> FormatResult:
        """Format code based on file extension or language"""

        if language:
            # Direct language specification
            if language.lower() == "python":
                return self._format_python(content, file_path)
            elif language.lower() in ["javascript", "js"]:
                return self._format_javascript(content, file_path)
            elif language.lower() in ["typescript", "ts"]:
                return self._format_typescript(content, file_path)

        # Determine from file extension
        file_ext = Path(file_path).suffix.lower()
        formatter = self.formatters.get(file_ext)

        if formatter:
            return formatter(content, file_path)
        else:
            # No formatter available, return as-is
            return FormatResult(
                success=True,
                formatted_code=content,
                errors=[],
                warnings=[f"No formatter available for {file_ext}"],
                changes_made=False,
            )

    def _format_python(self, content: str, file_path: str) -> FormatResult:
        """Format Python code using black and ruff"""
        errors = []
        warnings = []
        formatted_code = content
        changes_made = False

        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False,encoding='utf-8'
            ) as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name

            # Step 1: Format with black
            try:
                result = subprocess.run(
                    ["python", "-m", "black", tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    with open(tmp_path,"r",encoding="utf-8") as f:
                        formatted_code=f.read()
                    changes_made = formatted_code != content
                else:
                    errors.append(f"Black formatting error: {result.stderr}")
            except subprocess.TimeoutExpired:
                errors.append("Black formatting timed out")
            except FileNotFoundError:
                warnings.append("Black not found, skipping formatting")

            # Step 2: Lint with ruff (check for issues, don't auto-fix)
            try:
                result = subprocess.run(
                    ["python", "-m", "ruff", "check", tmp_path, "--output-format=json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.stdout:
                    import json

                    ruff_issues = json.loads(result.stdout)
                    for issue in ruff_issues:
                        warnings.append(
                            f"Line {issue.get('location', {}).get('row', '?')}: "
                            f"{issue.get('code', '?')} - {issue.get('message', 'Unknown issue')}"
                        )
            except subprocess.TimeoutExpired:
                warnings.append("Ruff linting timed out")
            except FileNotFoundError:
                warnings.append("Ruff not found, skipping linting")
            except Exception as e:
                warnings.append(f"Ruff analysis error: {str(e)}")

        except Exception as e:
            errors.append(f"Python formatting error: {str(e)}")
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)  # type:ignore
            except:
                pass

        return FormatResult(
            success=len(errors) == 0,
            formatted_code=formatted_code,
            errors=errors,
            warnings=warnings,
            changes_made=changes_made,
        )

    def _format_javascript(self, content: str, file_path: str) -> FormatResult:
        """Format JavaScript code using prettier"""
        errors = []
        warnings = []
        formatted_code = content
        changes_made = False

        try:
            # Use prettier via subprocess
            result = subprocess.run(
                ["npx", "prettier", "--parser", "babel", "--stdin-filepath", file_path],
                input=content,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                formatted_code = result.stdout
                changes_made = formatted_code != content
            else:
                errors.append(f"Prettier error: {result.stderr}")

        except subprocess.TimeoutExpired:
            errors.append("Prettier formatting timed out")
        except FileNotFoundError:
            warnings.append("Prettier not found, skipping formatting")
        except Exception as e:
            errors.append(f"JavaScript formatting error: {str(e)}")

        # Basic ESLint-style checks (simple regex patterns)
        self._add_js_warnings(content, warnings)

        return FormatResult(
            success=len(errors) == 0,
            formatted_code=formatted_code,
            errors=errors,
            warnings=warnings,
            changes_made=changes_made,
        )

    def _format_typescript(self, content: str, file_path: str) -> FormatResult:
        """Format TypeScript code using prettier"""
        errors = []
        warnings = []
        formatted_code = content
        changes_made = False

        try:
            # Use prettier with typescript parser
            result = subprocess.run(
                [
                    "npx",
                    "prettier",
                    "--parser",
                    "typescript",
                    "--stdin-filepath",
                    file_path,
                ],
                input=content,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                formatted_code = result.stdout
                changes_made = formatted_code != content
            else:
                errors.append(f"Prettier error: {result.stderr}")

        except subprocess.TimeoutExpired:
            errors.append("Prettier formatting timed out")
        except FileNotFoundError:
            warnings.append("Prettier not found, skipping formatting")
        except Exception as e:
            errors.append(f"TypeScript formatting error: {str(e)}")

        # Basic TypeScript checks
        self._add_ts_warnings(content, warnings)

        return FormatResult(
            success=len(errors) == 0,
            formatted_code=formatted_code,
            errors=errors,
            warnings=warnings,
            changes_made=changes_made,
        )

    def _add_js_warnings(self, content: str, warnings: list):
        """Add basic JavaScript style warnings"""
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            # Check for common issues
            if "==" in line and "===" not in line:
                warnings.append(f"Line {i}: Consider using === instead of ==")

            if "var " in line:
                warnings.append(
                    f"Line {i}: Consider using 'let' or 'const' instead of 'var'"
                )

            if (
                line.strip().endswith(";") is False
                and line.strip()
                and not line.strip().endswith("{")
                and not line.strip().endswith("}")
            ):
                if not any(
                    keyword in line
                    for keyword in [
                        "if",
                        "for",
                        "while",
                        "function",
                        "class",
                        "import",
                        "export",
                    ]
                ):
                    warnings.append(f"Line {i}: Missing semicolon")

    def _add_ts_warnings(self, content: str, warnings: list):
        """Add basic TypeScript style warnings"""
        self._add_js_warnings(content, warnings)  # Include JS warnings

        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            # Check for any type
            if ": any" in line or "<any>" in line:
                warnings.append(f"Line {i}: Avoid using 'any' type, be more specific")

# code_formatter=CodeFormatter()
# result=code_formatter.format_code(content="""def print_():\n      print(\"hi\")\nprint_()""",file_path="C:/Users/HP/Desktop/FORGRIDE/CODE/MVP/test1.py")
# print(result)
