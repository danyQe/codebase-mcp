"""Python AST-based chunker"""

import ast
import json
from typing import List, Optional,Union
from .base import BaseChunker
from semantic_search.models import ChunkData


class PythonChunker(BaseChunker):
    """AST-based Python code chunker"""

    def __init__(self):
        super().__init__()
        self.supported_extensions = {".py"}

    async def chunk_file(self, file_path: str, content: str) -> List[ChunkData]:
        """Extract chunks from Python file"""
        try:
            tree = ast.parse(content, filename=file_path)
            chunks = []

            # File overview chunk
            file_overview = self._create_file_overview(tree, file_path, content)
            chunks.append(file_overview)

            # Function and class chunks
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Only top-level functions or class methods
                    chunk = self._create_function_chunk(node, file_path, content)
                    if chunk:
                        chunks.append(chunk)

                elif isinstance(node, ast.ClassDef):
                    # Top-level classes only
                    if node.col_offset == 0:
                        chunk = self._create_class_chunk(node, file_path, content)
                        if chunk:
                            chunks.append(chunk)

            return chunks

        except SyntaxError as e:
            # Return error chunk for unparseable files
            return [
                ChunkData(
                    chunk_id=self._generate_chunk_id(file_path, "syntax_error", 1),
                    file_path=file_path,
                    chunk_type="error",
                    symbol_name="syntax_error",
                    line_start=1,
                    line_end=1,
                    content=f"Syntax error: {str(e)}",
                )
            ]

    def _create_file_overview(
        self, tree: ast.Module, file_path: str, content: str
    ) -> ChunkData:
        """Create file-level overview chunk"""
        imports = []
        functions = []
        classes = []

        # Extract top-level elements
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(f"{node.module}")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)

        overview_content = {
            "file_type": "python",
            "imports": imports,
            "functions": functions,
            "classes": classes,
            "total_lines": len(content.split("\n")),
        }

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, "file_overview", 1),
            file_path=file_path,
            chunk_type="file_overview",
            symbol_name="file_overview",
            line_start=1,
            line_end=len(content.split("\n")),
            content=json.dumps(overview_content, indent=2),
        )

    def _create_function_chunk(
        self, node: Union[ast.FunctionDef,ast.AsyncFunctionDef], file_path: str, content: str
    ) -> Optional[ChunkData]:
        """Create chunk for function/method"""
        if not node.lineno or not node.end_lineno:
            return None

        # Extract docstring
        docstring = None
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            docstring = node.body[0].value.value

        # Build signature
        signature = self._build_function_signature(node)

        # Extract function content
        func_content = self._extract_content_lines(
            content, node.lineno, node.end_lineno
        )

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, node.name, node.lineno),
            file_path=file_path,
            chunk_type="function",
            symbol_name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno,
            content=func_content,
            signature=signature,
            docstring=str(docstring),
        )

    def _create_class_chunk(
        self, node: ast.ClassDef, file_path: str, content: str
    ) -> Optional[ChunkData]:
        """Create chunk for class"""
        if not node.lineno or not node.end_lineno:
            return None

        # Extract docstring
        docstring = None
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            docstring = node.body[0].value.value

        # Extract methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        # Build signature with inheritance
        bases = (
            [ast.unparse(base) for base in node.bases]
            if hasattr(ast, "unparse")
            else []
        )
        signature = f"class {node.name}"
        if bases:
            signature += f"({', '.join(bases)})"

        # Class content (just signature and methods for overview)
        class_content = {
            "name": node.name,
            "methods": methods,
            "inheritance": bases,
            "docstring": docstring,
        }

        return ChunkData(
            chunk_id=self._generate_chunk_id(file_path, node.name, node.lineno),
            file_path=file_path,
            chunk_type="class",
            symbol_name=node.name,
            line_start=node.lineno,
            line_end=node.end_lineno,
            content=json.dumps(class_content, indent=2),
            signature=signature,
            docstring=str(docstring),
        )

    def _build_function_signature(self, node: Union[ast.FunctionDef,ast.AsyncFunctionDef]) -> str:
        """Build function signature string"""
        args = []

        # Regular arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if hasattr(ast, "unparse") and arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        # Add defaults handling could go here

        signature = f"def {node.name}({', '.join(args)})"

        # Return type
        if hasattr(ast, "unparse") and node.returns:
            signature += f" -> {ast.unparse(node.returns)}"

        return signature
