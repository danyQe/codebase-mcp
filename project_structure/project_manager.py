"""
Enhanced Project Structure Manager
Provides detailed project tree with line counts, file sizes, and metadata
"""

import os
import fnmatch
from pathlib import Path
from typing import Dict, List, Any



class ProjectStructureManager:
    """Enhanced project structure analysis and display"""
    
    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir)
        self.ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', 'dist', 'build'}
        self.ignore_files = {'.DS_Store', '.gitignore', 'Thumbs.db'}
        
    def load_gitignore_patterns(self) -> List[str]:
        """Load gitignore patterns"""
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
        
        return patterns
    
    def should_ignore(self, path: Path, patterns: List[str]) -> bool:
        """Check if path should be ignored"""
        try:
            rel_path = path.relative_to(self.working_dir)
        except ValueError:
            return True
        
        rel_str = str(rel_path).replace(os.sep, '/')
        
        # Check ignore directories
        for part in rel_path.parts:
            if part in self.ignore_dirs:
                return True
        
        # Check ignore files
        if path.name in self.ignore_files:
            return True
        
        # Check gitignore patterns
        for pattern in patterns:
            if fnmatch.fnmatch(rel_str, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
        
        return False
    
    def count_lines_in_file(self, file_path: Path) -> int:
        """Count lines in a text file"""
        if self.is_binary_file(file_path):
            return 0
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def is_binary_file(self, path: Path) -> bool:
        """Check if file is binary"""
        try:
            with open(path, 'rb') as f:
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
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get detailed file information"""
        try:
            stat = file_path.stat()
            line_count = self.count_lines_in_file(file_path)
            
            return {
                'name': file_path.name,
                'size': stat.st_size,
                'line_count': line_count,
                'is_binary': self.is_binary_file(file_path),
                'modified': stat.st_mtime,
                'type': 'file'
            }
        except Exception:
            return {
                'name': file_path.name,
                'size': 0,
                'line_count': 0,
                'is_binary': True,
                'modified': 0,
                'type': 'file'
            }
    
    def get_directory_info(self, dir_path: Path, patterns: List[str], max_depth: int, current_depth: int = 0) -> Dict[str, Any]:
        """Get directory information recursively"""
        if current_depth >= max_depth:
            return {
                'name': dir_path.name,
                'type': 'directory',
                'truncated': True,
                'total_files': 0,
                'total_size': 0,
                'total_lines': 0
            }
        
        total_files = 0
        total_size = 0
        total_lines = 0
        children = []
        
        try:
            items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items:
                if self.should_ignore(item, patterns):
                    continue
                
                if item.is_file():
                    file_info = self.get_file_info(item)
                    children.append(file_info)
                    total_files += 1
                    total_size += file_info['size']
                    total_lines += file_info['line_count']
                
                elif item.is_dir():
                    dir_info = self.get_directory_info(item, patterns, max_depth, current_depth + 1)
                    children.append(dir_info)
                    total_files += dir_info.get('total_files', 0)
                    total_size += dir_info.get('total_size', 0)
                    total_lines += dir_info.get('total_lines', 0)
        
        except PermissionError:
            pass
        
        return {
            'name': dir_path.name or self.working_dir.name,
            'type': 'directory',
            'children': children,
            'total_files': total_files,
            'total_size': total_size,
            'total_lines': total_lines,
            'truncated': False
        }
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"
    
    def build_tree_string(self, node: Dict[str, Any], prefix: str = "", is_last: bool = True, include_hidden: bool = False) -> str:
        """Build tree structure string with enhanced metadata"""
        output = ""
        
        # Current node
        connector = "└── " if is_last else "├── "
        name = node['name']
        
        if node['type'] == 'directory':
            # Directory with metadata
            total_files = node.get('total_files', 0)
            total_size = node.get('total_size', 0)
            total_lines = node.get('total_lines', 0)
            
            output += f"{prefix}{connector}{name}/  # dir: {total_files} files, {self.format_size(total_size)}, {total_lines:,} lines\n"
            
            # Add children
            children = node.get('children', [])
            if not include_hidden:
                children = [c for c in children if not c['name'].startswith('.')]
            
            for i, child in enumerate(children):
                is_child_last = (i == len(children) - 1)
                next_prefix = prefix + ("    " if is_last else "│   ")
                output += self.build_tree_string(child, next_prefix, is_child_last, include_hidden)
            
            if node.get('truncated'):
                next_prefix = prefix + ("    " if is_last else "│   ")
                output += f"{next_prefix}└── ... (truncated at max depth)\n"
        
        else:
            # File with metadata
            size = node.get('size', 0)
            line_count = node.get('line_count', 0)
            is_binary = node.get('is_binary', False)
            
            file_type = "binary" if is_binary else "text"
            line_info = f"{line_count:,} lines" if line_count > 0 else "binary"
            
            output += f"{prefix}{connector}{name}  # file: {self.format_size(size)}, {line_info},file type:{file_type}\n"
        
        return output
    
    def get_project_info(self) -> Dict[str, Any]:
        """Get basic project information"""
        patterns = self.load_gitignore_patterns()
        
        # Count files and sizes
        total_files = 0
        total_size = 0
        total_lines = 0
        file_types = {}
        
        for root, dirs, files in os.walk(self.working_dir):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            root_path = Path(root)
            if self.should_ignore(root_path, patterns):
                continue
            
            for file in files:
                file_path = root_path / file
                
                if self.should_ignore(file_path, patterns):
                    continue
                
                file_info = self.get_file_info(file_path)
                total_files += 1
                total_size += file_info['size']
                total_lines += file_info['line_count']
                
                # Track file extensions
                ext = file_path.suffix.lower()
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1
        
        # Detect project type
        project_files = []
        for check_file in ['package.json', 'requirements.txt', 'pyproject.toml', 'Cargo.toml', 'go.mod', 'pom.xml']:
            if (self.working_dir / check_file).exists():
                project_files.append(check_file)
        
        return {
            'working_directory': str(self.working_dir),
            'total_files': total_files,
            'total_size': total_size,
            'total_lines': total_lines,
            'project_files': project_files,
            'top_file_types': sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:10]
        }
    
    def get_project_structure(self, max_depth: int = 5, include_hidden: bool = False) -> str:
        """Get formatted project structure tree"""
        patterns = self.load_gitignore_patterns()
        
        # Build tree structure
        root_info = self.get_directory_info(self.working_dir, patterns, max_depth)
        
        # Format as tree
        header = f"📁 {root_info['name']}/\n"
        tree_content = ""
        
        children = root_info.get('children', [])
        if not include_hidden:
            children = [c for c in children if not c['name'].startswith('.')]
        
        for i, child in enumerate(children):
            is_last = (i == len(children) - 1)
            tree_content += self.build_tree_string(child, "", is_last, include_hidden)
        
        return header + tree_content
    
    def get_dependencies_info(self) -> Dict[str, str]:
        """Get project dependencies information"""
        deps_info = {}
        
        dependency_files = {
            'requirements.txt': 'Python requirements',
            'package.json': 'Node.js dependencies',
            'pyproject.toml': 'Python project configuration',
            'Cargo.toml': 'Rust dependencies',
            'go.mod': 'Go modules',
            'pom.xml': 'Maven dependencies',
            'build.gradle': 'Gradle dependencies'
        }
        
        for filename, description in dependency_files.items():
            file_path = self.working_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        if len(content) > 5000:  # Truncate very long files
                            content = content[:5000] + "\n... (truncated)"
                        deps_info[f"{filename} ({description})"] = content
                except Exception:
                    deps_info[f"{filename} ({description})"] = "Error reading file"
        
        return deps_info
