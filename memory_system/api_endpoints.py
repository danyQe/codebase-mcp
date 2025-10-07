"""FastAPI endpoints for memory system"""

from typing import Optional, List, Dict, Any
from fastapi import HTTPException
from datetime import datetime
import logging

from memory_system import MemoryManager
from memory_system.models import (
    Memory,
    MemoryRequest,
    MemorySearchRequest,
)

logger = logging.getLogger(__name__)


async def store_memory_endpoint(memory_manager: MemoryManager, request: MemoryRequest):
    """Store a new memory"""
    try:
        memory = await memory_manager.store_memory(request)

        return {
            "result": {
                "id": memory.id,
                "category": memory.category.value,
                "content": memory.content,
                "importance": memory.importance.value,
                "timestamp": memory.timestamp.isoformat(),
                "session_id": memory.session_id,
                "status": "stored",
            },
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Memory storage error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")


async def search_memories_endpoint(
    memory_manager: MemoryManager, request: MemorySearchRequest
):
    """Search memories using semantic search"""
    try:
        results = await memory_manager.search_memories(request)

        formatted_results = []
        for result in results:
            memory_data = {
                "id": result.memory.id,
                "category": result.memory.category.value,
                "subcategory": result.memory.subcategory,
                "content": result.memory.content,
                "importance": result.memory.importance.value,
                "timestamp": result.memory.timestamp.isoformat(),
                "tags": result.memory.tags,
                "context": result.memory.context,
                "related_files": result.memory.related_files,
                "status": result.memory.status,
                "verified": result.memory.verified,
            }

            formatted_results.append(
                {
                    "memory": memory_data,
                    "relevance_score": result.relevance_score,
                    "match_reason": result.match_reason,
                }
            )

        return {
            "result": {
                "query": request.query,
                "total_results": len(formatted_results),
                "results": formatted_results,
            },
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to search memories: {str(e)}"
        )


async def get_context_summary_endpoint(
    memory_manager: MemoryManager, session_id: Optional[str] = None
):
    """Get context summary for session start"""
    try:
        context = await memory_manager.get_context_summary(session_id)

        def format_memory_list(memories: List[Memory]) -> List[Dict]:
            return [
                {
                    "id": m.id,
                    "category": m.category.value,
                    "content": m.content,
                    "importance": m.importance.value,
                    "timestamp": m.timestamp.isoformat(),
                    "tags": m.tags,
                }
                for m in memories
            ]

        return {
            "result": {
                "recent_progress": format_memory_list(context.recent_progress),
                "key_learnings": format_memory_list(context.key_learnings),
                "user_preferences": format_memory_list(context.user_preferences),
                "important_warnings": format_memory_list(context.important_warnings),
                "current_focus": context.current_focus,
                "next_priorities": context.next_priorities,
            },
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Context summary error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get context: {str(e)}")


def get_memory_stats_endpoint(memory_manager: MemoryManager):
    """Get memory system statistics"""
    try:
        stats = memory_manager.get_stats()

        return {
            "result": {
                "total_memories": stats.total_memories,
                "by_category": stats.by_category,
                "by_importance": stats.by_importance,
                "recent_count": stats.recent_count,
                "verified_count": stats.verified_count,
                "archived_count": stats.archived_count,
            },
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Memory stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


async def update_memory_endpoint(
    memory_manager: MemoryManager, memory_id: int, updates: Dict[str, Any]
):
    """Update existing memory"""
    try:
        updated_memory = await memory_manager.update_memory(memory_id, **updates)

        if not updated_memory:
            raise HTTPException(status_code=404, detail=f"Memory {memory_id} not found")

        return {
            "result": {
                "id": updated_memory.id,
                "category": updated_memory.category.value,
                "content": updated_memory.content,
                "importance": updated_memory.importance.value,
                "timestamp": updated_memory.timestamp.isoformat(),
                "status": "updated",
            },
            "success": True,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory update error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update memory: {str(e)}"
        )
