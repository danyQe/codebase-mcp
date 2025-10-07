#ruff: noqa
"""
Symbol reading tool with bounds detection and database integration
Provides precise symbol extraction from codebase with line numbers
"""

import os
import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .models import SearchResult


class SymbolBoundsDetector:
    """Detects symbol boundaries in different programming languages"""
    
    @staticmethod
    def _leading_indent(line: str) -> int:
        """Get leading whitespace count"""
        return len(line) - len(line.lstrip(' \t'))
    
    def find_python_bounds(self, lines: List[str], start_idx: int, symbol_type: str) -> Tuple[int, int]:
        """Find bounds for Python symbols (functions, classes)"""
        n = len(lines)
        
        # Find decorators above the symbol
        start = start_idx
        while start - 1 >= 0 and lines[start - 1].lstrip().startswith('@'):
            start -= 1
        
        # Get base indentation level
        base_indent = self._leading_indent(lines[start_idx])
        
        # Find end of symbol by looking for next line with same or less indentation
        end = start_idx
        for i in range(start_idx + 1, n):
            line = lines[i]
            
            # Skip empty lines and comments
            if not line.strip() or line.lstrip().startswith('#'):
                end = i
                continue
            
            indent = self._leading_indent(line)
            
            # If we find a line with same or less indentation that's not a comment, we've found the end
            if indent <= base_indent:
                return start, i - 1
            
            end = i
        
        return start, n - 1
    
    def find_javascript_bounds(self, lines: List[str], start_idx: int, symbol_type: str) -> Tuple[int, int]:
        """Find bounds for JavaScript/TypeScript symbols"""
        n = len(lines)
        
        # Simple brace counting for JavaScript
        brace_stack = []
        opened = False
        start_line = start_idx
        
        for i in range(start_idx, n):
            line = lines[i]
            
            if not opened:
                # Look for opening brace
                if '{' in line:
                    opened = True
                    brace_stack += ['{'] * line.count('{')
                    brace_stack = brace_stack[:-line.count('}')] if line.count('}') else brace_stack
                    
                    if not brace_stack:  # Single line function
                        return start_line, i
                else:
                    # Check for single-line arrow function or declaration
                    if ';' in line or line.strip().endswith(')'):
                        return start_line, i
                    continue
            else:
                # Count braces
                for char in line:
                    if char == '{':
                        brace_stack.append('{')
                    elif char == '}':
                        if brace_stack:
                            brace_stack.pop()
                
                # If stack is empty, we've found the closing brace
                if not brace_stack:
                    return start_line, i
        
        return start_line, n - 1
    
    def find_symbol_bounds(self, lines: List[str], start_idx: int, symbol_type: str, language: str) -> Tuple[int, int]:
        """Find symbol boundaries based on language and type"""
        if language == 'python':
            return self.find_python_bounds(lines, start_idx, symbol_type)
        elif language in ['javascript', 'typescript']:
            return self.find_javascript_bounds(lines, start_idx, symbol_type)
        else:
            # Default: return just the single line
            return start_idx, start_idx


class SymbolReader:
    """Main symbol reading functionality"""
    
    def __init__(self, working_dir: str, vector_store):
        self.working_dir = Path(working_dir)
        self.vector_store = vector_store
        self.bounds_detector = SymbolBoundsDetector()
    
    def detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript', 
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, 'text')
    
    def validate_path(self, file_path: str) -> Path:
        """Validate file path is within working directory"""
        if os.path.isabs(file_path):
            abs_path = Path(file_path).resolve()
        else:
            abs_path = (self.working_dir / file_path).resolve()
        
        # Ensure path is within working directory
        if not str(abs_path).startswith(str(self.working_dir.resolve())):
            raise ValueError("Access denied: path outside working directory")
        
        return abs_path
    
    def is_binary_file(self, file_path: Path) -> bool:
        """Check if file is binary"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(2048)
                if b'\0' in chunk:
                    return True
                if not chunk:
                    return False
                text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
                nontext = sum(1 for b in chunk if b not in text_chars)
                return (nontext / len(chunk)) > 0.30
        except Exception:
            return True
    
    def find_symbol_in_database(self, symbol_name: str, file_path: Optional[str] = None) -> List[SearchResult]:
        """Find symbol occurrences in the database"""
        try:
            conn = sqlite3.connect(self.vector_store.metadata_db)
            
            # Build query
            query = """
                SELECT chunk_id, file_path, symbol_name, line_start, line_end, 
                       signature, docstring, chunk_type
                FROM chunks 
                WHERE symbol_name = ?
            """
            params = [symbol_name]
            
            if file_path:
                query += " AND file_path = ?"
                params.append(file_path)
            
            query += " ORDER BY file_path, line_start"
            
            cursor = conn.execute(query, params)
            results = []
            
            for row in cursor.fetchall():
                chunk_id, file_path, symbol_name, line_start, line_end, signature, docstring, chunk_type = row
                results.append(SearchResult(
                    chunk_id=chunk_id,
                    file_path=file_path,
                    symbol_name=symbol_name,
                    line_start=line_start,
                    line_end=line_end,
                    signature=signature,
                    docstring=docstring,
                    relevance_score=1.0,
                    chunk_type=chunk_type,
                ))
            
            conn.close()
            return results
            
        except Exception as e:
            print(f"Database search error: {e}")
            return []
    
    def read_code_content(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        symbol_name: Optional[str] = None,
        occurrence: int = 1,
        with_line_numbers: bool = True
    ) -> Dict[str, Any]:
        """
        Read code content with multiple modes:
        - Line range (start_line & end_line)
        - Symbol name (function/class/interface)
        - Whole file (default)
        """
        try:
            abs_path = self.validate_path(file_path)
            
            if not abs_path.exists():
                return {
                    "success": False,
                    "error": f"File not found: {file_path}"
                }
            
            if self.is_binary_file(abs_path):
                return {
                    "success": False,
                    "error": f"Binary file: {file_path}"
                }
            
            # Read file content
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.read().splitlines()
            
            selected_lines = []
            line_offset = 1
            mode = "whole_file"
            
            # Case 1: Line range
            if start_line is not None and end_line is not None:
                if start_line < 1 or end_line < 1 or end_line > len(lines) or start_line > end_line:
                    return {
                        "success": False,
                        "error": f"Invalid line range: {start_line}-{end_line} (file has {len(lines)} lines)"
                    }
                
                selected_lines = lines[start_line - 1:end_line]
                line_offset = start_line
                mode = "line_range"
            
            # Case 2: Symbol lookup
            elif symbol_name:
                language = self.detect_language(file_path)
                symbol_matches = []
                
                # Search for symbol in current file using database
                db_results = self.find_symbol_in_database(symbol_name, file_path)
                
                if db_results:
                    # Use database results for more accurate symbol detection
                    if occurrence < 1 or occurrence > len(db_results):
                        return {
                            "success": False,
                            "error": f"Invalid occurrence: {occurrence} (found {len(db_results)} matches)"
                        }
                    
                    # Get the specific occurrence
                    target_symbol = db_results[occurrence - 1]
                    start_idx = target_symbol.line_start - 1
                    
                    # Use bounds detection to get precise symbol boundaries
                    start, end = self.bounds_detector.find_symbol_bounds(
                        lines, start_idx, target_symbol.chunk_type, language
                    )
                    
                    selected_lines = lines[start:end + 1]
                    line_offset = start + 1
                    mode = f"symbol_db_{target_symbol.chunk_type}"
                else:
                    # Fallback to pattern matching if not in database
                    symbol_patterns = {
                        'python': [
                            (re.compile(r'^\s*def\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
                            (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(:|\(|$)'), 'class'),
                            (re.compile(r'^\s*async\s+def\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
                        ],
                        'javascript': [
                            (re.compile(r'^\s*function\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
                            (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*\('), 'function'),
                            (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(?:\{|extends|$)'), 'class'),
                        ],
                        'typescript': [
                            (re.compile(r'^\s*function\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
                            (re.compile(r'^\s*interface\s+([a-zA-Z_][\w_]*)\s*\{'), 'interface'),
                            (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(?:\{|extends|$)'), 'class'),
                        ],
                    }
                    
                    if language in symbol_patterns:
                        for line_num, line in enumerate(lines):
                            for pattern, symbol_type in symbol_patterns[language]:
                                match = pattern.match(line)
                                if match and match.group(1) == symbol_name:
                                    symbol_matches.append((line_num, symbol_type))
                    
                    if not symbol_matches:
                        return {
                            "success": False,
                            "error": f"Symbol '{symbol_name}' not found in {file_path}"
                        }
                    
                    if occurrence < 1 or occurrence > len(symbol_matches):
                        return {
                            "success": False,
                            "error": f"Invalid occurrence: {occurrence} (found {len(symbol_matches)} matches)"
                        }
                    
                    start_idx, symbol_type = symbol_matches[occurrence - 1]
                    start, end = self.bounds_detector.find_symbol_bounds(
                        lines, start_idx, symbol_type, language
                    )
                    
                    selected_lines = lines[start:end + 1]
                    line_offset = start + 1
                    mode = f"symbol_pattern_{symbol_type}"
            
            # Case 3: Whole file
            else:
                selected_lines = lines
                line_offset = 1
                mode = "whole_file"
            
            # Format output
            if with_line_numbers:
                width = len(str(line_offset + len(selected_lines) - 1))
                formatted_lines = []
                for i, line in enumerate(selected_lines):
                    line_num = str(i + line_offset).rjust(width)
                    formatted_lines.append(f"{line_num} | {line}")
                content = "\n".join(formatted_lines)
            else:
                content = "\n".join(selected_lines)
            
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "mode": mode,
                "line_range": {
                    "start": line_offset,
                    "end": line_offset + len(selected_lines) - 1,
                    "total_lines": len(selected_lines)
                },
                "file_stats": {
                    "total_file_lines": len(lines),
                    "file_size": abs_path.stat().st_size
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error reading code: {str(e)}"
            }
