"""Vector storage with FAISS and SQLite with SHA1 change detection"""

import sqlite3
import numpy as np
import hashlib
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import faiss
from .models import ChunkData, SearchResult


class VectorStore:
    def __init__(self, working_dir:str,db_path: str = ".data",):
        self.db_path = Path(f"{working_dir}/{db_path}")
        self.db_path.mkdir(exist_ok=True)

        self.metadata_db = working_dir/self.db_path / "metadata.db"
        self.vector_index_path = self.db_path / "vectors.faiss"

        # Initialize SQLite
        self._init_sqlite()

        # Initialize FAISS
        self.dimension = 384  # all-MiniLM-L6-v2 embedding size
        self.index = None
        self._load_or_create_faiss_index()

    def _init_sqlite(self):
        """Initialize SQLite database for metadata with SHA1 support"""
        conn = sqlite3.connect(self.metadata_db)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                chunk_type TEXT NOT NULL,
                symbol_name TEXT,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                signature TEXT,
                docstring TEXT,
                content TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                faiss_index INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Add indexes for efficient queries
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_file_path ON chunks(file_path);
            CREATE INDEX IF NOT EXISTS idx_file_hash ON chunks(file_hash);
            CREATE INDEX IF NOT EXISTS idx_symbol_name ON chunks(symbol_name);
            CREATE INDEX IF NOT EXISTS idx_chunk_type ON chunks(chunk_type);
            CREATE INDEX IF NOT EXISTS idx_faiss_index ON chunks(faiss_index);
            
            -- Create file_hashes table for tracking file changes
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                chunk_count INTEGER DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_file_hashes_hash ON file_hashes(file_hash);
        """
        )
        conn.commit()
        conn.close()

    def _load_or_create_faiss_index(self):
        """Load existing FAISS index or create new one"""
        if self.vector_index_path.exists():
            try:
                self.index = faiss.read_index(str(self.vector_index_path))
                print(f"Loaded FAISS index with {self.index.ntotal} vectors")
            except Exception as e:
                print(f"Error loading FAISS index: {e}. Creating new index.")
                self.index = faiss.IndexFlatIP(self.dimension)
        else:
            self.index = faiss.IndexFlatIP(self.dimension)

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA1 hash of file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha1(f.read()).hexdigest()
        except Exception:
            return ""

    def has_file_changed(self, file_path: str) -> bool:
        """Check if file has changed since last indexing"""
        try:
            current_hash = self.calculate_file_hash(file_path)
            if not current_hash:
                return True  # If we can't read the file, assume it changed
            
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.execute(
                "SELECT file_hash FROM file_hashes WHERE file_path = ?",
                (file_path,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return True  # File not indexed yet
            
            return result[0] != current_hash
            
        except Exception:
            return True  # If there's any error, assume file changed

    def get_file_hash(self, file_path: str) -> Optional[str]:
        """Get stored hash for a file"""
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.execute(
                "SELECT file_hash FROM file_hashes WHERE file_path = ?",
                (file_path,)
            )
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception:
            return None

    def add_chunks(self, chunks: List[ChunkData], embeddings: np.ndarray):
        """Add chunks and their embeddings to the store with proper SHA1 handling"""
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Get current FAISS index size to assign proper indices
        current_faiss_size = self.index.ntotal#type:ignore

        # Add to FAISS
        self.index.add(embeddings.astype(np.float32))#type:ignore

        # Add to SQLite with proper file hash handling
        conn = sqlite3.connect(self.metadata_db)
        
        # Track files and their chunks for file_hashes table
        file_chunks = {}
        
        for i, chunk in enumerate(chunks):
            faiss_idx = current_faiss_size + i
            
            # Use the file_hash from the chunk, or calculate it if missing
            file_hash = chunk.file_hash or self.calculate_file_hash(chunk.file_path)
            
            conn.execute(
                """
                INSERT OR REPLACE INTO chunks 
                (chunk_id, file_path, chunk_type, symbol_name, line_start, line_end, 
                 signature, docstring, content, file_hash, faiss_index, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    chunk.chunk_id,
                    chunk.file_path,
                    chunk.chunk_type,
                    chunk.symbol_name,
                    chunk.line_start,
                    chunk.line_end,
                    chunk.signature,
                    chunk.docstring,
                    chunk.content,
                    file_hash,
                    faiss_idx,
                ),
            )
            
            # Track chunks per file
            if chunk.file_path not in file_chunks:
                file_chunks[chunk.file_path] = {'hash': file_hash, 'count': 0}
            file_chunks[chunk.file_path]['count'] += 1

        # Update file_hashes table
        for file_path, info in file_chunks.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO file_hashes 
                (file_path, file_hash, last_indexed, chunk_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (file_path, info['hash'], info['count'])
            )

        conn.commit()
        conn.close()

        # Save FAISS index
        faiss.write_index(self.index, str(self.vector_index_path))

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        file_pattern: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search for similar chunks"""
        if self.index.ntotal == 0:#type:ignore
            return []

        # Normalize query embedding
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)

        # Search FAISS
        scores, indices = self.index.search(query_embedding, min(top_k * 2, self.index.ntotal))#type:ignore

        # Get metadata from SQLite using FAISS indices
        conn = sqlite3.connect(self.metadata_db)
        results = []

        for score, faiss_idx in zip(scores[0], indices[0]):
            if faiss_idx == -1:  # FAISS returns -1 for empty slots
                continue

            # Get chunk metadata by FAISS index
            cursor = conn.execute(
                """
                SELECT chunk_id, file_path, symbol_name, line_start, line_end, 
                       signature, docstring, chunk_type
                FROM chunks 
                WHERE faiss_index = ?
            """,
                (int(faiss_idx),),
            )

            row = cursor.fetchone()
            if row:
                (
                    chunk_id,
                    file_path,
                    symbol_name,
                    line_start,
                    line_end,
                    signature,
                    docstring,
                    chunk_type,
                ) = row

                # Apply file pattern filter if specified
                if file_pattern and file_pattern not in file_path:
                    continue

                results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        file_path=file_path,
                        symbol_name=symbol_name,
                        line_start=line_start,
                        line_end=line_end,
                        signature=signature,
                        docstring=docstring,
                        relevance_score=float(score),
                        chunk_type=chunk_type,
                    )
                )

        conn.close()
        return results[:top_k]

    def remove_file_chunks(self, file_path: str) -> int:
        """Remove all chunks for a specific file and return count removed"""
        conn = sqlite3.connect(self.metadata_db)
        
        # Get FAISS indices for chunks to be removed (for future optimization)
        cursor = conn.execute(
            "SELECT faiss_index FROM chunks WHERE file_path = ?",
            (file_path,)
        )
        # faiss_indices = [row[0] for row in cursor.fetchall()]
        
        # Remove from chunks table
        cursor = conn.execute(
            "DELETE FROM chunks WHERE file_path = ?", 
            (file_path,)
        )
        removed_count = cursor.rowcount
        
        # Remove from file_hashes table
        conn.execute(
            "DELETE FROM file_hashes WHERE file_path = ?",
            (file_path,)
        )
        
        conn.commit()
        conn.close()

        # Note: FAISS doesn't support efficient deletion, so we keep track
        # of deleted indices for potential future index rebuilding
        
        return removed_count

    def get_files_needing_update(self, file_paths: List[str]) -> List[str]:
        """Get list of files that need updating based on SHA1 comparison"""
        files_to_update = []
        
        for file_path in file_paths:
            if self.has_file_changed(file_path):
                files_to_update.append(file_path)
        
        return files_to_update

    def get_indexed_files(self) -> List[Tuple[str, str, int]]:
        """Get list of all indexed files with their hashes and chunk counts"""
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.execute(
            """
            SELECT file_path, file_hash, chunk_count 
            FROM file_hashes 
            ORDER BY last_indexed DESC
            """
        )
        results = cursor.fetchall()
        conn.close()
        
        return results

    def cleanup_deleted_files(self, existing_files: List[str]) -> int:
        """Remove chunks for files that no longer exist"""
        conn = sqlite3.connect(self.metadata_db)
        
        # Get all currently indexed files
        cursor = conn.execute("SELECT DISTINCT file_path FROM chunks")
        indexed_files = [row[0] for row in cursor.fetchall()]
        
        # Find files that are indexed but no longer exist
        deleted_files = [f for f in indexed_files if f not in existing_files]
        
        total_removed = 0
        for file_path in deleted_files:
            removed = self.remove_file_chunks(file_path)
            total_removed += removed
            print(f"Removed {removed} chunks for deleted file: {file_path}")
        
        return total_removed

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics with SHA1 integration info"""
        conn = sqlite3.connect(self.metadata_db)
        
        cursor = conn.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(DISTINCT file_path) FROM chunks")
        total_files = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM file_hashes")
        tracked_files = cursor.fetchone()[0]

        conn.close()

        return {
            "total_chunks": total_chunks,
            "total_files": total_files,
            "tracked_files": tracked_files,
            "faiss_vectors": self.index.ntotal if self.index else 0,
            "sha1_integration": True,
            "incremental_indexing": True,
            "indexed":True
        }