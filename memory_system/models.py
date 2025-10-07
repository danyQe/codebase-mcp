"""Memory system data models"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MemoryCategory(str, Enum):
    """Memory categories for organization"""

    PROGRESS = "progress"  # Project progress and status updates
    LEARNING = "learning"  # Technical learnings and insights
    PREFERENCE = "preference"  # User preferences and working style
    MISTAKE = "mistake"  # Mistakes made and corrections
    SOLUTION = "solution"  # Working solutions and patterns
    ARCHITECTURE = "architecture"  # Design decisions and rationale
    INTEGRATION = "integration"  # Component integration insights
    DEBUG = "debug"  # Debugging experiences and fixes


class MemoryImportance(int, Enum):
    """Memory importance levels"""

    CRITICAL = 5  # Must always remember
    HIGH = 4  # Very important
    MEDIUM = 3  # Standard importance
    LOW = 2  # Nice to remember
    MINIMAL = 1  # Archive level


class Memory(BaseModel):
    """Core memory data model"""

    id: Optional[int] = None
    category: MemoryCategory
    subcategory: Optional[str] = None
    content: str = Field(..., description="The actual memory content")
    importance: MemoryImportance = MemoryImportance.MEDIUM

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    related_files: List[str] = Field(default_factory=list)

    # Status
    status: str = "active"  # active, archived, deprecated
    verified: bool = False  # Has this been proven correct/useful?

    # Search support
    embedding_vector: Optional[List[float]] = None


class MemoryRequest(BaseModel):
    """Request to create or update memory"""

    category: MemoryCategory
    content: str = Field(..., description="Memory content to store")
    subcategory: Optional[str] = None
    importance: MemoryImportance = MemoryImportance.MEDIUM
    tags: List[str] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    related_files: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None


class MemorySearchRequest(BaseModel):
    """Request to search memories"""

    query: Optional[str] = None  # Semantic search query
    category: Optional[MemoryCategory] = None
    subcategory: Optional[str] = None
    min_importance: MemoryImportance = MemoryImportance.MINIMAL
    max_results: int = Field(10, ge=1, le=50)
    include_archived: bool = False
    tags: List[str] = Field(default_factory=list)
    recent_days: Optional[int] = None  # Only recent memories


class MemoryResult(BaseModel):
    """Search result with memory and relevance"""

    memory: Memory
    relevance_score: Optional[float] = None
    match_reason: Optional[str] = None  # Why this was matched


class MemoryStats(BaseModel):
    """Memory system statistics"""

    total_memories: int
    by_category: Dict[str, int]
    by_importance: Dict[str, int]
    recent_count: int  # Last 7 days
    verified_count: int
    archived_count: int


class ContextSummary(BaseModel):
    """Summary of relevant context for a new session"""

    recent_progress: List[Memory]
    key_learnings: List[Memory]
    user_preferences: List[Memory]
    important_warnings: List[Memory]
    current_focus: Optional[str] = None
    next_priorities: List[str] = Field(default_factory=list)
