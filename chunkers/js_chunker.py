"""JavaScript/TypeScript chunker using regex patterns"""

import re
import json
from typing import List, Optional, Match
from .base import BaseChunker
from semantic_search.models import ChunkData


class JSChunker(BaseChunker):
    """Regex-based JavaScript/TypeScript chunker"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = {".js", ".ts", ".jsx", ".tsx"}

        # Regex patterns for different constructs
        self.function_pattern = re.compile(
            r"(export\s+)?(async\s+)?function\s+(\w+)\s*\([^)]*\)\s*[:{]", re.MULTILINE
        )
        self.arrow_function_pattern = re.compile(
            r"(export\s+)?(const|let|var)\s+(\w+)\s*=\s*(async\s+)?\([^)]*\)\s*=>\s*[{]",
            re.MULTILINE,
        )
        self.class_pattern = re.compile(
            r"(export\s+)?(abstract\s+)?class\s+(\w+)(\s+extends\s+\w+)?(\s+implements\s+[\w,\s]+)?\s*[{]",
            re.MULTILINE,
        )
        self.interface_pattern = re.compile(
            r"(export\s+)?interface\s+(\w+)(\s+extends\s+[\w,\s]+)?\s*[{]", re.MULTILINE
        )
        self.import_pattern = re.compile(
            r'import\s+(?:[{]([^}]+)[}]|(\w+)|\*\s+as\s+(\w+))\s+from\s+["\']([^"\']+)["\']',
            re.MULTILINE,
        )

    async def chunk_file(self, file_path: str, content: str) -> List[ChunkData]:
        """Extract chunks from JavaScript/TypeScript file"""
        try:
            chunks = []
            lines = content.split("\n")

            # File overview
            file_overview = self._create_file_overview(content, file_path, lines)
            chunks.append(file_overview)

            # Find functions
            for match in self.function_pattern.finditer(content):
                chunk = self._create_function_chunk(
                    match, content, file_path, lines, "function"
                )
                if chunk:
                    chunks.append(chunk)

            # Find arrow functions
            for match in self.arrow_function_pattern.finditer(content):
                chunk = self._create_function_chunk(
                    match, content, file_path, lines, "arrow_function"
                )
                if chunk:
                    chunks.append(chunk)

            # Find classes
            for match in self.class_pattern.finditer(content):
                chunk = self._create_class_chunk(match, content, file_path, lines)
                if chunk:
                    chunks.append(chunk)

            # Find interfaces (TypeScript)
            if file_path.endswith((".ts", ".tsx")):
                for match in self.interface_pattern.finditer(content):
                    chunk = self._create_interface_chunk(
                        match, content, file_path, lines
                    )
                    if chunk:
                        chunks.append(chunk)

            return chunks

        except Exception as e:
            # Return error chunk
            return [
                ChunkData(
                    chunk_id=self._generate_chunk_id(file_path, "parse_error", 1),
                    file_path=file_path,
                    chunk_type="error",
                    symbol_name="parse_error",
                    line_start=1,
                    line_end=1,
                    content=f"Parse error: {str(e)}",
                )
            ]

    def _create_file_overview(
        self, content: str, file_path: str, lines: List[str]
    ) -> ChunkData:
        """Create file overview chunk"""
        imports = []
        functions = []
        classes = []
        interfaces = []

        # Extract imports
        for match in self.import_pattern.finditer(content):
            module = match.group(4)
            imports.append(module)

        # Extract function names
        for match in self.function_pattern.finditer(content):
            functions.append(match.group(3))

        for match in self.arrow_function_pattern.finditer(content):
            functions.append(match.group(3))

        # Extract class names
        for match in self.class_pattern.finditer(content):
            classes.append(match.group(3))

        # Extract interface names (TypeScript)
        for match in self.interface_pattern.finditer(content):
            interfaces.append(match.group(2))

        file_type = (
            "typescript" if file_path.endswith((".ts", ".tsx")) else "javascript"
        )
        if file_path.endswith((".jsx", ".tsx")):
            file_type += "_react"

        overview_content = {
            "file_type": file_type,
            "imports": imports,
            "functions": functions,
            "classes": classes,
            "interfaces": interfaces,
            "total_lines": len(lines),
        }

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, "file_overview", 1),
            file_path=file_path,
            chunk_type="file_overview",
            symbol_name="file_overview",
            line_start=1,
            line_end=len(lines),
            content=json.dumps(overview_content, indent=2),
        )

    def _create_function_chunk(
        self,
        match: Match,
        content: str,
        file_path: str,
        lines: List[str],
        func_type: str,
    ) -> Optional[ChunkData]:
        """Create function chunk"""
        start_pos = match.start()
        line_start = content[:start_pos].count("\n") + 1

        # Find function end by matching braces
        brace_count = 0
        pos = match.end() - 1  # Start from the opening brace
        while pos < len(content):
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        line_end = content[: pos + 1].count("\n") + 1

        # Extract function name
        if func_type == "function":
            func_name = match.group(3)
        else:  # arrow function
            func_name = match.group(3)

        # Extract function content
        func_content = self._extract_content_lines(content, line_start, line_end)

        # Extract signature (first line)
        signature = lines[line_start - 1].strip()

        # Try to extract JSDoc comment
        docstring = self._extract_jsdoc(lines, line_start - 1)

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, func_name, line_start),
            file_path=file_path,
            chunk_type="function",
            symbol_name=func_name,
            line_start=line_start,
            line_end=line_end,
            content=func_content,
            signature=signature,
            docstring=docstring,
        )

    def _create_class_chunk(
        self, match: Match, content: str, file_path: str, lines: List[str]
    ) -> Optional[ChunkData]:
        """Create class chunk"""
        start_pos = match.start()
        line_start = content[:start_pos].count("\n") + 1

        # Find class end by matching braces
        brace_count = 0
        pos = match.end() - 1
        while pos < len(content):
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        line_end = content[: pos + 1].count("\n") + 1

        class_name = match.group(3)
        signature = lines[line_start - 1].strip()

        # Extract methods from class body
        class_content_str = content[match.end() : pos]
        methods = re.findall(r"(\w+)\s*\([^)]*\)\s*[:{]", class_content_str)

        class_info = {
            "name": class_name,
            "methods": methods,
            "extends": match.group(4).strip() if match.group(4) else None,
        }

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, class_name, line_start),
            file_path=file_path,
            chunk_type="class",
            symbol_name=class_name,
            line_start=line_start,
            line_end=line_end,
            content=json.dumps(class_info, indent=2),
            signature=signature,
        )

    def _create_interface_chunk(
        self, match: Match, content: str, file_path: str, lines: List[str]
    ) -> Optional[ChunkData]:
        """Create interface chunk (TypeScript)"""
        start_pos = match.start()
        line_start = content[:start_pos].count("\n") + 1

        # Find interface end
        brace_count = 0
        pos = match.end() - 1
        while pos < len(content):
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
                if brace_count == 0:
                    break
            pos += 1

        line_end = content[: pos + 1].count("\n") + 1

        interface_name = match.group(2)
        signature = lines[line_start - 1].strip()

        interface_content = self._extract_content_lines(content, line_start, line_end)

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, interface_name, line_start),
            file_path=file_path,
            chunk_type="interface",
            symbol_name=interface_name,
            line_start=line_start,
            line_end=line_end,
            content=interface_content,
            signature=signature,
        )

    def _extract_jsdoc(self, lines: List[str], func_line: int) -> Optional[str]:
        """Extract JSDoc comment above function"""
        # Look backwards for JSDoc comment
        for i in range(func_line - 1, max(0, func_line - 10), -1):
            line = lines[i].strip()
            if line.startswith("/**"):
                # Found JSDoc start, collect until */
                doc_lines = []
                for j in range(i, func_line):
                    doc_line = lines[j].strip()
                    if doc_line.startswith("*"):
                        doc_line = doc_line[1:].strip()
                    doc_lines.append(doc_line)
                    if doc_line.endswith("*/"):
                        break
                return "\n".join(doc_lines)
            elif line and not line.startswith("//"):
                # Hit non-comment code, stop looking
                break
        return None
