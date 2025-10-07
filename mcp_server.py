"""
MCP Server for Codebase Management
Provides 7 MCP tools that proxy requests to FastAPI backend via HTTP calls.
"""

import asyncio
import sys
from typing import Optional, List, Dict, Any
import httpx
import time
import json
from mcp.server.fastmcp import FastMCP
import logging
from prompts.general_dev_prompt import GENERAL_DEV_PROMPT

logger = logging.getLogger(__name__)

# FastAPI server configuration
FASTAPI_BASE_URL = "http://localhost:6789"
HTTP_TIMEOUT = 30.0

# Initialize MCP server
mcp = FastMCP("Codebase Manager MCP Server",port=6789)

# HTTP client for making requests to FastAPI
http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create HTTP client"""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(base_url=FASTAPI_BASE_URL, timeout=HTTP_TIMEOUT)
    return http_client


async def make_request(method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
    """Make HTTP request to FastAPI server with intelligent error parsing"""
    try:
        client = await get_http_client()
        response = await client.request(method, endpoint, **kwargs)
        
        if response.status_code == 200:
            if response.headers.get("content-type", "").startswith("application/json"):
                return response.json()
            else:
                return {"result": response.text}
        else:
            # Parse detailed error response
            try:
                error_data = response.json()
                
                # Extract the most useful information for LLM
                error_msg = error_data.get("error", f"HTTP {response.status_code}")
                error_type = error_data.get("error_type", "HTTPError")
                details = error_data.get("details", {})
                debug_help = error_data.get("debug_help", "")
                
                return {
                    "error": error_msg,
                    "error_type": error_type,
                    "details": details,
                    "debug_help": debug_help,
                    "status_code": response.status_code,
                    "component": details.get("component", "Unknown"),
                    "operation": details.get("operation", "Unknown")
                }
            except:
                # Fallback for non-JSON error responses
                return {
                    "error": f"Request failed with status {response.status_code}: {response.text[:200]}",
                    "error_type": "HTTPError",
                    "status_code": response.status_code,
                    "raw_response": response.text
                }

    except httpx.TimeoutException:
        return {
            "error": "Request timed out - FastAPI server may be overloaded or unresponsive",
            "error_type": "TimeoutError",
            "debug_help": "Check if FastAPI server is running and responding normally"
        }
    except httpx.ConnectError:
        return {
            "error": "Cannot connect to FastAPI server - server may be down",
            "error_type": "ConnectionError", 
            "debug_help": f"Ensure FastAPI server is running on {FASTAPI_BASE_URL}"
        }
    except Exception as e:
        return {
            "error": f"Unexpected error making request: {str(e)}",
            "error_type": "UnexpectedError",
            "debug_help": "Check network connectivity and server status"
        }

async def auto_commit_if_enabled(file_path: str, operation: str, purpose: Optional[str] = None, quality_score: Optional[float] = None) -> Optional[str]:
    """Helper function to auto-commit changes if enabled and quality is good"""
    try:
        # Check if we're in a session (optional - you can always auto-commit)
        current_result = await make_request("GET", "/session/current")
        if "error" in current_result:
            return None
            
        # Only auto-commit if quality is decent
        if quality_score is not None and quality_score < 0.8:
            return None
            
        # Make auto-commit request
        commit_result = await make_request("POST", "/session/auto-commit", params={
            "file_path": file_path,
            "operation": operation,
            "purpose": purpose,
            "quality_score": quality_score
        })
        
        if "result" in commit_result and isinstance(commit_result["result"], dict):
            commit_data = commit_result["result"]
            if commit_data.get("auto_commit"):
                commit_hash = commit_data.get("commit_hash", "unknown")
                return f"🔄 Auto-committed as {commit_hash}"
        
        return None
        
    except Exception as e:
        logger.warning(f"Auto-commit failed: {e}")
        return None



# =============================================================================
# MCP TOOLS - 8 main tools that proxy to FastAPI
# =============================================================================

@mcp.tool()
async def session_tool(
    operation: str, 
    session_name: Optional[str] = None,
    message: Optional[str] = None,
    auto_merge: Optional[bool] = False
) -> str:
    """
    Manage development sessions with automatic branch creation and switching
    
    Args:
        operation: Session operation (start, end, switch, list, merge, current,delete)
        session_name: Name of the session (auto-generated if not provided for 'start')
        message: Optional message for merge operations
        auto_merge: Automatically merge session when ending (default: False)
        
    Operations:
        - start: Create a new session branch and switch to it
        - end: End current session and return to main branch
        - switch: Switch to an existing session branch
        - list: List all session branches
        - merge: Merge a session branch into main
        - current: Show current session status
        - delete:Delete the session by specifying the session name.auto switched to master branch for deletion.
    """
    try:
        payload = {
            "operation": operation,
            "session_name": session_name,
            "message": message,
            "auto_merge": auto_merge
        }

        # Handle 'current' operation with different endpoint
        if operation.lower() == "current":
            result = await make_request("GET", "/session/current")
        else:
            result = await make_request("POST", "/session", json=payload)

        if "error" in result:
            # Enhanced error reporting for sessions
            error_msg = f"🚨 Session {operation} Error: {result['error']}\n"
            error_msg += f"📍 Component: {result.get('component', 'SessionManager')}\n"
            error_msg += f"🔍 Error Type: {result.get('error_type', 'Unknown')}\n"
            
            if result.get("debug_help"):
                error_msg += f"💡 Debug Help: {result['debug_help']}\n"
            
            details = result.get("details", {})
            if details:
                error_msg += "\n📋 Technical Details:\n"
                for key, value in details.items():
                    if key not in ["component", "operation", "timestamp"]:
                        error_msg += f"   • {key}: {value}\n"
            
            # Specific help for common session errors
            if "not initialized" in result['error'].lower():
                error_msg += "\n🔧 Possible Solutions:\n"
                error_msg += "   • Ensure .codebase directory exists and is writable\n"
                error_msg += "   • Check FastAPI server working directory\n"
                error_msg += "   • Verify git manager initialization\n"
            
            elif "not on a session branch" in result['error'].lower():
                error_msg += "\n🔧 Possible Solutions:\n"
                error_msg += "   • Use 'session start' to create a new session\n"
                error_msg += "   • Use 'session current' to check current status\n"
                error_msg += "   • Use 'session list' to see available sessions\n"
            
            return error_msg

        # Format successful results with more context
        if "result" in result and isinstance(result["result"], dict):
            session_data = result["result"]
            
            if operation.lower() == "start":
                output = f"🌿 Session Started: {session_data.get('session_name', 'Unknown')}\n"
                output += "✅ Created new branch and switched to it\n"
                output += "📝 All changes will now be tracked in this session branch\n"
                
                # Show git directory being used
                if session_data.get("git_dir"):
                    output += f"🔧 Using git directory: {session_data['git_dir']}\n"
                
            elif operation.lower() == "end":
                output = f"🏁 Session Ended: {session_data.get('session_name', 'Unknown')}\n"
                output += "↩️  Switched back to main branch\n"
                if session_data.get("merged"):
                    output += "🔀 Session changes merged to main\n"
                else:
                    output += "💡 Use merge operation to integrate changes later\n"
                    
            elif operation.lower() == "switch":
                output = f"🔄 Switched to Session: {session_data.get('session_name', 'Unknown')}\n"
                output += "✅ Ready to continue working in this session\n"
                
            elif operation.lower() == "list":
                output = "📋 Session Branches:\n"
                output += session_data.get("output", "No sessions found")
                
                # Add helpful context with actual session data
                sessions = session_data.get("data", {}).get("session_branches", [])
                if sessions:
                    active_sessions = [s for s in sessions if not s.get("is_merged", False)]
                    output += f"\n💡 {len(active_sessions)} active sessions available\n"
                    
                    # Show recent session activity
                    if active_sessions:
                        output += "\nRecent Sessions:\n"
                        for session in active_sessions[:3]:
                            output += f"   • {session.get('name', 'Unknown')} - {session.get('last_commit_message', 'No commits')[:50]}\n"
                else:
                    output += "\n💡 No active sessions found. Use 'session start' to create one.\n"
                    
            elif operation.lower() == "merge":
                output = f"🔀 Merged Session: {session_data.get('session_name', 'Unknown')}\n"
                output += "✅ Changes integrated into main branch\n"
                
            elif operation.lower() == "current":
                current_branch = session_data.get("current_branch", "unknown")
                is_session = session_data.get("is_session_branch", False)
                
                if is_session:
                    output = f"🌿 Current Session: {current_branch}\n"
                    output += "📝 You're working in a session branch - changes are being tracked\n"
                else:
                    output = f"📍 Current Branch: {current_branch}\n"
                    if current_branch == "main":
                        output += "💡 You're on main branch. Use 'session start' to begin a new session\n"
                    else:
                        output += "ℹ️  You're on a regular branch (not a session)\n"
            
            else:
                output = session_data.get("message", f"✅ Session {operation} completed")
                
            return output

        # Fallback
        return result.get("result", f"✅ Session {operation} completed")

    except Exception as e:
        return f"🚨 Session tool error: {str(e)}\n💡 Check if FastAPI server and git manager are properly initialized."


@mcp.tool()
async def memory_tool(
    operation: str,
    content: Optional[str] = None,
    query: Optional[str] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    importance: Optional[int] = 3,
    session_id: Optional[str] = None,
    memory_id: Optional[int] = None,
    max_results: Optional[int] = 10,
    recent_days: Optional[int] = None,
    include_archived: Optional[bool] = False,
) -> str:
    """
     Memory System Tool - Store and retrieve project knowledge across chat sessions

    This tool enables LLM to maintain persistent memory of project learnings, user preferences,
    development progress, mistakes made, and solutions found. The memory persists across different
    chat sessions, allowing continuity in project work.

    CRITICAL: This tool is designed to help LLM remember context between conversations.
    Use it to store important learnings, track progress, remember user preferences, and
    avoid repeating mistakes.

    Operations Available:

    📝 WRITE OPERATIONS:
    - "store": Store a new memory (requires: content, category)
    - "update": Update existing memory (requires: memory_id, content/category/importance)

    🔍 READ OPERATIONS:
    - "search": Search memories semantically (requires: query, optional: category, max_results)
    - "context": Get session startup context (returns: recent progress, key learnings, preferences)
    - "list": List memories by category/importance (optional: category, recent_days)
    - "stats": Get memory system statistics

    🗂️ CATEGORIES (use for 'category' parameter):
    - "progress": Project development progress and milestones achieved
    - "learning": Technical learnings, insights, and discoveries made during development
    - "preference": User preferences, working style, communication preferences
    - "mistake": Mistakes made and corrections received to avoid repeating them
    - "solution": Working solutions, code patterns, and successful approaches
    - "architecture": Design decisions, system architecture choices and reasoning
    - "integration": How components work together, integration insights
    - "debug": Debugging experiences, error fixes, troubleshooting insights

    ⭐ IMPORTANCE LEVELS (1-5 scale for 'importance' parameter):
    - 5 (CRITICAL): Must always remember - core project facts, critical user preferences
    - 4 (HIGH): Very important - key learnings, major progress milestones
    - 3 (MEDIUM): Standard importance - general learnings, regular progress updates
    - 2 (LOW): Nice to remember - minor insights, small fixes
    - 1 (MINIMAL): Archive level - very specific details, completed items

    💡 USAGE EXAMPLES:

    Store a learning:
    memory_tool(operation="store", category="learning",
                content="MCP tools must return strings not JSON objects - stdio transport breaks",
                importance=4)

    Store progress:
    memory_tool(operation="store", category="progress",
                content="Phase 3 complete: Edit tool, Write tool, Semantic search all working",
                importance=4)

    Store user preference:
    memory_tool(operation="store", category="preference",
                content="User prefers detailed explanations with technical context. Uses Python primarily.",
                importance=3)

    Record a mistake:
    memory_tool(operation="store", category="mistake",
                content="MISTAKE: Suggested cloud APIs. CORRECTION: User wants privacy-first local only. PREVENTION: Always check privacy requirements first.",
                importance=4)

    Search for related knowledge:
    memory_tool(operation="search", query="rate limiting gemini api", max_results=5)

    Get startup context (use at beginning of new chats):
    memory_tool(operation="context")

    List recent progress:
    memory_tool(operation="list", category="progress", recent_days=30)

    Update existing memory:
    memory_tool(operation="update", memory_id=15, content="Updated content", importance=4)

    🎯 BEST PRACTICES:
    - Store memories immediately when learning something important
    - Use "context" operation at start of new chat sessions for continuity
    - Search memories before starting similar work to avoid repeating mistakes
    - Update importance as learnings prove more/less valuable over time
    - Use descriptive content that will be useful when recalled later
    - Include context about WHY something was learned or decided

    Args:
        operation: The memory operation to perform (store, search, context, list, update, stats)
        content: Memory content to store (required for store/update operations)
        query: Search query for semantic search (required for search operation)
        category: Memory category - see categories list above (optional filter)
        subcategory: Optional subcategory for more specific organization
        importance: Importance level 1-5, default 3 (used for store/update operations)
        session_id: Optional session identifier for grouping related memories
        memory_id: Required for update operations - ID of memory to update
        max_results: Maximum search results to return (default: 10, max: 50)
        recent_days: Filter to only recent memories within N days
        include_archived: Whether to include archived memories in search results
    """
    try:
        # Input validation
        if operation not in ["store", "search", "context", "list", "update", "stats"]:
            return f"❌ Memory Error: Invalid operation '{operation}'. Valid operations: store, search, context, list, update, stats"

        if operation == "store" and not content:
            return "❌ Memory Error: 'content' required for store operation"

        if operation == "search" and not query:
            return "❌ Memory Error: 'query' required for search operation"

        if operation == "update" and not memory_id:
            return "❌ Memory Error: 'memory_id' required for update operation"

        # Map string categories to enum values
        category_map = {
            "progress": "progress",
            "learning": "learning",
            "preference": "preference",
            "mistake": "mistake",
            "solution": "solution",
            "architecture": "architecture",
            "integration": "integration",
            "debug": "debug",
        }

        # Build request payload based on operation
        if operation == "store":
            payload = {
                "category": (
                    category_map.get(category, "learning") if category else "learning"
                ),
                "content": content,
                "subcategory": subcategory,
                "importance": max(1, min(5, importance or 3)),  # Clamp to 1-5
                "session_id": session_id,
                "tags": [],
                "context": {},
                "related_files": [],
            }

            result = await make_request("POST", "/memory/store", json=payload)

            if "error" in result:
                return f"❌ Memory Store Error: {result['error']}"

            if "result" in result and isinstance(result["result"], dict):
                details = result["result"]
                output = "✅ Memory Stored Successfully\n"
                output += f"🆔 ID: {details.get('id')}\n"
                output += f"📂 Category: {details.get('category')}\n"
                output += f"⭐ Importance: {details.get('importance')}/5\n"
                output += f"📝 Content: {content[:100]}{'...' if len(content) > 100 else ''}\n"
                output += f"🕒 Stored: {details.get('timestamp', '')}\n"
                return output

        elif operation == "search":
            payload = {
                "query": query,
                "category": category_map.get(category) if category else None,
                "subcategory": subcategory,
                "min_importance": max(
                    1, min(5, 1)
                ),  # Always search all importance levels
                "max_results": max(1, min(50, max_results or 10)),
                "include_archived": include_archived or False,
                "recent_days": recent_days,
            }

            result = await make_request("POST", "/memory/search", json=payload)

            if "error" in result:
                return f"❌ Memory Search Error: {result['error']}"

            if "result" in result and isinstance(result["result"], dict):
                search_data = result["result"]
                results = search_data.get("results", [])

                output = f"🔍 Memory Search Results: '{query}'\n"
                output += f"📊 Total Results: {search_data.get('total_results', 0)}\n\n"

                if not results:
                    output += "No relevant memories found.\n"
                    output += (
                        "💡 Try a broader search query or check different categories."
                    )
                    return output

                for i, result_item in enumerate(results, 1):
                    memory = result_item.get("memory", {})
                    relevance = result_item.get("relevance_score")

                    output += f"{i}. 📋 Memory #{memory.get('id')}\n"
                    output += f"   📂 Category: {memory.get('category')} "
                    if memory.get("subcategory"):
                        output += f"→ {memory.get('subcategory')}"
                    output += "\n"

                    output += f"   ⭐ Importance: {memory.get('importance', 0)}/5\n"

                    if relevance:
                        output += f"   🎯 Relevance: {relevance:.3f}\n"

                    content = memory.get("content", "")
                    if len(content) > 150:
                        content = content[:147] + "..."
                    output += f"   📝 Content: {content}\n"

                    output += f"   🕒 Stored: {memory.get('timestamp', '')[:10]}\n"

                    if memory.get("tags"):
                        output += f"   🏷️  Tags: {', '.join(memory['tags'])}\n"

                    output += "\n"

                return output

        elif operation == "context":
            params = {"session_id": session_id} if session_id else {}
            result = await make_request("GET", "/memory/context", params=params)

            if "error" in result:
                return f"❌ Memory Context Error: {result['error']}"

            if "result" in result and isinstance(result["result"], dict):
                context = result["result"]

                output = "🧠 Memory Context Summary\n"
                output += "=" * 40 + "\n\n"

                # Recent Progress
                progress = context.get("recent_progress", [])
                if progress:
                    output += f"📈 Recent Progress ({len(progress)} items):\n"
                    for i, mem in enumerate(progress[:3], 1):
                        content = mem.get("content", "")[:80]
                        if len(mem.get("content", "")) > 80:
                            content += "..."
                        output += f"  {i}. {content}\n"
                    if len(progress) > 3:
                        output += (
                            f"     ... and {len(progress) - 3} more progress items\n"
                        )
                    output += "\n"

                # Key Learnings
                learnings = context.get("key_learnings", [])
                if learnings:
                    output += f"💡 Key Learnings ({len(learnings)} items):\n"
                    for i, mem in enumerate(learnings[:3], 1):
                        content = mem.get("content", "")[:80]
                        if len(mem.get("content", "")) > 80:
                            content += "..."
                        output += f"  {i}. {content}\n"
                    if len(learnings) > 3:
                        output += f"     ... and {len(learnings) - 3} more learnings\n"
                    output += "\n"

                # User Preferences
                preferences = context.get("user_preferences", [])
                if preferences:
                    output += f"⚙️  User Preferences ({len(preferences)} items):\n"
                    for i, mem in enumerate(preferences[:3], 1):
                        content = mem.get("content", "")[:80]
                        if len(mem.get("content", "")) > 80:
                            content += "..."
                        output += f"  {i}. {content}\n"
                    if len(preferences) > 3:
                        output += (
                            f"     ... and {len(preferences) - 3} more preferences\n"
                        )
                    output += "\n"

                # Important Warnings
                warnings = context.get("important_warnings", [])
                if warnings:
                    output += f"⚠️  Important Warnings ({len(warnings)} items):\n"
                    for i, mem in enumerate(warnings[:3], 1):
                        content = mem.get("content", "")[:80]
                        if len(mem.get("content", "")) > 80:
                            content += "..."
                        output += f"  {i}. {content}\n"
                    if len(warnings) > 3:
                        output += f"     ... and {len(warnings) - 3} more warnings\n"
                    output += "\n"

                # Current focus and priorities
                if context.get("current_focus"):
                    output += f"🎯 Current Focus: {context['current_focus']}\n\n"

                if context.get("next_priorities"):
                    output += "📋 Next Priorities:\n"
                    for priority in context["next_priorities"][:5]:
                        output += f"  • {priority}\n"

                return output

        elif operation == "list":
            # Build search request for listing
            payload = {
                "query": None,  # No semantic search, just filtering
                "category": category_map.get(category) if category else None,
                "subcategory": subcategory,
                "min_importance": 1,  # Include all importance levels
                "max_results": max_results or 20,
                "include_archived": include_archived or False,
                "recent_days": recent_days,
            }

            result = await make_request("POST", "/memory/search", json=payload)

            if "error" in result:
                return f"❌ Memory List Error: {result['error']}"

            if "result" in result and isinstance(result["result"], dict):
                search_data = result["result"]
                results = search_data.get("results", [])

                filter_desc = f"Category: {category}" if category else "All categories"
                if recent_days:
                    filter_desc += f", Last {recent_days} days"

                output = f"📋 Memory List - {filter_desc}\n"
                output += f"📊 Total: {len(results)} memories\n\n"

                if not results:
                    output += "No memories found matching the criteria."
                    return output

                # Group by category for better organization
                by_category = {}
                for result_item in results:
                    memory = result_item.get("memory", {})
                    cat = memory.get("category", "unknown")
                    if cat not in by_category:
                        by_category[cat] = []
                    by_category[cat].append(memory)

                for cat, memories in by_category.items():
                    output += f"📂 {cat.upper()} ({len(memories)} items):\n"
                    for memory in memories[:5]:  # Show first 5 per category
                        content = memory.get("content", "")[:60]
                        if len(memory.get("content", "")) > 60:
                            content += "..."#type:ignore
                        importance_stars = "⭐" * memory.get("importance", 3)
                        output += (
                            f"  #{memory.get('id', '?')} {importance_stars} {content}\n"
                        )

                    if len(memories) > 5:
                        output += (
                            f"     ... and {len(memories) - 5} more {cat} memories\n"
                        )
                    output += "\n"

                return output

        elif operation == "update":
            updates = {}
            if content:
                updates["content"] = content
            if category:
                updates["category"] = category_map.get(category, category)
            if subcategory:
                updates["subcategory"] = subcategory
            if importance is not None:
                updates["importance"] = max(1, min(5, importance))

            result = await make_request("PUT", f"/memory/{memory_id}", json=updates)

            if "error" in result:
                return f"❌ Memory Update Error: {result['error']}"

            if "result" in result and isinstance(result["result"], dict):
                details = result["result"]
                output = "✅ Memory Updated Successfully\n"
                output += f"🆔 ID: {details.get('id')}\n"
                output += f"📂 Category: {details.get('category')}\n"
                output += f"⭐ Importance: {details.get('importance')}/5\n"
                output += f"🕒 Updated: {details.get('timestamp', '')}\n"
                return output

        elif operation == "stats":
            result = await make_request("GET", "/memory/stats")

            if "error" in result:
                return f"❌ Memory Stats Error: {result['error']}"

            if "result" in result and isinstance(result["result"], dict):
                stats = result["result"]

                output = "📊 Memory System Statistics\n"
                output += "=" * 30 + "\n\n"

                output += (
                    f"📈 Total Active Memories: {stats.get('total_memories', 0)}\n"
                )
                output += f"🕒 Recent (7 days): {stats.get('recent_count', 0)}\n"
                output += f"✅ Verified: {stats.get('verified_count', 0)}\n"
                output += f"🗃️  Archived: {stats.get('archived_count', 0)}\n\n"

                # By category
                by_category = stats.get("by_category", {})
                if by_category:
                    output += "📂 By Category:\n"
                    for cat, count in sorted(
                        by_category.items(), key=lambda x: x[1], reverse=True
                    ):
                        output += f"   {cat}: {count}\n"
                    output += "\n"

                # By importance
                by_importance = stats.get("by_importance", {})
                if by_importance:
                    output += "⭐ By Importance:\n"
                    for imp in [5, 4, 3, 2, 1]:
                        count = by_importance.get(str(imp), 0)
                        stars = "⭐" * imp
                        if count > 0:
                            output += f"   {stars} ({imp}): {count}\n"

                return output

        # Fallback
        return result.get("result", f"✅ Memory {operation} operation completed")

    except Exception as e:
        return f"❌ Memory tool error: {str(e)}"


@mcp.tool()
async def git_tool(
    operation: str, 
    file_path: Optional[str] = None, 
    message: Optional[str] = None,
    max_results: Optional[int] = 10,
    cached: Optional[bool] = False
) -> str:
    """
    Comprehensive git operations tool for repository management and context

    Args:
        operation: Git operation (status, branches, log, diff, commit, add, blame, tree)
        file_path: Optional file path for file-specific operations
        message: Optional commit message (required for commit operation)
        max_results: Maximum results for log operations (default: 10)
        cached: Show staged/cached changes for diff operation (default: False)
        
    Operations:
        - status: Show repository status, current branch, and modified files
        - branches: List all branches with commit info and current branch indicator  
        - log: Show recent commit history (optionally for specific file)
        - diff: Show current changes or differences (optionally for specific file)
        - commit: Commit staged changes with message
        - add: Add files to staging area (requires file_path)
        - blame: Show line-by-line file history (requires file_path)
        - tree: Show git file tree structure
    """
    try:
        # Handle different operations
        if operation.lower() == "tree":
            # Special case for tree operation - use multiple git commands
            payload = {"operation": "status"}
            status_result = await make_request("POST", "/git", json=payload)
            
            payload = {"operation": "branches"}
            branches_result = await make_request("POST", "/git", json=payload)
            
            if "error" in status_result or "error" in branches_result:
                return f"⚠️ Git tree error: {status_result.get('error', branches_result.get('error'))}"
            
            # Combine results for comprehensive tree view
            output = "🌳 Git Repository Tree\n\n"
            
            if "result" in status_result and isinstance(status_result["result"], dict):
                status_data = status_result["result"]
                output += status_data.get("output", "")
                output += "\n\n"
            
            if "result" in branches_result and isinstance(branches_result["result"], dict):
                branches_data = branches_result["result"]
                output += branches_data.get("output", "")
            
            return output
        
        # Handle standard git operations
        payload = {
            "operation": operation,
            "file_path": file_path,
            "message": message,
            "max_results": max_results,
            "cached": cached
        }

        result = await make_request("POST", "/git", json=payload)

        if "error" in result:
            # Format detailed error for LLM understanding
            error_msg = f"🚨 Git {operation} Error: {result['error']}\n"
            error_msg += f"📍 Component: {result.get('component', 'GitManager')}\n"
            error_msg += f"🔍 Error Type: {result.get('error_type', 'Unknown')}\n"
            
            if result.get("debug_help"):
                error_msg += f"💡 Debug Help: {result['debug_help']}\n"
            
            details = result.get("details", {})
            if details:
                error_msg += "\n📋 Technical Details:\n"
                for key, value in details.items():
                    if key not in ["component", "operation", "timestamp"]:
                        error_msg += f"   • {key}: {value}\n"
            
            return error_msg

        if "result" in result and isinstance(result["result"], dict):
            git_data = result["result"]
            
            output = f"✅ Git {operation.title()} Results\n\n"
            output += git_data.get("output", "No output")
            
            # Add context information
            if git_data.get("working_dir"):
                output += f"\n\n📁 Working Directory: {git_data['working_dir']}"
            if git_data.get("git_dir"):
                output += f"\n🔧 Git Directory: {git_data['git_dir']}"
            
            return output

        return result.get("result", f"✅ Git {operation} completed")

    except Exception as e:
        return f"🚨 Git Tool Error: Unexpected error in git_tool: {str(e)}\n💡 Check if FastAPI server is running and accessible."


@mcp.tool()
async def file_tool(
    operation: str,
    file_path: str,
    content: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    File operations tool (legacy - use write_tool for intelligent writing)

    Args:
        operation: File operation (read, write, edit, create, delete)
        file_path: Path to the file
        content: Content for write/edit operations
        start_line: Start line for read/edit operations
        end_line: End line for read/edit operations
    """
    try:
        payload = {
            "operation": operation,
            "file_path": file_path,
            "content": content,
            "start_line": start_line,
            "end_line": end_line,
        }

        result = await make_request("POST", "/file", json=payload)

        if "error" in result:
            return f"❌ File Error: {result['error']}"

        return str(result.get("result", "✅ File operation completed"))

    except Exception as e:
        return f"❌ File tool error: {str(e)}"


@mcp.tool()
async def write_tool(
    file_path: str,
    content: str,
    purpose: Optional[str] = None,
    language: Optional[str] = None,
    save_to_file: Optional[bool] = True,
) -> str:
    """
    Intelligent write tool with formatting, dependency checking, and quality analysis

    Args:
        file_path: Path to the file to write
        content: Code content to write
        purpose: Purpose/description of what this code does
        language: Programming language (python, javascript, typescript) - auto-detected if not provided
        save_to_file: Whether to save to file after processing (default: True)
    """
    try:
        payload = {
            "file_path": file_path,
            "content": content,
            "purpose": purpose,
            "language": language,
            "save_to_file": save_to_file,
        }

        result = await make_request("POST", "/write", json=payload)

        # Handle both success and failure responses
        # if "error" in result:
        #     # Check if it's a detailed error response
        #     if "details" in result and result.get("error_type") == "WriteQualityFailure":
        #         details = result["details"]
                
        #         output = f"⚠️ Write Quality Issues for: {file_path}\n"
        #         if purpose:
        #             output += f"Purpose: {purpose}\n"
                
        #         output += f"Quality Score: {details.get('quality_score', 0):.1%}\n"
        #         output += f"Status: {details.get('summary', 'Write failed quality checks')}\n\n"
                
        #         # Show failure analysis if available
        #         failure_analysis = details.get("failure_analysis", {})
        #         if failure_analysis:
        #             reasons = failure_analysis.get("failure_reasons", [])
        #             if reasons:
        #                 output += "❌ Failure Reasons:\n"
        #                 for reason in reasons:
        #                     output += f"   • {reason}\n"
                    
        #             fixes = failure_analysis.get("suggested_fixes", [])
        #             if fixes:
        #                 output += "\n💡 Suggested Fixes:\n"
        #                 for fix in fixes:
        #                     output += f"   • {fix}\n"
        #             output += "\n"
                
        #         # Show detailed formatting issues
        #         formatting = details.get("formatting", {})
        #         if formatting.get("errors"):
        #             output += f"❌ Formatting Errors ({len(formatting['errors'])}):\n"
        #             for error in formatting["errors"]:
        #                 output += f"   • {error}\n"
        #             output += "\n"
                
        #         if formatting.get("warnings"):
        #             output += f"⚠️  Formatting Warnings ({len(formatting['warnings'])}):\n"
        #             for warning in formatting["warnings"]:
        #                 output += f"   • {warning}\n"
        #             output += "\n"
                
        #         # Show detailed dependency issues  
        #         dependencies = details.get("dependencies", {})
        #         if dependencies.get("missing_dependencies"):
        #             output += f"❌ Missing Dependencies ({len(dependencies['missing_dependencies'])}):\n"
        #             for dep in dependencies["missing_dependencies"]:
        #                 output += f"   • {dep}\n"
        #             output += "\n"
                
        #         if dependencies.get("suggestions"):
        #             output += f"💡 Dependency Suggestions ({len(dependencies['suggestions'])}):\n"
        #             for suggestion in dependencies["suggestions"]:
        #                 output += f"   • {suggestion}\n"
        #             output += "\n"
                
        #         # Show general errors and warnings
        #         if details.get("errors"):
        #             output += f"❌ General Errors ({len(details['errors'])}):\n"
        #             for error in details["errors"]:
        #                 output += f"   • {error}\n"
        #             output += "\n"
                
        #         if details.get("warnings"):
        #             output += f"⚠️  General Warnings ({len(details['warnings'])}):\n"
        #             for warning in details["warnings"]:
        #                 output += f"   • {warning}\n"
                
        #         return output
        #     else:
        #         return f"❌ Write Error: {result['error']}"
                
        # Success case
        if "result" in result and isinstance(result["result"], dict):
            details = result["result"]

            output = f"✅ Write Success: {details.get('file_path', file_path)}\n"
            if purpose:
                output += f"Purpose: {purpose}\n"

            output += f"Quality Score: {details.get('quality_score', 1.0):.1%}\n"
            output += f"{details.get('summary', 'File written successfully')}\n\n"

            # Detailed formatting information
            formatting = details.get("formatting", {})
            # if formatting.get("changes_made"):
            #     output += f"🎨 Formatting Changes Made ({formatting['changes_made']}):\n"
            #     for change in formatting["changes_made"][:3]:  # Show first 3
            #         output += f"   • {change}\n"
            #     if len(formatting.get("changes_made", [])) > 3:
            #         output += f"   ... and {formatting['changes_made'] - 3} more changes\n"
            #     output += "\n"
            # else:
            output += f"ℹ️ changes made:{str(formatting)}"

            # Show formatting warnings if any
            if formatting.get("warnings"):
                output += f"⚠️  Formatting Warnings ({len(formatting['warnings'])}):\n"
                for warning in formatting["warnings"]:
                    output += f"   • {warning}\n"
                output += "\n"

            # Detailed dependency information
            dependencies = details.get("dependencies", {})
            imports_count = dependencies.get("imports_found", 0)
            if imports_count > 0:
                output += f"📦 {imports_count} imports analyzed\n"
                
                # Show resolved symbols if any
                resolved = dependencies.get("resolved_symbols", [])
                if resolved:
                    output += f"✅ Resolved Symbols ({len(resolved)}):\n"
                    for symbol in resolved[:5]:  # Show first 5
                        output += f"   • {symbol}\n"
                    if len(resolved) > 5:
                        output += f"   ... and {len(resolved) - 5} more symbols\n"
                    output += "\n"
                
                # Show missing dependencies with details
                missing = dependencies.get("missing_dependencies", [])
                if missing:
                    output += f"❌ Missing Dependencies ({len(missing)}):\n"
                    for dep in missing:
                        output += f"   • {dep}\n"
                    output += "\n"
                
                # Show specific suggestions
                suggestions = dependencies.get("suggestions", [])
                if suggestions:
                    output += f"💡 Dependency Suggestions ({len(suggestions)}):\n"
                    for suggestion in suggestions:
                        output += f"   • {suggestion}\n"
                    output += "\n"
                
                # Show duplicate definitions if any
                duplicates = dependencies.get("duplicate_definitions", [])
                if duplicates:
                    output += f"⚠️  Duplicate Definitions ({len(duplicates)}):\n"
                    for dup in duplicates:
                        output += f"   • {dup}\n"
                    output += "\n"
            
            # Show general errors and warnings with details
            if details.get("errors"):
                output += f"❌ General Issues ({len(details['errors'])}):\n"
                for error in details["errors"]:
                    output += f"   • {error}\n"
                output += "\n"
            
            if details.get("warnings"):
                output += f"⚠️  General Warnings ({len(details['warnings'])}):\n"
                for warning in details["warnings"]:
                    output += f"   • {warning}\n"
                output += "\n"

            # Final status
            if details.get('quality_score', 0) >= 0.8:
                output += "✅ Ready to save\n"
                
                # Check for auto-commit
                auto_commit_msg = await auto_commit_if_enabled(
                    file_path=file_path,
                    operation="write", 
                    purpose=purpose,
                    quality_score=details.get('quality_score')
                )
                if auto_commit_msg:
                    output += f"\n{auto_commit_msg}"
            else:
                output += f"⚠️  Quality below auto-save threshold ({details.get('quality_score', 0):.1%} < 80%)\n"
                output += "💡 Review and fix issues above before proceeding"
            
            return output

        # Fallback
        return result.get("result", "✅ Write operation completed")

    except Exception as e:
        return f"❌ Write tool error: {str(e)}"


@mcp.tool()
async def edit_file(
    target_file: str,
    instructions: str,
    code_edit: str,
    language: Optional[str] = None,
    save_to_file: Optional[bool] = True,
) -> str:
    """
    Use this tool to propose an edit to an existing file.

    This will be read by a less intelligent model, which will quickly apply the edit. You should make it clear what the edit is, while also minimizing the unchanged code you write.
    When writing the edit, you should specify each edit in sequence, with the special comment `// ... existing code ...` to represent unchanged code in between edited lines.

    For example:

    ```
    // ... existing code ...
    FIRST_EDIT
    // ... existing code ...
    SECOND_EDIT
    // ... existing code ...
    THIRD_EDIT
    // ... existing code ...
    ```

    You should still bias towards repeating as few lines of the original file as possible to convey the change.
    But, each edit should contain sufficient context of unchanged lines around the code you're editing to resolve ambiguity.
    DO NOT omit spans of pre-existing code (or comments) without using the `// ... existing code ...` comment to indicate its absence. If you omit the existing code comment, the model may inadvertently delete these lines.
    Make sure it is clear what the edit should be, and where it should be applied.

    Args:
        target_file: The target file to modify. You can use either a relative path in the workspace or an absolute path. If an absolute path is provided, it will be preserved as is.
        instructions: A single sentence instruction describing what you are going to do for the sketched edit. This is used to assist the less intelligent model in applying the edit. Please use the first person to describe what you are going to do. Dont repeat what you have said previously in normal messages. And use it to disambiguate uncertainty in the edit.
        code_edit: Specify ONLY the precise lines of code that you wish to edit. **NEVER specify or write out unchanged code**. Instead, represent all unchanged code using the comment of the language you're editing in - example: `// ... existing code ...`
        language: Programming language (auto-detected if not provided)
        save_to_file: Whether to save to file after processing (default: True)
    """
    try:
        payload = {
            "target_file": target_file,
            "instructions": instructions,
            "code_edit": code_edit,
            "language": language,
            "save_to_file": save_to_file,
        }

        start_time=time.time()
        try:
        
            result = await asyncio.wait_for(make_request("POST", "/edit", json=payload),timeout=30.0)
        except asyncio.TimeoutError:
            duration=time.time()-start_time
            return f"""⏰ Edit Processing Timeout ({duration:.1f}s)

                            📄 File: {target_file}
                            🎯 Instructions: {instructions[:80]}{'...' if len(instructions) > 80 else ''}
                            
                            🔄 What's happening:
                               • Edit request sent to Gemini API
                               • Processing taking longer than expected
                               • Request timed out to prevent Claude Desktop timeout
                            
                            💡 Recommendations:
                            1️⃣ Wait 30-60 seconds, then check if edit completed:
                               read_code_tool(file_path="{target_file}", start_line=1, end_line=20)
                            
                            2️⃣ Check for partial changes:
                               git_tool(operation="diff", file_path="{target_file}")
                            
                            3️⃣ For complex edits, try breaking into smaller parts:
                               • Edit one function at a time
                               • Use shorter, more specific instructions
                               • Target smaller code sections
                            
                            ⚠️  Large files or complex instructions may exceed timeout limits."""
                                    
        # Handle both success and failure responses
        if "error" in result:
            # Check if it's a detailed error response
            if "details" in result and result.get("error_type") == "EditQualityFailure":
                details = result["details"]

                output = f"⚠️ Edit Quality Issues for: {target_file}\n"
                output += f"Instructions: {instructions}\n"
                output += f"Quality Score: {details.get('quality_score', 0):.1%}\n"
                output += f"Status: {details.get('summary', 'Edit failed')}\n\n"

                # Show failure analysis if available
                failure_analysis = details.get("failure_analysis", {})
                if failure_analysis:
                    reasons = failure_analysis.get("failure_reasons", [])
                    if reasons:
                        output += "❌ Failure Reasons:\n"
                        for reason in reasons:
                            output += f"   • {reason}\n"
                    
                    fixes = failure_analysis.get("suggested_fixes", [])
                    if fixes:
                        output += "\n💡 Suggested Fixes:\n"
                        for fix in fixes:
                            output += f"   • {fix}\n"
                    output += "\n"

                # Processing details
                processing = details.get("processing", {})
                output += f"🤖 Gemini Edit: {'✅' if processing.get('gemini_edit_success') else '❌'}\n"
                output += f"🎨 Format Check: {'✅' if processing.get('format_success') else '❌'}\n"

                if processing.get("error_correction_attempts", 0) > 0:
                    output += f"🔄 Error Corrections: {processing['error_correction_attempts']} attempts\n"

                output += f"⚡ Processing: {processing.get('processing_time_seconds', 0):.1f}s\n"
                output += f"📞 Gemini Calls: {processing.get('total_gemini_calls', 0)}\n\n"

                # Content info
                content_info = details.get("content_info", {})
                if content_info.get("content_changed"):
                    output += f"📝 Content Length: {content_info.get('original_length', 0)} → {content_info.get('final_length', 0)}\n\n"

                # Show specific errors
                errors = details.get("errors", {})
                if errors.get("gemini_errors"):
                    output += f"❌ Gemini Errors ({len(errors['gemini_errors'])}):\n"
                    for error in errors["gemini_errors"]:
                        output += f"   • {error}\n"
                    output += "\n"

                if errors.get("format_errors"):
                    output += f"❌ Format Errors ({len(errors['format_errors'])}):\n"
                    for error in errors["format_errors"]:
                        output += f"   • {error}\n"
                    output += "\n"

                if errors.get("warnings"):
                    output += f"⚠️  Warnings ({len(errors['warnings'])}):\n"
                    for warning in errors["warnings"]:
                        output += f"   • {warning}\n"
                    output += "\n"

                return output
            else:
                # Simple error response
                return f"❌ Edit Error: {result['error']}"

        # Success case - show detailed information
        if "result" in result and isinstance(result["result"], dict):
            details = result["result"]

            output = f"✅ Write Success: {details.get('file_path', target_file)}\n"
            if instructions:
                output += f"Purpose: {instructions}\n"

            output += f"Quality Score: {details.get('quality_score', 1.0):.1%}\n"
            output += f"{details.get('summary', 'File written successfully')}\n\n"

            # Detailed formatting information
            formatting = details.get("formatting", {})
            if formatting.get("changes_made"):
                output += f"🎨 Formatting Changes Made ({str(formatting['changes_made'])}):\n"

            # Show formatting warnings with actual details
            if formatting.get("warnings"):
                output += f"⚠️  Formatting Warnings ({len(formatting['warnings'])}):\n"
                for warning in formatting["warnings"]:
                    output += f"   • {warning}\n"
                output += "\n"

            # Detailed dependency information
            dependencies = details.get("dependencies", {})
            imports_count = dependencies.get("imports_found", 0)
            if imports_count > 0:
                output += f"📦 {imports_count} imports analyzed\n"
                
                # Show resolved symbols if any
                resolved = dependencies.get("resolved_symbols", [])
                if resolved:
                    output += f"✅ Resolved Symbols ({len(resolved)}):\n"
                    for symbol in resolved[:5]:  # Show first 5
                        output += f"   • {symbol}\n"
                    if len(resolved) > 5:
                        output += f"   ... and {len(resolved) - 5} more symbols\n"
                    output += "\n"
                
                # Show missing dependencies with actual names
                missing = dependencies.get("missing_dependencies", [])
                if missing:
                    output += f"❌ Missing Dependencies ({len(missing)}):\n"
                    for dep in missing:
                        output += f"   • {dep}\n"
                    output += "\n"
                
                # Show specific suggestions
                suggestions = dependencies.get("suggestions", [])
                if suggestions:
                    output += f"💡 Dependency Suggestions ({len(suggestions)}):\n"
                    for suggestion in suggestions:
                        output += f"   • {suggestion}\n"
                    output += "\n"
                
                # Show duplicate definitions if any
                duplicates = dependencies.get("duplicate_definitions", [])
                if duplicates:
                    output += f"⚠️  Duplicate Definitions ({len(duplicates)}):\n"
                    for dup in duplicates:
                        output += f"   • {dup}\n"
                    output += "\n"
            
            # Show general errors and warnings with details
            if details.get("errors"):
                output += f"❌ General Issues ({len(details['errors'])}):\n"
                for error in details["errors"]:
                    output += f"   • {error}\n"
                output += "\n"
            
            if details.get("warnings"):
                output += f"⚠️  General Warnings ({len(details['warnings'])}):\n"
                for warning in details["warnings"]:
                    output += f"   • {warning}\n"
                output += "\n"

            # Final status
            if details.get('quality_score', 0) >= 0.8:
                output += "✅ Ready to save\n"
                
                # Check for auto-commit
                auto_commit_msg = await auto_commit_if_enabled(
                    file_path=target_file,
                    operation="write", 
                    purpose=instructions,
                    quality_score=details.get('quality_score')
                )
                if auto_commit_msg:
                    output += f"\n{auto_commit_msg}"
            else:
                output += f"⚠️  Quality below auto-save threshold ({details.get('quality_score', 0):.1%} < 80%)\n"
                output += "💡 Review and fix issues above before proceeding"
            
            return output

        # Fallback
        return result.get("result", "✅ Write operation completed")

    except Exception as e:
        return f"❌ Write tool error: {str(e)}"


@mcp.tool()
async def project_context_tool(
    operation: str, max_depth: Optional[int] = 5, include_hidden: Optional[bool] = False
) -> str:
    """
    Project context and structure tool

    Args:
        operation: Context operation (structure, info, dependencies, files)
        max_depth: Maximum depth for structure traversal
        include_hidden: Whether to include hidden files/folders
    """
    try:
        payload = {
            "operation": operation,
            "max_depth": max_depth,
            "include_hidden": include_hidden,
        }

        result = await make_request("GET", "/project/context", params=payload)

        if "error" in result:
            return f"❌ Project Context Error: {result['error']}"

        return str(result.get("result", "✅ Project context retrieved"))

    except Exception as e:
        return f"❌ Project context tool error: {str(e)}"

@mcp.prompt(name="system prompt")
def system_prompt()->str:
    return GENERAL_DEV_PROMPT


@mcp.tool()
async def search_tool(
    query: str,
    search_type: str = "semantic",
    file_pattern: Optional[str] = None,
    symbol_type: Optional[str] = None,
    use_regex: bool = False,
    case_sensitive: bool = False,
    fuzzy: bool = True,
    max_results: int = 10,
) -> str:
    """
    Enhanced search tool with multiple search modes

    Args:
        query: Search query
        search_type: Search mode - "semantic", "fuzzy_symbol", "text", "symbol_exact"
        file_pattern: File pattern filter (e.g., "*.py", "*.js")
        symbol_type: Symbol type filter (function, class, interface, type, enum)
        use_regex: Use regex patterns (for text search)
        case_sensitive: Case sensitive matching (for text search)
        fuzzy: Enable fuzzy matching (for symbol search)
        max_results: Maximum number of results (1-50)
        
    Search Types:
        - semantic: AI-powered semantic code search
        - fuzzy_symbol: Fuzzy symbol name matching with scoring
        - text: Text content search with regex support
        - symbol_exact: Exact symbol name matching
    """
    try:
        # Validate search type
        valid_types = ["semantic", "fuzzy_symbol", "text", "symbol_exact"]
        if search_type not in valid_types:
            return f"❌ Invalid search type. Valid types: {', '.join(valid_types)}"

        # Build request payload
        payload = {
            "query": query,
            "search_type": search_type,
            "file_pattern": file_pattern,
            "symbol_type": symbol_type,
            "use_regex": use_regex,
            "case_sensitive": case_sensitive,
            "fuzzy": fuzzy,
            "max_results": min(max(1, max_results), 50),
        }

        # Use appropriate endpoint based on search type
        if search_type == "text":
            result = await make_request("POST", "/search/text", params={
                "query": query,
                "file_pattern": file_pattern or "*.py",
                "use_regex": use_regex,
                "case_sensitive": case_sensitive,
                "max_results": max_results
            })
        elif search_type in ["fuzzy_symbol", "symbol_exact"]:
            result = await make_request("POST", "/search/symbols", params={
                "query": query,
                "symbol_type": symbol_type,
                "file_pattern": file_pattern,
                "fuzzy": fuzzy if search_type == "fuzzy_symbol" else False,
                "max_results": max_results
            })
        else:
            # Semantic search (existing endpoint)
            result = await make_request("POST", "/search", json=payload)

        if "error" in result:
            return f"❌ Search Error: {result['error']}"

        if "result" in result and isinstance(result["result"], dict):
            search_data = result["result"]

            output = f"🔍 {search_type.title()} Search Results: '{query}'\n"
            if search_data.get('file_pattern'):
                output += f"📁 Pattern: {search_data['file_pattern']}\n"
            if search_data.get('symbol_type'):
                output += f"🏷️ Type: {search_data['symbol_type']}\n"
            
            output += f"📊 Total: {search_data.get('total_results', 0)} results\n\n"

            results = search_data.get("results", [])

            if not results:
                output += "No results found."
                if search_type == "fuzzy_symbol":
                    output += "\n💡 Try lowering min_score or using broader query terms."
                return output

            for i, search_result in enumerate(results, 1):
                output += f"{i}. 📄 {search_result.get('file_path', 'Unknown')}\n"

                if search_type in ["fuzzy_symbol", "symbol_exact"]:
                    output += f"   🏷️ Symbol: {search_result.get('symbol_name', 'Unknown')}\n"
                    output += f"   📝 Type: {search_result.get('symbol_type', 'unknown')}\n"
                    output += f"   📍 Lines: {search_result.get('line_start', '?')}-{search_result.get('line_end', '?')}\n"
                    if search_result.get('relevance_score'):
                        output += f"   📊 Score: {search_result['relevance_score']:.3f}\n"
                    if search_result.get('signature'):
                        output += f"   ✏️ Signature: {search_result['signature']}\n"
                
                elif search_type == "text":
                    output += f"   📍 Line: {search_result.get('line_number', '?')}\n"
                    content = search_result.get('content', '')
                    if content:
                        content = content[:80] + "..." if len(content) > 80 else content
                        output += f"   📝 Content: {content}\n"
                
                else:  # semantic
                    if search_result.get("symbol_name"):
                        output += f"   🏷️ Symbol: {search_result['symbol_name']}\n"
                    output += f"   📝 Lines: {search_result.get('line_start', '?')}-{search_result.get('line_end', '?')}\n"
                    output += f"   🗃️ Type: {search_result.get('chunk_type', 'unknown')}\n"
                    output += f"   📊 Score: {search_result.get('relevance_score', 0):.3f}\n"
                    if search_result.get('signature'):
                        output += f"   ✏️ Signature: {search_result['signature']}\n"
                    if search_result.get('docstring'):
                        docstring = search_result['docstring'][:100] + "..." if len(search_result.get('docstring', '')) > 100 else search_result.get('docstring', '')
                        if docstring:
                            output += f"   📚 Doc: {docstring}\n"

                output += "\n"

            return output

        return result.get("result", "✅ Search completed")

    except Exception as e:
        return f"❌ Search tool error: {str(e)}"


@mcp.tool()
async def code_analysis_tool(
    operation: str, file_path: str, analysis_type: Optional[str] = "basic"
) -> str:
    """
    Code analysis tool for syntax checking, linting, etc.

    Args:
        operation: Analysis operation (syntax, lint, imports, dependencies)
        file_path: Path to file to analyze
        analysis_type: Type of analysis (basic, advanced, full)
    """
    try:
        payload = {
            "operation": operation,
            "file_path": file_path,
            "analysis_type": analysis_type,
        }

        result = await make_request("POST", "/code/analyze", json=payload)

        if "error" in result:
            return f"❌ Code Analysis Error: {result['error']}"

        return result.get("result", "✅ Code analysis completed")

    except Exception as e:
        return f"❌ Code analysis tool error: {str(e)}"


@mcp.tool()
async def execute_tool(
    command: str,
    args: Optional[List[str]] = None,
    timeout: Optional[int] = 60,
    cwd: Optional[str] = None,
) -> str:
    """
    Command execution tool

    Args:
        command: Command to execute
        args: Command arguments
        timeout: Execution timeout in seconds
        cwd: Working directory for command execution
    """
    try:
        payload = {
            "command": command,
            "args": args or [],
            "timeout": timeout,
            "cwd": cwd,
        }

        result = await make_request("POST", "/execute", json=payload)

        if "error" in result:
            return f"❌ Execution Error: {result['error']}"

        return result.get("result", "✅ Command executed")

    except Exception as e:
        return f"❌ Execute tool error: {str(e)}"



@mcp.tool()
async def list_file_symbols_tool(file_path: str) -> str:
    """
    List all symbols (functions, classes, interfaces) in a specific file

    Args:
        file_path: Path to the file to analyze
    """
    try:
        result = await make_request("GET", f"/search/symbols/{file_path}")

        if "error" in result:
            return f"❌ Error: {result['error']}"

        if "result" in result and isinstance(result["result"], dict):
            file_info = result["result"]

            if file_info.get("error"):
                return f"❌ Error analyzing {file_path}: {file_info['error']}"

            output = f"📄 Symbols in {file_info.get('file', file_path)}\n"
            output += f"📊 File: {file_info.get('total_lines', 0)} lines, {file_info.get('file_size', 0)} bytes\n"
            output += f"🔒 Hash: {file_info.get('file_hash', 'unknown')[:8]}...\n\n"

            symbols = file_info.get("symbols", [])
            
            if not symbols:
                output += "No symbols found in this file."
                return output

            # Group symbols by type
            by_type = {}
            for symbol in symbols:
                symbol_type = symbol.get('type', 'unknown')
                if symbol_type not in by_type:
                    by_type[symbol_type] = []
                by_type[symbol_type].append(symbol)

            for symbol_type, type_symbols in sorted(by_type.items()):
                output += f"🏷️ {symbol_type.upper()} ({len(type_symbols)}):\n"
                for symbol in sorted(type_symbols, key=lambda x: x.get('line', 0)):
                    output += f"   📍 Line {symbol.get('line', '?'):4d}: {symbol.get('name', 'Unknown')}\n"
                    if symbol.get('signature'):
                        output += f"        ✏️ {symbol['signature']}\n"
                output += "\n"

            return output

        return result.get("result", "✅ Symbol listing completed")

    except Exception as e:
        return f"❌ List symbols error: {str(e)}"


@mcp.tool()
async def read_code_tool(
    file_path: str,
    symbol_name: Optional[str] = None,
    occurrence: int = 1,
    start_line: Optional[int] = None,  # Changed from int to str to handle empty strings
    end_line: Optional[int] = None,    # Changed from int to str to handle empty strings
    with_line_numbers: bool = True
) -> str:
    """
    Read code content from files with multiple modes
    
    Modes:
    1. Symbol reading: Provide symbol_name to read specific functions/classes/interfaces
    2. Line range: Provide start_line and end_line for specific line ranges  
    3. Whole file: Leave all parameters as defaults
    
    Args:
        file_path: Path to the file to read
        symbol_name: Name of symbol (function/class/interface) to read
        occurrence: Which occurrence of the symbol if multiple exist (default: 1)
        start_line: Start line number for range reading (1-indexed)
        end_line: End line number for range reading (inclusive)
        with_line_numbers: Include line numbers in output (default: True)
    
    Examples:
        read_code_tool("src/main.py", symbol_name="process_data")
        read_code_tool("src/utils.py", start_line="10", end_line="25")
        read_code_tool("config.json")
    """
    try:
        # Handle empty strings and convert to proper types
        start_line_int = None
        end_line_int = None
        
        # Convert empty strings to None and parse integers
        if start_line and isinstance(start_line, str) and str(start_line).strip() and str(start_line).strip() != "":
            try:
                start_line_int = int(start_line)
            except ValueError:
                return f"❌ Invalid start_line: '{start_line}' must be a valid integer"
                
        if end_line and isinstance(end_line, str) and str(end_line).strip() and str(end_line).strip() != "":
            try:
                end_line_int = int(end_line)
            except ValueError:
                return f"❌ Invalid end_line: '{end_line}' must be a valid integer"
        
        # Handle empty symbol_name
        if not symbol_name or symbol_name.strip() == "":
            symbol_name = None
        
        # Validate parameters
        if symbol_name and (start_line_int is not None or end_line_int is not None):
            return "❌ Cannot specify both symbol_name and line range. Use one or the other."
        
        if (start_line_int is not None) != (end_line_int is not None):
            return "❌ Must specify both start_line and end_line for range reading."
        
        if occurrence < 1:
            return "❌ Occurrence must be 1 or greater."
        
        # Build request parameters
        params = {
            "file_path": file_path,
            "with_line_numbers": with_line_numbers
        }
        
        if symbol_name:
            params.update({
                "symbol_name": symbol_name,
                "occurrence": occurrence
            })
        elif start_line_int is not None and end_line_int is not None:
            params.update({
                "start_line": start_line_int,
                "end_line": end_line_int
            })
        
        # Make request to FastAPI
        result = await make_request("POST", "/read", params=params)
        
        if "error" in result:
            return f"❌ Read Error: {result['error']}"
        
        if "result" in result and isinstance(result["result"], dict):
            read_data = result["result"]
            
            if not read_data.get("success"):
                return f"❌ Read failed: {read_data.get('error', 'Unknown error')}"
            
            # Format successful response
            output = f"📄 Code Content: {read_data.get('file_path', file_path)}\n"
            
            mode = read_data.get('mode', 'unknown')
            line_range = read_data.get('line_range', {})
            file_stats = read_data.get('file_stats', {})
            
            # Add metadata
            if mode.startswith('symbol_'):
                symbol_type = mode.split('_')[-1]
                output += f"🎯 Mode: {symbol_type} symbol"
                if symbol_name:
                    output += f" '{symbol_name}'"
                if occurrence > 1:
                    output += f" (occurrence {occurrence})"
                output += "\n"
            elif mode == 'line_range':
                output += f"📍 Mode: Line range {start_line_int}-{end_line_int}\n"
            else:
                output += "📋 Mode: Whole file\n"
            
            # Add line information
            output += f"📝 Lines: {line_range.get('start', '?')}-{line_range.get('end', '?')} "
            output += f"({line_range.get('total_lines', '?')} lines shown)\n"
            
            # Add file stats
            if file_stats:
                output += f"📊 File: {file_stats.get('total_file_lines', '?')} total lines, "
                file_size = file_stats.get('file_size', 0)
                if file_size > 1024:
                    output += f"{file_size // 1024}KB\n"
                else:
                    output += f"{file_size}B\n"
            
            output += "\n" + "─" * 50 + "\n"
            
            # Add the actual code content
            content = read_data.get('content', '')
            output += content
            
            return output
        
        return result.get("result", "✅ Read completed")
        
    except Exception as e:
        return f"❌ Read tool error: {str(e)}"

@mcp.tool() 
async def read_symbol_from_database(symbol_name: str, file_path: Optional[str] = None) -> str:
    """
    Find and read a symbol from the codebase database
    
    This tool searches for symbols in the indexed database and shows all occurrences
    with their locations and content.
    
    Args:
        symbol_name: Name of the symbol to find (function, class, interface, etc.)
        file_path: Optional file path to limit search to specific file
    """
    try:
        # Search for symbol first
        search_params = {
            "query": symbol_name,
            "search_type": "symbol_exact",
            "max_results": 20
        }
        
        if file_path:
            search_params["file_pattern"] = file_path
        
        search_result = await make_request("POST", "/search/symbols", params=search_params)
        
        if "error" in search_result:
            return f"❌ Search Error: {search_result['error']}"
        
        if "result" not in search_result or not search_result["result"].get("results"):
            return f"❌ Symbol '{symbol_name}' not found in database"
        
        search_data = search_result["result"]
        symbols = search_data["results"]
        
        output = f"🔍 Found {len(symbols)} occurrences of symbol '{symbol_name}':\n\n"
        
        # Group by file
        by_file = {}
        for symbol in symbols:
            file = symbol["file_path"]
            if file not in by_file:
                by_file[file] = []
            by_file[file].append(symbol)
        
        # Show each occurrence
        for file, file_symbols in by_file.items():
            output += f"📄 {file}:\n"
            
            for i, symbol in enumerate(file_symbols, 1):
                output += f"  {i}. {symbol['symbol_type']} at lines {symbol['line_start']}-{symbol['line_end']}\n"
                if symbol.get('signature'):
                    output += f"     ✏️ {symbol['signature']}\n"
            
            # If only one file and one symbol, read its content
            if len(by_file) == 1 and len(file_symbols) == 1:
                symbol = file_symbols[0]
                read_result = await read_code_tool(
                    file_path=file,
                    symbol_name=symbol_name,
                    occurrence=1,
                    with_line_numbers=True
                )
                
                output += f"\n📖 Content:\n{read_result}\n"
            
            output += "\n"
        
        if len(by_file) > 1 or sum(len(syms) for syms in by_file.values()) > 1:
            output += "💡 Use read_code_tool() with specific file_path and occurrence to read individual symbols."
        
        return output
        
    except Exception as e:
        return f"❌ Symbol database read error: {str(e)}"

@mcp.tool()
async def project_structure_tool(
    operation: str = "structure",
    max_depth: int = 5,
    include_hidden: bool = False
) -> str:
    """
    Enhanced project structure tool with detailed file information
    
    Args:
        operation: Operation type - "info", "structure", or "dependencies"
        max_depth: Maximum directory depth to traverse (default: 5)
        include_hidden: Include hidden files and directories (default: False)
        
    Operations:
        - info: Show project statistics and overview
        - structure: Display enhanced directory tree with line counts and file sizes
        - dependencies: Show project dependencies from configuration files
    """
    try:
        valid_operations = ["info", "structure", "dependencies"]
        if operation not in valid_operations:
            return f"❌ Invalid operation. Valid operations: {', '.join(valid_operations)}"
        
        params = {
            "operation": operation,
            "max_depth": max_depth,
            "include_hidden": include_hidden
        }
        
        result = await make_request("GET", "/project/context", params=params)
        
        if "error" in result:
            return f"❌ Project {operation} error: {result['error']}"
        
        if "result" in result and isinstance(result["result"], dict):
            data = result["result"]
            
            if operation == "info":
                summary = data.get("summary", {})
                output = "📊 Project Information\n"
                output += f"Directory: {data.get('working_directory', 'unknown')}\n"
                output += f"Files: {summary.get('total_files', 0):,}\n" 
                output += f"Size: {summary.get('total_size', '0B')}\n"
                output += f"Lines: {summary.get('total_lines', '0')}\n\n"
                
                project_files = data.get("project_files", [])
                if project_files:
                    output += f"Project files: {', '.join(project_files)}\n\n"
                
                file_types = data.get("file_types", [])[:5]
                if file_types:
                    output += "Top file types:\n"
                    for ext, count in file_types:
                        output += f"  {ext}: {count:,}\n"
                
                return output
            
            elif operation == "structure":
                summary = data.get("summary", {})
                output = "🌳 Project Structure\n"
                output += f"Total: {summary.get('total_files', 0):,} files, {summary.get('total_size', '0B')}, {summary.get('total_lines', '0')} lines\n\n"
                output += data.get("tree_structure", "")
                return output
            
            elif operation == "dependencies":
                deps = data.get("dependencies", {})
                if not deps:
                    return "📦 No dependency files found"
                
                output = f"📦 Project Dependencies ({len(deps)} files)\n\n"
                for file_desc, content in deps.items():
                    output += f"📄 {file_desc}\n"
                    output += "─" * 40 + "\n"
                    output += content[:800]  # Truncate for display
                    if len(content) > 800:
                        output += "\n... (truncated)"
                    output += "\n\n"
                
                return output
        
        return result.get("result", f"✅ Project {operation} completed")
        
    except Exception as e:
        return f"❌ Project structure tool error: {str(e)}"

@mcp.tool()
async def list_directory_tool(
    directory_path: str = ".",
    max_depth: int = 2,
    include_hidden: bool = False,
    show_metadata: bool = True,
    respect_gitignore: bool = True,
    files_only: bool = False,
    dirs_only: bool = False,
    tree_format: bool = True
) -> str:
    """
    List directory contents with configurable depth and filtering

    Args:
        directory_path: Directory to list (relative to project root, default: ".")
        max_depth: Maximum depth to traverse (0-10, default: 2)
        include_hidden: Include hidden files/directories (default: False)
        show_metadata: Include file sizes and line counts (default: True)
        respect_gitignore: Filter based on .gitignore patterns (default: True)
        files_only: Show only files, not directories (default: False)
        dirs_only: Show only directories, not files (default: False)
        tree_format: Display in tree format vs flat list (default: True)
    """
    try:
        # Validate parameters
        if max_depth < 0 or max_depth > 10:
            return "❌ max_depth must be between 0 and 10"
        
        if files_only and dirs_only:
            return "❌ Cannot set both files_only and dirs_only to True"

        # Make request to FastAPI
        params = {
            "directory_path": directory_path,
            "max_depth": max_depth,
            "include_hidden": include_hidden,
            "show_metadata": show_metadata,
            "respect_gitignore": respect_gitignore,
            "files_only": files_only,
            "dirs_only": dirs_only
        }

        result = await make_request("GET", "/directory/list", params=params)

        if "error" in result:
            return f"❌ Directory Error: {result['error']}"

        if "result" in result and isinstance(result["result"], dict):
            data = result["result"]

            # Handle errors from directory lister
            if "error" in data:
                return f"❌ {data['error']}"

            output = []
            
            # Header
            dir_name = data.get("directory", ".")
            summary = data.get("summary", {})
            
            output.append(f"📁 Directory: {dir_name}")
            output.append(f"📊 Summary: {summary.get('total_files', 0)} files, {summary.get('total_directories', 0)} directories")
            if show_metadata:
                output.append(f"💾 Total Size: {summary.get('total_size_formatted', '0 B')}")
            output.append("")

            # Items
            items = data.get("items", [])
            if not items:
                output.append("📭 Directory is empty")
                return "\n".join(output)

            if tree_format:
                # Tree format
                for item in items:
                    prefix = item.get("tree_prefix", "")
                    name = item.get("name", "Unknown")
                    
                    if item.get("error"):
                        output.append(f"{prefix}❌ {name} - {item['error']}")
                        continue
                    
                    # Format based on type
                    if item.get("is_directory", False):
                        output.append(f"{prefix}📁 {name}/")
                    else:
                        line = f"{prefix}📄 {name}"
                        
                        if show_metadata:
                            # Add file metadata
                            metadata_parts = []
                            
                            if item.get("size"):
                                size_formatted = data.get("directory_lister", {}).get("format_size", lambda x: f"{x}B")(item["size"])
                                metadata_parts.append(size_formatted)
                            
                            if item.get("line_count"):
                                metadata_parts.append(f"{item['line_count']} lines")
                            
                            if item.get("file_type"):
                                metadata_parts.append(item["file_type"])
                            
                            if metadata_parts:
                                line += f" ({', '.join(metadata_parts)})"
                        
                        output.append(line)
            else:
                # Flat format
                files = [item for item in items if not item.get("is_directory")]
                directories = [item for item in items if item.get("is_directory")]
                
                if directories:
                    output.append("📁 Directories:")
                    for item in directories:
                        output.append(f"   {item.get('name', 'Unknown')}/")
                    output.append("")
                
                if files:
                    output.append("📄 Files:")
                    for item in files:
                        name = item.get('name', 'Unknown')
                        if show_metadata and item.get('size'):
                            size_str = f" ({item['size']} bytes"
                            if item.get('line_count'):
                                size_str += f", {item['line_count']} lines"
                            size_str += ")"
                            name += size_str
                        output.append(f"   {name}")

            # Footer with options
            options = data.get("options", {})
            option_strs = []
            if options.get("include_hidden"):
                option_strs.append("hidden files shown")
            if options.get("files_only"):
                option_strs.append("files only")
            if options.get("dirs_only"):
                option_strs.append("directories only")
            if not options.get("respect_gitignore"):
                option_strs.append("gitignore ignored")
            
            if option_strs:
                output.append("")
                output.append(f"ℹ️  Options: {', '.join(option_strs)}")

            return "\n".join(output)

        return result.get("result", "✅ Directory listing completed")

    except Exception as e:
        return f"❌ Directory tool error: {str(e)}"


@mcp.tool()
async def show_directory_tree(directory_path: str = ".", max_depth: int = 3) -> str:
    """
    Show directory structure as a clean tree (optimized for LLM context)

    Args:
        directory_path: Directory to show tree for (default: ".")  
        max_depth: Maximum depth for tree (1-5, default: 3)
    """
    try:
        if max_depth < 1 or max_depth > 5:
            return "❌ max_depth must be between 1 and 5"

        result = await make_request("GET", "/directory/tree", params={
            "directory_path":directory_path,
            "max_depth": max_depth
        })

        if "error" in result:
            return f"❌ Tree Error: {result['error']}"

        if "result" in result and isinstance(result["result"], dict):
            data = result["result"]
            
            if "error" in data:
                return f"❌ {data['error']}"

            output = []
            
            # Header
            dir_name = data.get("directory", ".")
            summary = data.get("summary", {})
            
            output.append(f"📁 {dir_name}/")
            output.append(data.get("tree", ""))
            output.append("")
            output.append(f"📊 {summary.get('total_files', 0)} files, {summary.get('total_directories', 0)} directories")
            
            return "\n".join(output)

        return result.get("result", "✅ Tree display completed")

    except Exception as e:
        return f"❌ Tree tool error: {str(e)}"

# =============================================================================
# MCP RESOURCES
# =============================================================================


@mcp.resource("project://health")
async def health_check() -> str:
    """Health check resource"""
    try:
        result = await make_request("GET", "/health")
        if "error" in result:
            return f"❌ FastAPI server unhealthy: {result['error']}"

        # Format health check results
        if "result" in result and isinstance(result["result"], dict):
            health_data = result["result"]
            output = "✅ System Health Status\n"
            output += f"Status: {health_data.get('status', 'unknown')}\n"
            output += f"Working Directory: {health_data.get('working_directory', 'unknown')}\n"
            output += (
                f"Search Engine: {'✅' if health_data.get('search_engine') else '❌'}\n"
            )
            output += f"Write Pipeline: {'✅' if health_data.get('write_pipeline') else '❌'}\n"
            output += (
                f"Edit Pipeline: {'✅' if health_data.get('edit_pipeline') else '❌'}\n"
            )
            return output

        return "✅ MCP Server and FastAPI backend are healthy"
    except Exception as e:
        return f"❌ Health check failed: {str(e)}"

@mcp.resource("git://context")
async def get_git_context_summary() -> str:
    """Get a quick git context summary for LLM awareness"""
    try:
        # Get status and recent log
        status_result = await make_request("POST", "/git", json={"operation": "status"})
        log_result = await make_request("POST", "/git", json={"operation": "log", "max_results": 5})
        
        if "error" in status_result:
            return "⚠️ No git context available"
        
        output = "📋 Quick Git Context:\n"
        
        # Status summary
        if "result" in status_result:
            status_data = status_result["result"].get("data", {}).get("status", {})
            branch = status_data.get("current_branch", "unknown")
            modified = len(status_data.get("modified_files", []))
            untracked = len(status_data.get("untracked_files", []))
            
            output += f"Branch: {branch}"
            if modified or untracked:
                output += f" ({modified} modified, {untracked} untracked)"
            else:
                output += " (clean)"
        
        # Recent activity
        if "result" in log_result and "error" not in log_result:
            commits = log_result["result"].get("data", {}).get("commits", [])
            if commits:
                latest = commits[0]
                output += f"\nLatest: {latest.get('short_hash', '???')} - {latest.get('message', 'No message')[:50]}"
        
        return output
        
    except Exception:
        return "⚠️ Git context unavailable"


@mcp.resource("project://status")
async def server_status() -> str:
    """Server status resource"""
    try:
        result = await make_request("GET", "/status")
        if "error" in result:
            return f"Server status unavailable: {result['error']}"

        if "result" in result:
            return json.dumps(result["result"], indent=2)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"❌ Status check failed: {str(e)}"

@mcp.resource("project://info")
async def get_project_info() -> str:
    """Enhanced project information with detailed statistics"""
    try:
        result = await make_request("GET", "/project/context", params={"operation": "info"})
        
        if "error" in result:
            return f"❌ Project info unavailable: {result['error']}"
        
        if "result" in result and isinstance(result["result"], dict):
            info = result["result"]
            
            output = "📁 Project Information\n"
            output += f"Working Directory: {info.get('working_directory', 'unknown')}\n\n"
            
            summary = info.get("summary", {})
            output += "📊 Project Statistics:\n"
            output += f"   Files: {summary.get('total_files', 0):,}\n"
            output += f"   Size: {summary.get('total_size', '0B')}\n"
            output += f"   Lines: {summary.get('total_lines', '0')}\n\n"
            
            project_files = info.get("project_files", [])
            if project_files:
                output += "📋 Project Files Found:\n"
                for pf in project_files:
                    output += f"   • {pf}\n"
                output += "\n"
            
            file_types = info.get("file_types", [])[:5]  # Top 5
            if file_types:
                output += "📂 Top File Types:\n"
                for ext, count in file_types:
                    output += f"   {ext}: {count:,} files\n"
            
            return output
        
        return "📁 Project information retrieved"
        
    except Exception as e:
        return f"❌ Project info error: {str(e)}"


@mcp.resource("project://structure")
async def get_project_structure() -> str:
    """Enhanced project structure with line counts and file sizes"""
    try:
        result = await make_request("GET", "/project/context", params={
            "operation": "structure",
            "max_depth": 6,
            "include_hidden": False
        })
        
        if "error" in result:
            return f"❌ Project structure unavailable: {result['error']}"
        
        if "result" in result and isinstance(result["result"], dict):
            structure_data = result["result"]
            
            output = "🌳 Enhanced Project Structure\n\n"
            
            summary = structure_data.get("summary", {})
            output += f"📊 Summary: {summary.get('total_files', 0):,} files, "
            output += f"{summary.get('total_size', '0B')}, "
            output += f"{summary.get('total_lines', '0')} lines\n\n"
            
            tree = structure_data.get("tree_structure", "")
            output += tree
            
            output += "\n💡 Legend:\n"
            output += "   dir: directory with file count, total size, total lines\n"
            output += "   file: individual file with size and line count\n"
            
            return output
        
        return "🌳 Project structure retrieved"
        
    except Exception as e:
        return f"❌ Project structure error: {str(e)}"


@mcp.resource("project://dependencies") 
async def get_project_dependencies() -> str:
    """Project dependencies from various configuration files"""
    try:
        result = await make_request("GET", "/project/context", params={"operation": "dependencies"})
        
        if "error" in result:
            return f"❌ Dependencies unavailable: {result['error']}"
        
        if "result" in result and isinstance(result["result"], dict):
            deps_data = result["result"]
            
            dependency_files = deps_data.get("dependency_files", [])
            dependencies = deps_data.get("dependencies", {})
            
            if not dependency_files:
                return "📦 No dependency files found in project"
            
            output = "📦 Project Dependencies\n"
            output += f"Found {len(dependency_files)} dependency files:\n\n"
            
            for file_desc, content in dependencies.items():
                output += f"📄 {file_desc}\n"
                output += "─" * 50 + "\n"
                output += content[:1000]  # Limit content length
                if len(content) > 1000:
                    output += "\n... (truncated)"
                output += "\n\n"
            
            return output
        
        return "📦 Dependencies retrieved"
        
    except Exception as e:
        return f"❌ Dependencies error: {str(e)}"

# =============================================================================
# CLEANUP
# =============================================================================


async def cleanup():
    """Cleanup resources on shutdown"""
    global http_client
    if http_client:
        await http_client.aclose()
        http_client = None


def main():
    """Main entry point"""
    try:
        # Run the MCP server with stdio transport
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
    except Exception:
        sys.exit(1)
    finally:
        # Cleanup
        try:
            asyncio.run(cleanup())
        except Exception:
            pass


if __name__ == "__main__":
    main()
