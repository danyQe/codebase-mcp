"""
Directory listing functionality with depth control and metadata
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class DirectoryLister:
    """Directory listing with gitignore support and metadata"""
    
    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir)
        self._gitignore_patterns = None
    
    def load_gitignore_patterns(self) -> List[str]:
        """Load gitignore patterns from .gitignore file"""
        if self._gitignore_patterns is not None:
            return self._gitignore_patterns
            
        gitignore_path = self.working_dir / '.gitignore'
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
        
        self._gitignore_patterns = patterns
        return patterns
    
    def should_ignore(self, path: Path, gitignore_patterns: List[str] = []) -> bool:
        """Check if path should be ignored based on gitignore patterns"""
        if gitignore_patterns is None:
            gitignore_patterns = self.load_gitignore_patterns()
        
        # Default ignore patterns
        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.pytest_cache'}
        ignore_files = {'.DS_Store', '.env', 'Thumbs.db', '.pyc'}
        
        # Check if it's a default ignored directory
        if path.is_dir() and path.name in ignore_dirs:
            return True
        
        # Check if it's a default ignored file
        if path.is_file() and (path.name in ignore_files or path.suffix == '.pyc'):
            return True
        
        # Check gitignore patterns
        try:
            rel_path = path.relative_to(self.working_dir)
            rel_str = str(rel_path).replace(os.sep, '/')
            
            for pattern in gitignore_patterns:
                # Handle directory patterns
                if pattern.endswith('/'):
                    if rel_str.startswith(pattern.rstrip('/')) or fnmatch.fnmatch(rel_str + '/', pattern):
                        return True
                # Handle file patterns
                elif fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                    return True
                # Handle parent directory matches
                elif '/' not in pattern and pattern in rel_str.split('/'):
                    return True
        except ValueError:
            # Path is not relative to working directory
            pass
        
        return False
    
    def get_file_metadata(self, path: Path) -> Dict[str, Any]:
        """Get metadata for a file or directory"""
        try:
            stat = path.stat()
            metadata = {
                'name': path.name,
                'path': str(path.relative_to(self.working_dir)),
                'is_directory': path.is_dir(),
                'size': stat.st_size if path.is_file() else 0,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'permissions': oct(stat.st_mode)[-3:],
            }
            
            # Add line count for code files
            if path.is_file() and self.is_code_file(path):
                metadata['line_count'] = self.count_lines(path)
                metadata['file_type'] = 'code'
            elif path.is_file():
                metadata['file_type'] = 'text' if self.is_text_file(path) else 'binary'
            else:
                metadata['file_type'] = 'directory'
            
            return metadata
        
        except (OSError, PermissionError):
            return {
                'name': path.name,
                'path': str(path.relative_to(self.working_dir)),
                'is_directory': path.is_dir(),
                'size': 0,
                'error': 'Permission denied or file not accessible',
                'file_type': 'directory' if path.is_dir() else 'unknown'
            }
    
    def is_code_file(self, path: Path) -> bool:
        """Check if file is a code file"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', 
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
            '.html', '.css', '.scss', '.less', '.vue', '.svelte',
            '.json', '.yaml', '.yml', '.toml', '.xml',
            '.sql', '.r', '.matlab', '.sh', '.bash', '.ps1'
        }
        return path.suffix.lower() in code_extensions
    
    def is_text_file(self, path: Path) -> bool:
        """Check if file is likely a text file"""
        text_extensions = {
            '.txt', '.md', '.rst', '.org', '.tex', '.rtf',
            '.csv', '.tsv', '.log', '.ini', '.cfg', '.conf',
            '.dockerfile', '.gitignore', '.gitattributes',
        }
        
        if path.suffix.lower() in text_extensions:
            return True
        
        # Check if it's a code file (code files are also text files)
        if self.is_code_file(path):
            return True
        
        # For files without extension, try to detect if it's text
        if not path.suffix:
            try:
                with open(path, 'rb') as f:
                    chunk = f.read(1024)
                    if b'\0' in chunk:
                        return False
                    # Check if mostly printable characters
                    printable = sum(1 for b in chunk if 32 <= b <= 126 or b in [9, 10, 13])
                    return (printable / len(chunk)) > 0.7 if chunk else True
            except Exception:
                return False
        
        return False
    
    def count_lines(self, path: Path) -> int:
        """Count lines in a text file"""
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"
    
    def list_directory(
        self, 
        directory_path: str = ".",
        max_depth: int = 2,
        include_hidden: bool = False,
        show_metadata: bool = True,
        respect_gitignore: bool = True,
        files_only: bool = False,
        dirs_only: bool = False
    ) -> Dict[str, Any]:
        """
        List directory contents with configurable options
        
        Args:
            directory_path: Path to directory (relative to working_dir)
            max_depth: Maximum depth to traverse (0 = current dir only)
            include_hidden: Include hidden files/directories
            show_metadata: Include file metadata (size, lines, etc.)
            respect_gitignore: Filter based on .gitignore patterns
            files_only: Only show files, not directories
            dirs_only: Only show directories, not files
        """
        try:
            # Resolve target directory
            if directory_path == ".":
                target_dir = self.working_dir
            else:
                target_dir = self.working_dir / directory_path
                if not target_dir.exists():
                    return {"error": f"Directory not found: {directory_path}"}
                if not target_dir.is_dir():
                    return {"error": f"Path is not a directory: {directory_path}"}
            
            # Load gitignore patterns if needed
            gitignore_patterns = self.load_gitignore_patterns() if respect_gitignore else []
            
            # Collect directory contents
            items = []
            total_files = 0
            total_dirs = 0
            total_size = 0
            
            def collect_items(current_dir: Path, current_depth: int, prefix: str = ""):
                nonlocal total_files, total_dirs, total_size
                
                if current_depth > max_depth:
                    return
                
                try:
                    entries = list(current_dir.iterdir())
                    entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
                    
                    for i, entry in enumerate(entries):
                        # Skip hidden files if not requested
                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        
                        # Skip ignored files/dirs if respecting gitignore
                        if respect_gitignore and self.should_ignore(entry, gitignore_patterns):
                            continue
                        
                        # Apply file/dir only filters
                        if files_only and entry.is_dir():
                            continue
                        if dirs_only and entry.is_file():
                            continue
                        
                        # Get metadata
                        metadata = self.get_file_metadata(entry) if show_metadata else {
                            'name': entry.name,
                            'is_directory': entry.is_dir()
                        }
                        
                        # Add tree structure indicators
                        is_last = (i == len(entries) - 1)
                        if current_depth == 0:
                            tree_prefix = ""
                            tree_connector = ""
                        else:
                            tree_connector = "└── " if is_last else "├── "
                            tree_prefix = prefix
                        
                        metadata['tree_prefix'] = tree_prefix + tree_connector
                        metadata['depth'] = current_depth
                        
                        items.append(metadata)
                        
                        # Update counters
                        if entry.is_file():
                            total_files += 1
                            total_size += metadata.get('size', 0)
                        else:
                            total_dirs += 1
                        
                        # Recurse into subdirectories
                        if entry.is_dir() and current_depth < max_depth:
                            next_prefix = prefix + ("    " if is_last else "│   ")
                            collect_items(entry, current_depth + 1, next_prefix)
                
                except PermissionError:
                    items.append({
                        'name': f"[Permission Denied: {current_dir.name}]",
                        'tree_prefix': prefix,
                        'error': 'Permission denied',
                        'depth': current_depth
                    })
            
            # Start collection
            collect_items(target_dir, 0)
            
            return {
                'directory': str(target_dir.relative_to(self.working_dir)) if target_dir != self.working_dir else ".",
                'items': items,
                'summary': {
                    'total_files': total_files,
                    'total_directories': total_dirs,
                    'total_size': total_size,
                    'total_size_formatted': self.format_size(total_size),
                    'max_depth': max_depth,
                    'items_shown': len(items),
                },
                'options': {
                    'include_hidden': include_hidden,
                    'show_metadata': show_metadata,
                    'respect_gitignore': respect_gitignore,
                    'files_only': files_only,
                    'dirs_only': dirs_only,
                }
            }
        
        except Exception as e:
            return {"error": f"Failed to list directory: {str(e)}"}
