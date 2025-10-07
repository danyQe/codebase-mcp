"""Memory management system with SQLite storage and semantic search"""

import sqlite3
import json
import uuid
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
from enum import Enum

from .models import (
    Memory,
    MemoryRequest,
    MemorySearchRequest,
    MemoryResult,
    MemoryStats,
    ContextSummary,
    MemoryCategory,
    MemoryImportance,
)


class MemoryManager:
    """Manages Claude's memories with SQLite storage and semantic search"""

    def __init__(self, db_path: str = ".data"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(exist_ok=True)

        # Use same database as semantic search
        self.metadata_db = self.db_path / "metadata.db"

        # Initialize embedding model (same as semantic search)
        self.embedding_model = None
        self.embedding_dimension = 384  # all-MiniLM-L6-v2

        # Initialize database
        self._init_database()

    async def initialize(self):
        """Async initialization for embedding model"""
        if self.embedding_model is None:
            # Load same model as semantic search for consistency
            self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    def _init_database(self):
        """Initialize memory tables in SQLite"""
        conn = sqlite3.connect(self.metadata_db)

        # Create memories table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                subcategory TEXT,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 3,
                
                -- Metadata
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                tags_json TEXT,  -- JSON array of tags
                context_json TEXT,  -- JSON object
                related_files_json TEXT,  -- JSON array
                
                -- Status
                status TEXT DEFAULT 'active',
                verified BOOLEAN DEFAULT FALSE,
                
                -- Embeddings for semantic search
                embedding_vector BLOB
            )
        """
        )

        # Create indexes for fast queries
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
            CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp);
            CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
            CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id);
        """
        )

        # Create memory sessions table for context tracking
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_sessions (
                id TEXT PRIMARY KEY,
                start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_time DATETIME,
                focus_area TEXT,
                achievements TEXT,
                created_memories INTEGER DEFAULT 0
            )
        """
        )

        conn.commit()
        conn.close()

    def _serialize_list(self, items: List) -> str:
        """Serialize list to JSON string"""
        return json.dumps(items) if items else "[]"

    def _deserialize_list(self, json_str: Optional[str]) -> List:
        """Deserialize JSON string to list"""
        if not json_str:
            return []
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return []

    def _serialize_dict(self, data: Optional[Dict]) -> str:
        """Serialize dict to JSON string"""
        return json.dumps(data) if data else "{}"

    def _deserialize_dict(self, json_str: Optional[str]) -> Dict:
        """Deserialize JSON string to dict"""
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """Serialize embedding vector to bytes"""
        return embedding.astype(np.float32).tobytes()

    def _deserialize_embedding(self, blob: bytes) -> np.ndarray:
        """Deserialize bytes to embedding vector"""
        return np.frombuffer(blob, dtype=np.float32)

    def _memory_from_row(self, row: tuple) -> Memory:
        """Convert database row to Memory object"""
        (
            id_,
            category,
            subcategory,
            content,
            importance,
            timestamp,
            session_id,
            tags_json,
            context_json,
            related_files_json,
            status,
            verified,
            embedding_blob,
        ) = row

        # Parse timestamp
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        # Deserialize JSON fields
        tags = self._deserialize_list(tags_json)
        context = self._deserialize_dict(context_json)
        related_files = self._deserialize_list(related_files_json)

        # Deserialize embedding if present
        embedding_vector = None
        if embedding_blob:
            embedding_array = self._deserialize_embedding(embedding_blob)
            embedding_vector = embedding_array.tolist()

        return Memory(
            id=id_,
            category=MemoryCategory(category),
            subcategory=subcategory,
            content=content,
            importance=MemoryImportance(importance),
            timestamp=timestamp,
            session_id=session_id,
            tags=tags,
            context=context,
            related_files=related_files,
            status=status,
            verified=verified,
            embedding_vector=embedding_vector,
        )

    async def store_memory(self, request: MemoryRequest) -> Memory:
        """Store a new memory"""
        if not self.embedding_model:
            await self.initialize()

        # Generate embedding for content
        embedding = self.embedding_model.encode(request.content)  # type:ignore
        embedding_blob = self._serialize_embedding(embedding)  # type:ignore

        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Insert into database
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.execute(
            """
            INSERT INTO memories 
            (category, subcategory, content, importance, session_id, 
             tags_json, context_json, related_files_json, embedding_vector)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                request.category.value,
                request.subcategory,
                request.content,
                request.importance.value,
                session_id,
                self._serialize_list(request.tags),
                self._serialize_dict(request.context),
                self._serialize_list(request.related_files),
                embedding_blob,
            ),
        )

        memory_id = cursor.lastrowid
        conn.commit()

        # Retrieve the created memory
        cursor = conn.execute(
            """
            SELECT * FROM memories WHERE id = ?
        """,
            (memory_id,),
        )

        row = cursor.fetchone()
        conn.close()

        return self._memory_from_row(row)

    async def search_memories(self, request: MemorySearchRequest) -> List[MemoryResult]:
        """Search memories using semantic search and filters"""
        if not self.embedding_model:
            await self.initialize()

        conn = sqlite3.connect(self.metadata_db)

        # Build SQL query with filters
        sql_parts = ["SELECT * FROM memories WHERE status = 'active'"]
        params = []

        if not request.include_archived:
            sql_parts.append("AND status != 'archived'")

        if request.category:
            sql_parts.append("AND category = ?")
            params.append(request.category.value)

        if request.subcategory:
            sql_parts.append("AND subcategory = ?")
            params.append(request.subcategory)

        if request.min_importance:
            sql_parts.append("AND importance >= ?")
            params.append(request.min_importance.value)

        if request.recent_days:
            cutoff_date = datetime.now() - timedelta(days=request.recent_days)
            sql_parts.append("AND timestamp >= ?")
            params.append(cutoff_date.isoformat())

        # Execute base query
        sql = " ".join(sql_parts)
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        memories = [self._memory_from_row(row) for row in rows]

        # Apply semantic search if query provided
        if request.query and memories:
            query_embedding = self.embedding_model.encode(request.query)  # type:ignore

            results = []
            for memory in memories:
                if memory.embedding_vector:
                    memory_embedding = np.array(memory.embedding_vector)

                    # Calculate cosine similarity
                    similarity = np.dot(query_embedding, memory_embedding) / (
                        np.linalg.norm(query_embedding)
                        * np.linalg.norm(memory_embedding)
                    )

                    results.append(
                        MemoryResult(
                            memory=memory,
                            relevance_score=float(similarity),
                            match_reason="Semantic similarity",
                        )
                    )

            # Sort by relevance and limit
            results.sort(key=lambda x: x.relevance_score or 0, reverse=True)
            return results[: request.max_results]

        # Return without semantic ranking
        results = [
            MemoryResult(memory=memory, match_reason="Filter match")
            for memory in memories
        ]
        return results[: request.max_results]

    async def get_context_summary(
        self, session_id: Optional[str] = None
    ) -> ContextSummary:
        """Get contextual summary for new session"""
        if not self.embedding_model:
            await self.initialize()

        # Get recent progress updates
        recent_progress = await self.search_memories(
            MemorySearchRequest(
                category=MemoryCategory.PROGRESS, recent_days=30, max_results=5
            )
        )

        # Get key learnings (high importance)
        key_learnings = await self.search_memories(
            MemorySearchRequest(
                category=MemoryCategory.LEARNING,
                min_importance=MemoryImportance.HIGH,
                max_results=5,
            )
        )

        # Get user preferences
        user_preferences = await self.search_memories(
            MemorySearchRequest(category=MemoryCategory.PREFERENCE, max_results=10)
        )

        # Get important warnings (mistakes, debugging insights)
        important_warnings = await self.search_memories(
            MemorySearchRequest(
                category=MemoryCategory.MISTAKE,
                min_importance=MemoryImportance.MEDIUM,
                recent_days=60,
                max_results=5,
            )
        )

        return ContextSummary(
            recent_progress=[r.memory for r in recent_progress],
            key_learnings=[r.memory for r in key_learnings],
            user_preferences=[r.memory for r in user_preferences],
            important_warnings=[r.memory for r in important_warnings],
        )

    async def update_memory(self, memory_id: int, **updates) -> Optional[Memory]:
        """Update existing memory"""
        conn = sqlite3.connect(self.metadata_db)

        # Build update query
        set_parts = []
        params = []

        for field, value in updates.items():
            if field in [
                "content",
                "category",
                "subcategory",
                "importance",
                "status",
                "verified",
            ]:
                set_parts.append(f"{field} = ?")
                if isinstance(value, Enum):
                    params.append(value.value)
                else:
                    params.append(value)

        if not set_parts:
            conn.close()
            return None

        params.append(memory_id)

        conn.execute(
            f"""
            UPDATE memories 
            SET {', '.join(set_parts)}
            WHERE id = ?
        """,
            params,
        )

        conn.commit()

        # Retrieve updated memory
        cursor = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()

        return self._memory_from_row(row) if row else None

    def get_stats(self) -> MemoryStats:
        """Get memory system statistics"""
        conn = sqlite3.connect(self.metadata_db)

        # Total memories
        cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE status = 'active'")
        total_memories = cursor.fetchone()[0]

        # By category
        cursor = conn.execute(
            """
            SELECT category, COUNT(*) 
            FROM memories 
            WHERE status = 'active' 
            GROUP BY category
        """
        )
        by_category = dict(cursor.fetchall())

        # By importance - convert integer keys to strings for Pydantic
        cursor = conn.execute(
            """
            SELECT importance, COUNT(*) 
            FROM memories 
            WHERE status = 'active' 
            GROUP BY importance
        """
        )
        by_importance_raw = cursor.fetchall()
        by_importance = {str(k): v for k, v in by_importance_raw}

        # Recent (last 7 days)
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        cursor = conn.execute(
            """
            SELECT COUNT(*) 
            FROM memories 
            WHERE status = 'active' AND timestamp >= ?
        """,
            (week_ago,),
        )
        recent_count = cursor.fetchone()[0]

        # Verified count
        cursor = conn.execute(
            """
            SELECT COUNT(*) 
            FROM memories 
            WHERE status = 'active' AND verified = TRUE
        """
        )
        verified_count = cursor.fetchone()[0]

        # Archived count
        cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE status = 'archived'")
        archived_count = cursor.fetchone()[0]

        conn.close()

        return MemoryStats(
            total_memories=total_memories,
            by_category=by_category,
            by_importance=by_importance,
            recent_count=recent_count,
            verified_count=verified_count,
            archived_count=archived_count,
        )
