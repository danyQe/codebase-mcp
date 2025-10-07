"""
Enhanced search functionality with fuzzy matching, text search, and symbol operations
Integrates with existing semantic search system
"""

import re
import os
import fnmatch
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from .models import SearchRequest, SearchResult


class SymbolMatcher:
    """Symbol pattern matching and detection"""
    
    # Language-specific symbol patterns
    SYMBOL_PATTERNS = {
        'python': [
            (re.compile(r'^\s*def\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
            (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(:|\(|$)'), 'class'),
            (re.compile(r'^\s*async\s+def\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
        ],
        'javascript': [
            (re.compile(r'^\s*function\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
            (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*\('), 'function'),
            (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(?:\{|extends|$)'), 'class'),
            (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*[^=]*=>'), 'function'),
            (re.compile(r'^\s*([a-zA-Z_][\w_]*)\s*:\s*function\s*\('), 'function'),  # Object methods
        ],
        'typescript': [
            (re.compile(r'^\s*function\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
            (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*[^=]*=>'), 'function'),
            (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(?:\{|extends|$)'), 'class'),
            (re.compile(r'^\s*interface\s+([a-zA-Z_][\w_]*)\s*\{'), 'interface'),
            (re.compile(r'^\s*type\s+([a-zA-Z_][\w_]*)\s*='), 'type'),
            (re.compile(r'^\s*enum\s+([a-zA-Z_][\w_]*)\s*\{'), 'enum'),
        ],
    }
    
    @staticmethod
    def detect_language(file_path: str) -> str:
        """Detect language from file extension"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript', 
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, 'text')
    
    def extract_symbols(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Extract symbols from file content"""
        language = self.detect_language(file_path)
        if language not in self.SYMBOL_PATTERNS:
            return []
        
        symbols = []
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern, symbol_type in self.SYMBOL_PATTERNS[language]:
                match = pattern.match(line)
                if match:
                    symbol_name = match.group(1)
                    symbols.append({
                        'name': symbol_name,
                        'type': symbol_type,
                        'line': line_num,
                        'file': file_path
                    })
        
        return symbols


class TextSearcher:
    """Text-based search with pattern and regex support"""
    
    @staticmethod
    def should_ignore_file(file_path: str, gitignore_patterns: List[str]) -> bool:
        """Check if file should be ignored based on gitignore patterns"""
        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build'}
        ignore_files = {'.gitignore', '.env', '.DS_Store'}
        
        path_parts = Path(file_path).parts
        
        # Check ignore directories
        for part in path_parts:
            if part in ignore_dirs:
                return True
        
        # Check ignore files
        if Path(file_path).name in ignore_files:
            return True
        
        # Check gitignore patterns
        for pattern in gitignore_patterns:
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(Path(file_path).name, pattern):
                return True
        
        return False
    
    def load_gitignore_patterns(self, working_dir: str) -> List[str]:
        """Load gitignore patterns from .gitignore file"""
        gitignore_path = Path(working_dir) / '.gitignore'
        patterns = []
        
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except Exception:
                pass
        
        return patterns
    
    def search_in_files(
        self, 
        working_dir: str,
        query: str, 
        file_pattern: str = "*.py",
        use_regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Search for text content in files"""
        results = []
        gitignore_patterns = self.load_gitignore_patterns(working_dir)
        
        # Compile search pattern
        if use_regex:
            try:
                search_pattern = re.compile(query, 0 if case_sensitive else re.IGNORECASE)
            except re.error:
                return []  # Invalid regex
        else:
            search_query = query if case_sensitive else query.lower()
        
        # Walk through files
        for root, _, files in os.walk(working_dir):
            if self.should_ignore_file(root, gitignore_patterns):
                continue
            
            for file in files:
                if not fnmatch.fnmatch(file, file_pattern):
                    continue
                
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, working_dir)
                
                if self.should_ignore_file(file_path, gitignore_patterns):
                    continue
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()
                    
                    for line_num, line in enumerate(lines, 1):
                        found = False
                        if use_regex:
                            if search_pattern.search(line):
                                found = True
                        else:
                            line_to_search = line if case_sensitive else line.lower()
                            if search_query in line_to_search:
                                found = True
                        
                        if found:
                            results.append({
                                'file': rel_path,
                                'line': line_num,
                                'content': line.strip(),
                                'match_type': 'regex' if use_regex else 'text'
                            })
                            
                            if len(results) >= max_results:
                                return results
                
                except Exception:
                    continue
        
        return results


class FuzzySymbolSearch:
    """Fuzzy symbol matching and search"""
    
    @staticmethod
    def fuzzy_match_score(query: str, symbol: str) -> float:
        """Calculate fuzzy match score between query and symbol"""
        query_lower = query.lower()
        symbol_lower = symbol.lower()
        
        # Exact match
        if query_lower == symbol_lower:
            return 1.0
        
        # Starts with
        if symbol_lower.startswith(query_lower):
            return 0.9
        
        # Contains
        if query_lower in symbol_lower:
            return 0.7
        
        # Subsequence match (characters in order)
        query_idx = 0
        for char in symbol_lower:
            if query_idx < len(query_lower) and char == query_lower[query_idx]:
                query_idx += 1
        
        if query_idx == len(query_lower):
            return 0.5
        
        return 0.0
    
    def search_symbols(
        self, 
        conn,  # SQLite connection to search in metadata
        query: str, 
        symbol_type: Optional[str] = None,
        file_pattern: Optional[str] = None,
        fuzzy: bool = True,
        min_score: float = 0.5,
        max_results: int = 20
    ) -> List[SearchResult]:
        """Search for symbols with fuzzy matching"""
        results = []
        
        # Build SQL query
        sql_query = """
            SELECT chunk_id, file_path, symbol_name, line_start, line_end, 
                   signature, docstring, chunk_type
            FROM chunks 
            WHERE symbol_name IS NOT NULL
        """
        params = []
        
        if symbol_type:
            sql_query += " AND chunk_type = ?"
            params.append(symbol_type)
        
        if file_pattern:
            sql_query += " AND file_path LIKE ?"
            params.append(f"%{file_pattern}%")
        
        cursor = conn.execute(sql_query, params)
        
        for row in cursor.fetchall():
            chunk_id, file_path, symbol_name, line_start, line_end, signature, docstring, chunk_type = row
            
            if not symbol_name:
                continue
            
            # Calculate match score
            if fuzzy:
                score = self.fuzzy_match_score(query, symbol_name)
                if score < min_score:
                    continue
            else:
                # Exact match only
                if query.lower() != symbol_name.lower():
                    continue
                score = 1.0
            
            results.append(SearchResult(
                chunk_id=chunk_id,
                file_path=file_path,
                symbol_name=symbol_name,
                line_start=line_start,
                line_end=line_end,
                signature=signature,
                docstring=docstring,
                relevance_score=score,
                chunk_type=chunk_type,
            ))
        
        # Sort by relevance score
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return results[:max_results]


class EnhancedSearchManager:
    """Main enhanced search manager"""
    
    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.symbol_matcher = SymbolMatcher()
        self.text_searcher = TextSearcher()
        self.fuzzy_searcher = FuzzySymbolSearch()
    
    def calculate_sha1(self, file_path: str) -> str:
        """Calculate SHA1 hash of file"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha1(f.read()).hexdigest()
        except Exception:
            return ""
    
    def list_symbols_in_file(self, file_path: str) -> List[Dict[str, Any]]:
        """List all symbols in a specific file"""
        try:
            abs_path = Path(self.working_dir) / file_path
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            symbols = self.symbol_matcher.extract_symbols(str(abs_path), content)
            
            # Add file hash for change detection
            file_hash = self.calculate_sha1(str(abs_path))
            
            return {
                'file': file_path,
                'file_hash': file_hash,
                'symbols': symbols,
                'total_lines': len(content.split('\n')),
                'file_size': len(content)
            }
        
        except Exception as e:
            return {
                'file': file_path, 
                'error': str(e),
                'symbols': []
            }
    
    def enhanced_search(
        self, 
        request: SearchRequest,
        sqlite_conn = None
    ) -> List[SearchResult]:
        """Perform enhanced search based on search type"""
        
        if request.search_type == "fuzzy_symbol":
            if not sqlite_conn:
                return []
            return self.fuzzy_searcher.search_symbols(
                sqlite_conn,
                request.query,
                symbol_type=getattr(request, 'symbol_type', None),
                file_pattern=request.file_pattern,
                fuzzy=True,
                max_results=request.max_results
            )
        
        elif request.search_type == "text":
            text_results = self.text_searcher.search_in_files(
                self.working_dir,
                request.query,
                file_pattern=request.file_pattern or "*.py",
                use_regex=getattr(request, 'use_regex', False),
                case_sensitive=getattr(request, 'case_sensitive', False),
                max_results=request.max_results
            )
            
            # Convert to SearchResult format
            results = []
            for i, result in enumerate(text_results):
                results.append(SearchResult(
                    chunk_id=f"text_{i}",
                    file_path=result['file'],
                    symbol_name=None,
                    line_start=result['line'],
                    line_end=result['line'],
                    signature=None,
                    docstring=None,
                    relevance_score=1.0,
                    chunk_type='text_match',
                ))
            
            return results
        
        elif request.search_type == "symbol_exact":
            if not sqlite_conn:
                return []
            return self.fuzzy_searcher.search_symbols(
                sqlite_conn,
                request.query,
                symbol_type=getattr(request, 'symbol_type', None),
                file_pattern=request.file_pattern,
                fuzzy=False,
                max_results=request.max_results
            )
        
        return []
