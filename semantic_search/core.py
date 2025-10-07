"""Core semantic search engine with enhanced search capabilities"""

import asyncio
import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Any,Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from .models import SearchRequest, SearchResult, ChunkData
from .vector_store import VectorStore
from .enhanced_search import EnhancedSearchManager
from chunkers import PythonChunker, JSChunker, BaseChunker


class SemanticSearchEngine:
    """Main semantic search engine with enhanced capabilities"""

    def __init__(self, working_dir: str, model_name: str = "all-MiniLM-L6-v2"):
        self.working_dir = Path(working_dir)
        self.model_name = model_name
        self.embedding_model = None
        self.vector_store = VectorStore(working_dir=working_dir)

        # Initialize enhanced search manager
        self.enhanced_search = EnhancedSearchManager(str(working_dir))
        self.symbol_reader = None
        # Initialize chunkers
        self.chunkers: List[BaseChunker] = [PythonChunker(), JSChunker()]
        self.codebase_indexed=False
        self._is_initialized = False
        self._processing_lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the search engine"""
        if self._is_initialized:
            return

        # Load embedding model
        print(f"Loading embedding model: {self.model_name}")
        self.embedding_model = SentenceTransformer(self.model_name)
        
        from .symbol_reader import SymbolReader
        self.symbol_reader = SymbolReader(str(self.working_dir), self.vector_store)
        if not self.codebase_indexed and not self.vector_store.get_stats()["indexed"] :
            await self.index_codebase()
            self.codebase_indexed=True
            print("Codebase indexed")

        self._is_initialized = True
        print("Semantic search engine initialized")
    
    async def read_symbol_content(
        self,
        file_path: str,
        symbol_name: Optional[str] = None,
        occurrence: int = 1,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        with_line_numbers: bool = True
    ) -> Dict[str, Any]:
        """Read code content with symbol or line range support"""
        if not self._is_initialized:
            await self.initialize()
        
        if not self.symbol_reader:
            return {
                "success": False,
                "error": "Symbol reader not initialized"
            }
        
        return self.symbol_reader.read_code_content(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            symbol_name=symbol_name,
            occurrence=occurrence,
            with_line_numbers=with_line_numbers
        )
    
    async def index_codebase(self, force_reindex: bool = False):
        """Index the entire codebase"""
        if not self._is_initialized:
            await self.initialize()

        async with self._processing_lock:
            print(f"Starting codebase indexing: {self.working_dir}")

            all_chunks = []
            processed_files = 0

            # Walk through all files
            for file_path in self._get_code_files():
                try:
                    chunks = await self._process_file(str(file_path))
                    all_chunks.extend(chunks)
                    processed_files += 1

                    if processed_files % 10 == 0:
                        print(
                            f"Processed {processed_files} files, {len(all_chunks)} chunks"
                        )

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

            if all_chunks:
                # Generate embeddings in batches
                print(f"Generating embeddings for {len(all_chunks)} chunks")
                embeddings = await self._generate_embeddings(
                    [chunk.content for chunk in all_chunks]
                )

                # Store in vector database
                self.vector_store.add_chunks(all_chunks, embeddings)

                print(
                    f"Indexing complete: {processed_files} files, {len(all_chunks)} chunks"
                )
            else:
                print("No chunks to index")

    async def search(self, request: SearchRequest) -> List[SearchResult]:
        """Search for relevant code chunks using various search methods"""
        if not self._is_initialized:
            await self.initialize()

        if request.search_type == "semantic":
            return await self._semantic_search(request)
        elif request.search_type in ["fuzzy_symbol", "text", "symbol_exact"]:
            return await self._enhanced_search(request)
        else:
            return []

    async def _semantic_search(self, request: SearchRequest) -> List[SearchResult]:
        """Perform semantic search"""
        # Generate query embedding
        query_embedding = self.embedding_model.encode([request.query])  # type:ignore

        # Search vector store
        results = self.vector_store.search(
            query_embedding[0],
            top_k=request.max_results,
            file_pattern=request.file_pattern,
        )

        return results

    async def _enhanced_search(self, request: SearchRequest) -> List[SearchResult]:
        """Perform enhanced search using symbol/text search"""
        # Get SQLite connection from vector store
        try:
            conn = sqlite3.connect(self.vector_store.metadata_db)
            results = self.enhanced_search.enhanced_search(request, conn)
            conn.close()
            return results
        except Exception as e:
            print(f"Enhanced search error: {e}")
            return []

    async def list_symbols_in_file(self, file_path: str) -> List[Dict[str, Any]]:
        """List all symbols in a specific file"""
        return self.enhanced_search.list_symbols_in_file(file_path)

    async def _process_file(self, file_path: str) -> List[ChunkData]:
        """Process a single file and extract chunks"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Calculate file hash for change detection
            file_hash = self.enhanced_search.calculate_sha1(file_path)

            # Find appropriate chunker
            for chunker in self.chunkers:
                if chunker.can_handle(file_path):
                    chunks = await chunker.chunk_file(file_path, content)
                    # Add file hash to chunks
                    for chunk in chunks:
                        chunk.file_hash = file_hash
                    return chunks

            # No specific chunker found, create basic chunk
            return [
                ChunkData(
                    chunk_id=f"{file_path}:1",
                    file_path=file_path,
                    chunk_type="file",
                    symbol_name=Path(file_path).name,
                    line_start=1,
                    line_end=len(content.split("\n")),
                    content=content[:1000],  # Truncate long files
                    file_hash=file_hash,
                )
            ]

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            return []

    async def _generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for texts"""
        # Process in batches to avoid memory issues
        batch_size = 32
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = self.embedding_model.encode(batch)  # type:ignore
            all_embeddings.append(batch_embeddings)

        return np.vstack(all_embeddings)

    def _get_code_files(self) -> List[Path]:
        """Get all code files to process"""
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
        }
        ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "env",".codebase"}
        ignore_files = {".gitignore", ".env", ".mcp_index.json"}

        code_files = []

        for root, dirs, files in os.walk(self.working_dir):
            # Remove ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for file in files:
                if file in ignore_files:
                    continue

                file_path = Path(root) / file
                if file_path.suffix in code_extensions:
                    code_files.append(file_path)

        return code_files

    async def update_file(self, file_path: str):
        """Update index for a specific file using SHA1 change detection"""
        if not self._is_initialized:
            return

        async with self._processing_lock:
            try:
                abs_path = Path(self.working_dir) / file_path
                
                # Check if file exists
                if not abs_path.exists():
                    # File was deleted, remove from index
                    self.vector_store.remove_file_chunks(file_path)
                    print(f"Removed deleted file from index: {file_path}")
                    return

                # Calculate current file hash
                current_hash = self.enhanced_search.calculate_sha1(str(abs_path))
                
                # Check if file has changed by comparing hashes in database
                conn = sqlite3.connect(self.vector_store.metadata_db)
                cursor = conn.execute(
                    "SELECT file_hash FROM chunks WHERE file_path = ? LIMIT 1",
                    (file_path,)
                )
                result = cursor.fetchone()
                conn.close()

                if result and result[0] == current_hash:
                    print(f"File unchanged (SHA1 match): {file_path}")
                    return

                # File has changed or is new, reprocess it
                # Remove existing chunks for this file
                self.vector_store.remove_file_chunks(file_path)

                # Process file and add new chunks
                chunks = await self._process_file(str(abs_path))
                if chunks:
                    embeddings = await self._generate_embeddings(
                        [chunk.content for chunk in chunks]
                    )
                    self.vector_store.add_chunks(chunks, embeddings)
                    print(f"Updated {len(chunks)} chunks for {file_path} (SHA1: {current_hash[:8]})")

            except Exception as e:
                print(f"Error updating file {file_path}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get search engine statistics"""
        stats = self.vector_store.get_stats()
        stats.update(
            {
                "initialized": self._is_initialized,
                "working_directory": str(self.working_dir),
                "model": self.model_name,
                "chunkers": len(self.chunkers),
                "enhanced_search_enabled": True,
                "supported_search_types": ["semantic", "fuzzy_symbol", "text", "symbol_exact"],
            }
        )
        return stats

    async def batch_update_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """Efficiently update multiple files using SHA1 change detection"""
        if not self._is_initialized:
            await self.initialize()
    
        async with self._processing_lock:
            # Get files that actually need updating
            files_needing_update = self.vector_store.get_files_needing_update(file_paths)
            
            if not files_needing_update:
                return {
                    "updated_files": 0,
                    "skipped_files": len(file_paths),
                    "message": "All files up to date (SHA1 unchanged)"
                }
    
            print(f"Updating {len(files_needing_update)} changed files out of {len(file_paths)} total")
    
            updated_files = 0
            total_chunks = 0
    
            for file_path in files_needing_update:
                try:
                    # Remove existing chunks for this file
                    removed_count = self.vector_store.remove_file_chunks(file_path)
                    if removed_count > 0:
                        print(f"Removed {removed_count} chunks for {file_path}")
    
                    # Process file and add new chunks
                    chunks = await self._process_file(file_path)
                    if chunks:
                        embeddings = await self._generate_embeddings(
                            [chunk.content for chunk in chunks]
                        )
                        self.vector_store.add_chunks(chunks, embeddings)
                        total_chunks += len(chunks)
                        updated_files += 1
    
                except Exception as e:
                    print(f"Error updating {file_path}: {e}")
    
            return {
                "updated_files": updated_files,
                "skipped_files": len(file_paths) - len(files_needing_update),
                "total_chunks": total_chunks,
                "message": f"Updated {updated_files} files with {total_chunks} chunks"
            }
    
    async def cleanup_index(self) -> Dict[str, Any]:
        """Clean up index by removing chunks for deleted files"""
        if not self._is_initialized:
            await self.initialize()
    
        async with self._processing_lock:
            # Get all existing code files
            existing_files = [str(f) for f in self._get_code_files()]
            
            # Remove chunks for deleted files
            removed_count = self.vector_store.cleanup_deleted_files(existing_files)
            
            return {
                "removed_chunks": removed_count,
                "existing_files": len(existing_files),
                "message": f"Cleaned up {removed_count} chunks from deleted files"
            }
    
    def get_indexing_status(self) -> Dict[str, Any]:
        """Get detailed indexing status with SHA1 information"""
        indexed_files = self.vector_store.get_indexed_files()
        stats = self.get_stats()
        
        return {
            "stats": stats,
            "indexed_files": len(indexed_files),
            "indexed_file_details": [
                {
                    "file": file_path,
                    "hash": file_hash[:8] + "...",  # Show first 8 chars of hash
                    "chunks": chunk_count
                }
                for file_path, file_hash, chunk_count in indexed_files[:10]  # Show first 10
            ],
            "total_indexed_files": len(indexed_files)
        }