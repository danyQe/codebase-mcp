"""Base chunker interface"""

import hashlib
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from semantic_search.models import ChunkData


class BaseChunker(ABC):
    """Abstract base class for code chunkers"""

    def __init__(self):
        self.supported_extensions = set()

    def can_handle(self, file_path: str) -> bool:
        """Check if this chunker can handle the file"""
        return Path(file_path).suffix in self.supported_extensions

    def _generate_chunk_id(
        self, file_path: str, symbol_name: str, line_start: int
    ) -> str:
        """Generate unique chunk ID"""
        content = f"{file_path}:{symbol_name}:{line_start}"
        return hashlib.md5(content.encode()).hexdigest()

    def _extract_content_lines(
        self, content: str, start_line: int, end_line: int
    ) -> str:
        """Extract specific lines from content"""
        lines = content.split("\n")
        return "\n".join(lines[start_line - 1 : end_line])
    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA1 hash of file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha1(f.read()).hexdigest()
        except Exception:
            return ""
    
    @abstractmethod
    async def chunk_file(self, file_path: str, content: str) -> List[ChunkData]:
        """Chunk file content - implemented by subclasses"""
        # Calculate file hash
        # file_hash = self.calculate_file_hash(file_path)
        
        # This will be implemented by subclasses, but they should use the file_hash
        raise NotImplementedError("Subclasses must implement chunk_file")