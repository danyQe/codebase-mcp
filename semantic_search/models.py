"""Pydantic models for semantic search"""

from typing import Optional, List
from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    file_pattern: Optional[str] = None
    search_type: str = "semantic"  # semantic, fuzzy_symbol, text, symbol_exact
    # Additional parameters for enhanced search
    symbol_type: Optional[str] = None  # function, class, interface, type, enum
    use_regex: bool = False  # For text search
    case_sensitive: bool = False  # For text search
    fuzzy: bool = True  # For symbol search
    min_score: float = 0.5  # Minimum fuzzy match score


class ChunkData(BaseModel):
    chunk_id: str
    file_path: str
    chunk_type: str  # file_overview, function, class
    symbol_name: Optional[str] = None
    line_start: int
    line_end: int
    content: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    file_hash: Optional[str] = None  # SHA1 hash for change detection


class SearchResult(BaseModel):
    chunk_id: str
    file_path: Optional[str]=None
    symbol_name: Optional[str] = None
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    relevance_score: float
    chunk_type: str


class SymbolInfo(BaseModel):
    """Model for symbol information"""
    name: str
    type: str  # function, class, interface, type, enum
    line: int
    file: str
    signature: Optional[str] = None


class FileSymbolsInfo(BaseModel):
    """Model for file symbols listing"""
    file: str
    file_hash: str
    symbols: List[SymbolInfo]
    total_lines: int
    file_size: int
    error: Optional[str] = None
