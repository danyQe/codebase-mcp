"""
Search and indexing endpoints
Provides semantic search, text search, symbol search, and index management
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from core import get_search_engine
from core.config import get_settings
from semantic_search.models import SearchRequest
from utils import (
    create_success_response,
    create_error_response,
    validate_file_path,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("")
async def search_codebase(request: SearchRequest):
    """Search the codebase using semantic search"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        results = await search_engine.search(request)

        # Format results for API response
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "file_path": result.file_path,
                    "symbol_name": result.symbol_name,
                    "chunk_type": result.chunk_type,
                    "line_start": result.line_start,
                    "line_end": result.line_end,
                    "signature": result.signature,
                    "docstring": result.docstring,
                    "relevance_score": result.relevance_score,
                }
            )

        return create_success_response(
            {
                "query": request.query,
                "search_type": request.search_type,
                "results": formatted_results,
                "total_results": len(formatted_results),
            }
        )

    except Exception as e:
        return create_error_response(f"Search failed: {str(e)}", 500)


@router.post("/index")
async def index_codebase():
    """Index the entire codebase"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        await search_engine.index_codebase()
        stats = search_engine.get_stats()

        return create_success_response(
            {"message": "Codebase indexing completed", "stats": stats}
        )

    except Exception as e:
        return create_error_response(f"Indexing failed: {str(e)}", 500)


@router.get("/symbols/{file_path:path}")
async def list_file_symbols(file_path: str):
    """List all symbols in a specific file"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        # Validate file path
        settings = get_settings()
        await validate_file_path(file_path, settings.WORKING_DIR)

        symbols_info = await search_engine.list_symbols_in_file(file_path)

        return create_success_response(symbols_info)

    except HTTPException:
        raise
    except Exception as e:
        return create_error_response(f"Failed to list symbols: {str(e)}", 500)


@router.post("/update_file")
async def update_file_index(
    file_path: str = Query(..., description="File path to update")
):
    """Update index for a specific file"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        settings = get_settings()
        await validate_file_path(file_path, settings.WORKING_DIR)
        await search_engine.update_file(file_path)

        return create_success_response(f"File index updated: {file_path}")

    except HTTPException:
        raise
    except Exception as e:
        return create_error_response(f"File update failed: {str(e)}", 500)


@router.post("/text")
async def text_search(
    query: str = Query(..., description="Text to search for"),
    file_pattern: str = Query("*.py", description="File pattern filter"),
    use_regex: bool = Query(False, description="Use regex matching"),
    case_sensitive: bool = Query(False, description="Case sensitive search"),
    max_results: int = Query(50, description="Maximum results"),
):
    """Search for text content in files"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        request = SearchRequest(
            query=query,
            search_type="text",
            file_pattern=file_pattern,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            max_results=max_results,
        )

        results = await search_engine.search(request)

        # Format results for API response
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "file_path": result.file_path,
                    "line_number": result.line_start,
                    "content": result.chunk_type,  # Contains the matched line content
                    "match_type": "text",
                }
            )

        return create_success_response(
            {
                "query": query,
                "search_type": "text",
                "file_pattern": file_pattern,
                "use_regex": use_regex,
                "results": formatted_results,
                "total_results": len(formatted_results),
            }
        )

    except Exception as e:
        return create_error_response(f"Text search failed: {str(e)}", 500)


@router.post("/symbols")
async def symbol_search(
    query: str = Query(..., description="Symbol name to search for"),
    symbol_type: Optional[str] = Query(
        None, description="Symbol type filter (function, class, interface)"
    ),
    file_pattern: Optional[str] = Query(None, description="File pattern filter"),
    fuzzy: bool = Query(True, description="Enable fuzzy matching"),
    min_score: float = Query(0.5, description="Minimum fuzzy match score"),
    max_results: int = Query(20, description="Maximum results"),
):
    """Search for symbols with fuzzy matching"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        search_type = "fuzzy_symbol" if fuzzy else "symbol_exact"

        request = SearchRequest(
            query=query,
            search_type=search_type,
            symbol_type=symbol_type,
            file_pattern=file_pattern,
            fuzzy=fuzzy,
            min_score=min_score,
            max_results=max_results,
        )

        results = await search_engine.search(request)

        # Format results for API response
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "file_path": result.file_path,
                    "symbol_name": result.symbol_name,
                    "symbol_type": result.chunk_type,
                    "line_start": result.line_start,
                    "line_end": result.line_end,
                    "signature": result.signature,
                    "relevance_score": result.relevance_score,
                }
            )

        return create_success_response(
            {
                "query": query,
                "search_type": search_type,
                "symbol_type": symbol_type,
                "fuzzy_enabled": fuzzy,
                "results": formatted_results,
                "total_results": len(formatted_results),
            }
        )

    except Exception as e:
        return create_error_response(f"Symbol search failed: {str(e)}", 500)


@router.get("/stats")
async def get_search_statistics():
    """Get detailed search engine statistics"""
    try:
        search_engine = get_search_engine()
        if not search_engine:
            return create_error_response("Semantic search not initialized", 500)

        stats = search_engine.get_stats()

        return create_success_response(
            {
                "index_stats": stats,
                "status": "healthy" if stats.get("total_files", 0) > 0 else "empty",
                "last_indexed": stats.get("last_indexed", "never"),
                "index_size_mb": (
                    stats.get("index_size", 0) / (1024 * 1024)
                    if stats.get("index_size")
                    else 0
                ),
            }
        )

    except Exception as e:
        return create_error_response(f"Failed to get search stats: {str(e)}", 500)
