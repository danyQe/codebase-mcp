"""Dependency analysis using structured codebase data"""

import ast
import re
import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from semantic_search.core import SemanticSearchEngine


@dataclass
class DependencyInfo:
    """Information about a dependency/import"""

    name: str
    import_type: str  # "import", "from_import", "es6_import", "require"
    source: Optional[str] = None  # Module/file being imported from
    alias: Optional[str] = None
    line_number: int = 0


@dataclass
class SymbolLocation:
    """Where a symbol is defined in the codebase"""

    symbol_name: str
    file_path: str
    chunk_type: str  # function, class, interface, etc.
    line_start: int
    line_end: int
    signature: Optional[str] = None


@dataclass
class DependencyCheckResult:
    """Result of dependency checking"""

    success: bool
    imports_found: List[DependencyInfo]
    resolved_symbols: List[SymbolLocation]  # Symbols found in codebase
    missing_dependencies: List[str]
    duplicate_definitions: List[str]  # Symbols defined multiple times
    suggestions: List[str]
    warnings: List[str]
    errors: List[str]


class DependencyChecker:
    """Analyzes dependencies using structured codebase data"""

    def __init__(self, search_engine: Optional[SemanticSearchEngine] = None):
        self.search_engine = search_engine

        # Standard library modules
        self.python_stdlib = {
            "os",
            "sys",
            "json",
            "pathlib",
            "typing",
            "datetime",
            "asyncio",
            "logging",
            "collections",
            "itertools",
            "functools",
            "dataclasses",
            "enum",
            "re",
            "math",
            "random",
            "uuid",
            "hashlib",
            "base64",
            "urllib",
            "http",
            "socket",
            "threading",
            "multiprocessing",
        }

        self.node_builtins = {
            "fs",
            "path",
            "os",
            "url",
            "util",
            "events",
            "stream",
            "http",
            "https",
            "crypto",
            "buffer",
            "process",
            "cluster",
            "child_process",
        }

    async def check_dependencies(
        self, content: str, file_path: str, language: Optional[str] = None
    ) -> DependencyCheckResult:
        """Check dependencies using structured codebase analysis"""

        file_ext = Path(file_path).suffix.lower()

        if language:
            if language.lower() == "python":
                return await self._check_python_dependencies(content, file_path)
            elif language.lower() in ["javascript", "typescript", "js", "ts"]:
                return await self._check_js_dependencies(content, file_path)

        # Auto-detect from extension
        if file_ext == ".py":
            return await self._check_python_dependencies(content, file_path)
        elif file_ext in [".js", ".jsx", ".ts", ".tsx"]:
            return await self._check_js_dependencies(content, file_path)
        else:
            return DependencyCheckResult(
                success=True,
                imports_found=[],
                resolved_symbols=[],
                missing_dependencies=[],
                duplicate_definitions=[],
                suggestions=[],
                warnings=[f"Dependency checking not supported for {file_ext}"],
                errors=[],
            )

    async def _check_python_dependencies(
        self, content: str, file_path: str
    ) -> DependencyCheckResult:
        """Check Python dependencies using AST + codebase analysis"""
        imports_found = []
        resolved_symbols = []
        missing_dependencies = []
        duplicate_definitions = []
        suggestions = []
        warnings = []
        errors = []

        try:
            tree = ast.parse(content)

            # Extract all imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports_found.append(
                            DependencyInfo(
                                name=alias.name,
                                import_type="import",
                                alias=alias.asname,
                                line_number=node.lineno,
                            )
                        )

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for alias in node.names:
                            imports_found.append(
                                DependencyInfo(
                                    name=alias.name,
                                    import_type="from_import",
                                    source=node.module,
                                    alias=alias.asname,
                                    line_number=node.lineno,
                                )
                            )

            # Analyze each import against the codebase
            for imp in imports_found:
                await self._analyze_python_import(
                    imp,
                    resolved_symbols,
                    missing_dependencies,
                    duplicate_definitions,
                    suggestions,
                    warnings,
                    file_path,
                )

        except SyntaxError as e:
            errors.append(f"Python syntax error: {str(e)}")
        except Exception as e:
            errors.append(f"Error analyzing Python dependencies: {str(e)}")

        return DependencyCheckResult(
            success=len(errors) == 0,
            imports_found=imports_found,
            resolved_symbols=resolved_symbols,
            missing_dependencies=missing_dependencies,
            duplicate_definitions=duplicate_definitions,
            suggestions=suggestions,
            warnings=warnings,
            errors=errors,
        )

    async def _check_js_dependencies(
        self, content: str, file_path: str
    ) -> DependencyCheckResult:
        """Check JS/TS dependencies using regex + codebase analysis"""
        imports_found = []
        resolved_symbols = []
        missing_dependencies = []
        duplicate_definitions = []
        suggestions = []
        warnings = []
        errors = []

        try:
            lines = content.split("\n")

            # ES6 and CommonJS import patterns
            es6_import_pattern = re.compile(
                r'import\s+(?:([{]([^}]+)[}])|(\w+)|\*\s+as\s+(\w+))\s+from\s+["\']([^"\']+)["\']'
            )
            require_pattern = re.compile(
                r'(?:const|let|var)\s+(?:[{]([^}]+)[}]|(\w+))\s*=\s*require\(["\']([^"\']+)["\']\)'
            )

            # Extract imports
            for i, line in enumerate(lines, 1):
                # ES6 imports
                for match in es6_import_pattern.finditer(line):
                    source = match.group(5)

                    if match.group(2):  # Named imports
                        names = [name.strip() for name in match.group(2).split(",")]
                        for name in names:
                            imports_found.append(
                                DependencyInfo(
                                    name=name,
                                    import_type="es6_import",
                                    source=source,
                                    line_number=i,
                                )
                            )
                    elif match.group(3):  # Default import
                        imports_found.append(
                            DependencyInfo(
                                name=match.group(3),
                                import_type="es6_import",
                                source=source,
                                line_number=i,
                            )
                        )
                    elif match.group(4):  # Namespace import
                        imports_found.append(
                            DependencyInfo(
                                name=match.group(4),
                                import_type="es6_import",
                                source=source,
                                line_number=i,
                            )
                        )

                # CommonJS requires
                for match in require_pattern.finditer(line):
                    source = match.group(3)

                    if match.group(1):  # Destructured
                        names = [name.strip() for name in match.group(1).split(",")]
                        for name in names:
                            imports_found.append(
                                DependencyInfo(
                                    name=name,
                                    import_type="require",
                                    source=source,
                                    line_number=i,
                                )
                            )
                    elif match.group(2):  # Direct require
                        imports_found.append(
                            DependencyInfo(
                                name=match.group(2),
                                import_type="require",
                                source=source,
                                line_number=i,
                            )
                        )

            # Analyze against codebase
            for imp in imports_found:
                await self._analyze_js_import(
                    imp,
                    resolved_symbols,
                    missing_dependencies,
                    duplicate_definitions,
                    suggestions,
                    warnings,
                    file_path,
                )

        except Exception as e:
            errors.append(f"Error analyzing JS/TS dependencies: {str(e)}")

        return DependencyCheckResult(
            success=len(errors) == 0,
            imports_found=imports_found,
            resolved_symbols=resolved_symbols,
            missing_dependencies=missing_dependencies,
            duplicate_definitions=duplicate_definitions,
            suggestions=suggestions,
            warnings=warnings,
            errors=errors,
        )

    async def _analyze_python_import(
        self,
        imp: DependencyInfo,
        resolved_symbols: List[SymbolLocation],
        missing_deps: List[str],
        duplicate_defs: List[str],
        suggestions: List[str],
        warnings: List[str],
        current_file: str,
    ):
        """Analyze Python import against structured codebase data"""

        module_name = imp.source or imp.name
        root_module = module_name.split(".")[0]

        # Skip standard library
        if root_module in self.python_stdlib:
            return

        # Handle relative imports
        if module_name.startswith("."):
            await self._check_relative_python_import(
                imp, resolved_symbols, missing_deps, suggestions, current_file
            )
            return

        # Check for symbols in the codebase using exact queries
        if imp.import_type == "from_import":
            # Importing specific symbol from module
            symbol_name = imp.name
            locations = await self._find_symbol_in_codebase(symbol_name)

            if locations:
                resolved_symbols.extend(locations)

                # Check for duplicates
                if len(locations) > 1:
                    duplicate_defs.append(
                        f"{symbol_name} defined in {len(locations)} places: "
                        + ", ".join(
                            [f"{loc.file_path}:{loc.line_start}" for loc in locations]
                        )
                    )
                    suggestions.append(
                        f"Consider consolidating {symbol_name} definitions"
                    )

                # Check if importing from correct module
                expected_module_paths = [loc.file_path for loc in locations]
                if not any(
                    module_name.replace(".", "/") in path
                    for path in expected_module_paths
                ):
                    suggestions.append(
                        f"Import {symbol_name} from {expected_module_paths[0]} instead of {module_name}"
                    )
            else:
                # Symbol not found in codebase
                missing_deps.append(f"Symbol '{symbol_name}' not found in codebase")

                # Check if similar symbols exist (typo detection)
                similar_symbols = await self._find_similar_symbols(symbol_name)
                if similar_symbols:
                    suggestions.append(
                        f"Did you mean {similar_symbols[0].symbol_name}? Found in {similar_symbols[0].file_path}"
                    )
        else:
            # Importing entire module
            module_files = await self._find_module_files(module_name)
            if module_files:
                # Module exists in codebase
                for file_path in module_files:
                    resolved_symbols.append(
                        SymbolLocation(
                            symbol_name=module_name,
                            file_path=file_path,
                            chunk_type="module",
                            line_start=1,
                            line_end=1,
                        )
                    )
            else:
                # External module
                missing_deps.append(f"Module '{module_name}' not found in codebase")
                suggestions.append(
                    f"Add {root_module} to requirements.txt if it's a third-party package"
                )

    async def _analyze_js_import(
        self,
        imp: DependencyInfo,
        resolved_symbols: List[SymbolLocation],
        missing_deps: List[str],
        duplicate_defs: List[str],
        suggestions: List[str],
        warnings: List[str],
        current_file: str,
    ):
        """Analyze JS/TS import against structured codebase data"""

        source = imp.source
        if not source:
            return

        # Skip Node.js built-ins
        if source in self.node_builtins:
            return

        # Handle relative imports
        if source.startswith("./") or source.startswith("../"):
            await self._check_relative_js_import(
                imp, resolved_symbols, missing_deps, suggestions, current_file
            )
            return

        # Check for symbols in codebase
        symbol_name = imp.name
        locations = await self._find_symbol_in_codebase(symbol_name)

        if locations:
            resolved_symbols.extend(locations)

            # Check for duplicates
            if len(locations) > 1:
                duplicate_defs.append(
                    f"{symbol_name} defined in {len(locations)} places"
                )
        else:
            # Check if it's an npm package
            if source.startswith("@") or not source.startswith("."):
                missing_deps.append(f"External package: {source}")
                suggestions.append(f"Ensure {source} is in package.json dependencies")
            else:
                missing_deps.append(f"Symbol '{symbol_name}' not found")

    async def _find_symbol_in_codebase(self, symbol_name: str) -> List[SymbolLocation]:
        """Find symbol definitions in the codebase using direct SQLite queries"""
        if not self.search_engine or not self.search_engine.vector_store:
            return []

        try:
            db_path = self.search_engine.vector_store.metadata_db
            conn = sqlite3.connect(db_path)

            cursor = conn.execute(
                """
                SELECT symbol_name, file_path, chunk_type, line_start, line_end, signature
                FROM chunks 
                WHERE symbol_name = ? AND chunk_type IN ('function', 'class', 'interface')
                ORDER BY file_path, line_start
                """,
                (symbol_name,),
            )

            locations = []
            for row in cursor.fetchall():
                symbol, file_path, chunk_type, line_start, line_end, signature = row
                locations.append(
                    SymbolLocation(
                        symbol_name=symbol,
                        file_path=file_path,
                        chunk_type=chunk_type,
                        line_start=line_start,
                        line_end=line_end,
                        signature=signature,
                    )
                )

            conn.close()
            return locations

        except Exception as e:
            print(f"Error querying symbol {symbol_name}: {e}")
            return []

    async def _find_similar_symbols(
        self, symbol_name: str, max_distance: int = 2
    ) -> List[SymbolLocation]:
        """Find symbols with similar names (basic Levenshtein-like matching)"""
        if not self.search_engine or not self.search_engine.vector_store:
            return []

        try:
            db_path = self.search_engine.vector_store.metadata_db
            conn = sqlite3.connect(db_path)

            # Get all symbols and do basic similarity matching
            cursor = conn.execute(
                """
                SELECT symbol_name, file_path, chunk_type, line_start, line_end, signature
                FROM chunks 
                WHERE symbol_name IS NOT NULL AND chunk_type IN ('function', 'class', 'interface')
                """
            )

            similar = []
            for row in cursor.fetchall():
                existing_symbol = row[0]
                if existing_symbol and self._is_similar(
                    symbol_name, existing_symbol, max_distance
                ):
                    similar.append(
                        SymbolLocation(
                            symbol_name=existing_symbol,
                            file_path=row[1],
                            chunk_type=row[2],
                            line_start=row[3],
                            line_end=row[4],
                            signature=row[5],
                        )
                    )

            conn.close()
            return similar[:3]  # Return top 3 matches

        except Exception:
            return []

    async def _find_module_files(self, module_name: str) -> List[str]:
        """Find files that could represent this module"""
        if not self.search_engine or not self.search_engine.vector_store:
            return []

        try:
            db_path = self.search_engine.vector_store.metadata_db
            conn = sqlite3.connect(db_path)

            # Look for files that match module name pattern
            module_path = module_name.replace(".", "/")
            cursor = conn.execute(
                """
                SELECT DISTINCT file_path FROM chunks 
                WHERE file_path LIKE ? OR file_path LIKE ?
                """,
                (f"%{module_path}.py", f"%{module_path}/__init__.py"),
            )

            files = [row[0] for row in cursor.fetchall()]
            conn.close()
            return files

        except Exception:
            return []

    async def _get_file_imports(self, file_path: str) -> List[str]:
        """Get all imports from a file's overview chunk"""
        if not self.search_engine or not self.search_engine.vector_store:
            return []

        try:
            db_path = self.search_engine.vector_store.metadata_db
            conn = sqlite3.connect(db_path)

            cursor = conn.execute(
                """
                SELECT content FROM chunks 
                WHERE file_path = ? AND chunk_type = 'file_overview'
                """,
                (file_path,),
            )

            row = cursor.fetchone()
            if row:
                try:
                    overview_data = json.loads(row[0])
                    return overview_data.get("imports", [])
                except json.JSONDecodeError:
                    pass

            conn.close()
            return []

        except Exception:
            return []

    async def _check_relative_python_import(
        self,
        imp: DependencyInfo,
        resolved_symbols: List[SymbolLocation],
        missing_deps: List[str],
        suggestions: List[str],
        current_file: str,
    ):
        """Check Python relative imports"""
        # Convert relative import to absolute path
        relative_path = self._resolve_python_relative_import(imp.source, current_file)

        # Check if the target file exists in codebase
        module_files = await self._find_module_files(relative_path)
        if module_files:
            resolved_symbols.append(
                SymbolLocation(
                    symbol_name=imp.name,
                    file_path=module_files[0],
                    chunk_type="module",
                    line_start=1,
                    line_end=1,
                )
            )
        else:
            missing_deps.append(f"Relative import not found: {imp.source}")

    async def _check_relative_js_import(
        self,
        imp: DependencyInfo,
        resolved_symbols: List[SymbolLocation],
        missing_deps: List[str],
        suggestions: List[str],
        current_file: str,
    ):
        """Check JS/TS relative imports"""
        # Resolve relative path
        relative_path = self._resolve_js_relative_import(imp.source, current_file)

        # Check if file exists (try common extensions)
        for ext in [".js", ".ts", ".jsx", ".tsx"]:
            test_path = relative_path + ext
            module_files = await self._find_module_files(test_path.replace("/", "."))
            if module_files:
                resolved_symbols.append(
                    SymbolLocation(
                        symbol_name=imp.name,
                        file_path=module_files[0],
                        chunk_type="module",
                        line_start=1,
                        line_end=1,
                    )
                )
                return

        missing_deps.append(f"Relative import not found: {imp.source}")

    def _resolve_python_relative_import(
        self, relative_import: str, current_file: str
    ) -> str:
        """Convert Python relative import to module path"""
        current_dir = Path(current_file).parent

        if relative_import.startswith(".."):
            # Handle multiple levels: ..module, ...module, etc.
            parts = relative_import.split(".")
            level = len([p for p in parts if p == ""])  # Count empty parts (dots)
            module_parts = [p for p in parts if p]

            # Go up directories
            target_dir = current_dir
            for _ in range(level - 1):
                target_dir = target_dir.parent

            # Build module path
            if module_parts:
                return ".".join(module_parts)
        else:
            # Single dot relative
            return relative_import[1:]  # Remove leading dot

        return relative_import

    def _resolve_js_relative_import(
        self, relative_import: str, current_file: str
    ) -> str:
        """Convert JS relative import to file path"""
        current_dir = Path(current_file).parent

        if relative_import.startswith("./"):
            return str(current_dir / relative_import[2:])
        elif relative_import.startswith("../"):
            parts = relative_import.split("/")
            target_dir = current_dir

            for part in parts:
                if part == "..":
                    target_dir = target_dir.parent
                elif part and part != ".":
                    target_dir = target_dir / part

            return str(target_dir)

        return relative_import

    def _is_similar(self, str1: str, str2: str, max_distance: int) -> bool:
        """Basic similarity check (simplified Levenshtein)"""
        if abs(len(str1) - len(str2)) > max_distance:
            return False

        # Simple character difference count
        min_len = min(len(str1), len(str2))
        differences = sum(1 for i in range(min_len) if str1[i] != str2[i])
        differences += abs(len(str1) - len(str2))

        return differences <= max_distance
