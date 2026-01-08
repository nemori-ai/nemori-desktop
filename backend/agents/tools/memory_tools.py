"""
Agent Tools - LangChain 1.0 compatible memory search tools

These tools provide the agent with capabilities to search and retrieve
memories from the Nemori memory system using the modern @tool decorator pattern.
"""

import json
from typing import Optional, List, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langchain_core.tools import tool

from storage.database import Database
from storage.vector_store import VectorStore
from services.llm_service import LLMService


# ==================== Tool Input Schemas ====================

class SearchEpisodicInput(BaseModel):
    """Input schema for search_episodic_memory tool"""
    query: str = Field(description="The search query to find relevant episodic memories")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return (1-20)")


class SearchSemanticInput(BaseModel):
    """Input schema for search_semantic_memory tool"""
    query: str = Field(description="The search query to find relevant semantic memories")
    category: Optional[Literal[
        'career', 'finance', 'health', 'family', 'social',
        'growth', 'leisure', 'spirit', 'knowledge', 'preference'
    ]] = Field(default=None, description="Optional category filter")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return (1-20)")


class KeywordSearchInput(BaseModel):
    """Input schema for keyword_search tool"""
    keywords: List[str] = Field(description="List of keywords to search for (e.g. ['meeting', 'project']). Returns memories containing ANY of these keywords.")
    memory_type: Optional[Literal['episodic', 'semantic']] = Field(
        default=None,
        description="Optional: 'episodic' or 'semantic'. Omit to search both types."
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum results to return (default: 10)")


class TimeFilterInput(BaseModel):
    """Input schema for time_filter tool"""
    start_date: Optional[str] = Field(default=None, description="Start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(default=None, description="End date in YYYY-MM-DD format")
    days_ago: Optional[int] = Field(default=None, ge=1, description="Get memories from the last N days")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")


class GetUserProfileInput(BaseModel):
    """Input schema for get_user_profile tool"""
    categories: Optional[List[Literal[
        'career', 'finance', 'health', 'family', 'social',
        'growth', 'leisure', 'spirit'
    ]]] = Field(default=None, description="Optional list of categories to include")


class GetRecentActivityInput(BaseModel):
    """Input schema for get_recent_activity tool"""
    limit: int = Field(default=5, ge=1, le=20, description="Number of recent memories to retrieve")


class SearchChatHistoryInput(BaseModel):
    """Input schema for search_chat_history tool"""
    query: str = Field(description="Keyword or phrase to search for in chat messages")
    role: Optional[Literal['user', 'assistant']] = Field(
        default=None,
        description="Optional: filter by 'user' or 'assistant' messages. Omit to search both."
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results to return (default: 20)")


class ThinkInput(BaseModel):
    """Input schema for think tool"""
    thought: str = Field(description="A thought to think about. Use this to reason through complex problems, analyze tool results, or plan next steps.")


# ==================== Memory Search Tools ====================

@tool("search_episodic_memory", args_schema=SearchEpisodicInput)
async def search_episodic_memory(query: str, top_k: int = 5) -> str:
    """Search through the user's episodic memories (life events, experiences, activities).

    Use this tool when you need to find specific events, experiences, or activities
    from the user's past. Episodic memories contain narrative descriptions of what
    the user did, thought, or experienced.

    Returns the most relevant memories based on semantic similarity to your query.
    """
    try:
        db = Database.get_instance()
        vector_store = VectorStore.get_instance()
        llm = LLMService.get_instance()

        if not llm.is_embedding_configured():
            return json.dumps({
                "success": False,
                "error": "Embedding model not configured",
                "results": []
            })

        # Generate query embedding
        query_embedding = await llm.embed_single(query)

        # Search vector store for episodic memories
        results = vector_store.query(
            query_embedding=query_embedding,
            n_results=top_k,
            where={'type': 'episodic'}
        )

        memories = []
        if results['ids'] and results['ids'][0]:
            for i, mem_id in enumerate(results['ids'][0]):
                memory = await db.get_episodic_memory(mem_id)
                if memory:
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    memories.append({
                        "id": memory['id'],
                        "title": memory['title'],
                        "content": memory['content'],
                        "start_time": datetime.fromtimestamp(memory['start_time']/1000).isoformat(),
                        "end_time": datetime.fromtimestamp(memory['end_time']/1000).isoformat(),
                        "relevance_score": round(1 - distance, 3)
                    })

        return json.dumps({
            "success": True,
            "query": query,
            "results_count": len(memories),
            "results": memories
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        })


@tool("search_semantic_memory", args_schema=SearchSemanticInput)
async def search_semantic_memory(
    query: str,
    category: Optional[str] = None,
    top_k: int = 5
) -> str:
    """Search through the user's semantic memories (facts, knowledge, preferences, life insights).

    Semantic memories are organized into 8 life categories:
    - career: Work, projects, professional skills
    - finance: Money, investments, spending
    - health: Physical health, exercise, diet
    - family: Family members, relationships
    - social: Friends, networking, community
    - growth: Learning, education, self-improvement
    - leisure: Hobbies, entertainment, travel
    - spirit: Mental health, values, philosophy

    Use this when you need to understand the user's preferences, knowledge, goals,
    or personal characteristics.
    """
    try:
        db = Database.get_instance()
        vector_store = VectorStore.get_instance()
        llm = LLMService.get_instance()

        if not llm.is_embedding_configured():
            return json.dumps({
                "success": False,
                "error": "Embedding model not configured",
                "results": []
            })

        # Generate query embedding
        query_embedding = await llm.embed_single(query)

        # Build where clause
        where = {'type': 'semantic'}
        if category:
            where['memory_type'] = category

        # Search vector store
        results = vector_store.query(
            query_embedding=query_embedding,
            n_results=top_k,
            where=where
        )

        memories = []
        if results['ids'] and results['ids'][0]:
            for i, mem_id in enumerate(results['ids'][0]):
                memory = await db.get_semantic_memory(mem_id)
                if memory:
                    distance = results['distances'][0][i] if results.get('distances') else 0
                    memories.append({
                        "id": memory['id'],
                        "type": memory['type'],
                        "content": memory['content'],
                        "confidence": memory.get('confidence', 0.5),
                        "relevance_score": round(1 - distance, 3)
                    })

        return json.dumps({
            "success": True,
            "query": query,
            "category_filter": category,
            "results_count": len(memories),
            "results": memories
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        })


@tool("keyword_search", args_schema=KeywordSearchInput)
async def keyword_search(
    keywords: List[str],
    memory_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """Search memories using keyword matching.

    Args:
        keywords: List of keywords to search for (e.g. ["meeting", "project"])
        memory_type: Optional filter - "episodic" or "semantic". Omit to search both.
        limit: Maximum number of results (default: 10)

    Returns memories containing ANY of the specified keywords.
    """
    try:
        db = Database.get_instance()
        conn = db._connection

        results = {
            "episodic": [],
            "semantic": []
        }

        # Build OR conditions for multiple keywords
        if not keywords:
            return json.dumps({
                "success": False,
                "error": "No keywords provided",
                "results": {"episodic": [], "semantic": []}
            })

        # Search episodic memories
        if memory_type is None or memory_type == 'episodic':
            # Build WHERE clause with OR for multiple keywords
            conditions = " OR ".join(["content LIKE ?" for _ in keywords])
            patterns = [f"%{kw}%" for kw in keywords]

            cursor = await conn.execute(
                f"""SELECT * FROM episodic_memories
                    WHERE {conditions}
                    ORDER BY start_time DESC LIMIT ?""",
                (*patterns, limit)
            )
            rows = await cursor.fetchall()

            for row in rows:
                mem = dict(row)
                content = mem.get('content', '')
                results["episodic"].append({
                    "id": mem['id'],
                    "title": mem.get('title', ''),
                    "content": content[:300] + "..." if len(content) > 300 else content,
                    "start_time": datetime.fromtimestamp(mem['start_time']/1000).isoformat() if mem.get('start_time') else None
                })

        # Search semantic memories
        if memory_type is None or memory_type == 'semantic':
            conditions = " OR ".join(["content LIKE ?" for _ in keywords])
            patterns = [f"%{kw}%" for kw in keywords]

            cursor = await conn.execute(
                f"""SELECT * FROM semantic_memories
                    WHERE {conditions}
                    ORDER BY created_at DESC LIMIT ?""",
                (*patterns, limit)
            )
            rows = await cursor.fetchall()

            for row in rows:
                mem = dict(row)
                results["semantic"].append({
                    "id": mem['id'],
                    "type": mem['type'],
                    "content": mem['content'],
                    "confidence": mem.get('confidence', 0.5)
                })

        total_count = len(results["episodic"]) + len(results["semantic"])

        return json.dumps({
            "success": True,
            "keywords": keywords,
            "memory_type_filter": memory_type,
            "total_results": total_count,
            "results": results
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": {"episodic": [], "semantic": []}
        })


@tool("time_filter", args_schema=TimeFilterInput)
async def time_filter(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days_ago: Optional[int] = None,
    limit: int = 10
) -> str:
    """Filter episodic memories by time range.

    Use this when you need to find memories from a specific time period.
    You can specify:
    - A date range (start_date and/or end_date in YYYY-MM-DD format)
    - Or use days_ago for relative time (e.g., days_ago=7 for last week)

    Returns episodic memories that occurred within the specified time frame.
    """
    try:
        db = Database.get_instance()
        now = datetime.now()

        if days_ago is not None:
            start_ts = int((now - timedelta(days=days_ago)).timestamp() * 1000)
            end_ts = int(now.timestamp() * 1000)
            time_description = f"last {days_ago} days"
        else:
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                start_ts = int(start_dt.timestamp() * 1000)
            else:
                start_ts = 0

            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_ts = int((end_dt.timestamp() + 86400) * 1000)  # End of day
            else:
                end_ts = int(now.timestamp() * 1000)

            time_description = f"{start_date or 'beginning'} to {end_date or 'now'}"

        # Query episodic memories in time range
        conn = db._connection
        cursor = await conn.execute(
            """SELECT * FROM episodic_memories
               WHERE start_time >= ? AND start_time <= ?
               ORDER BY start_time DESC LIMIT ?""",
            (start_ts, end_ts, limit)
        )
        rows = await cursor.fetchall()

        memories = []
        for row in rows:
            mem = dict(row)
            content = mem.get('content', '')
            memories.append({
                "id": mem['id'],
                "title": mem['title'],
                "content": content[:300] + "..." if len(content) > 300 else content,
                "start_time": datetime.fromtimestamp(mem['start_time']/1000).isoformat(),
                "end_time": datetime.fromtimestamp(mem['end_time']/1000).isoformat()
            })

        return json.dumps({
            "success": True,
            "time_range": time_description,
            "results_count": len(memories),
            "results": memories
        }, ensure_ascii=False)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid date format. Use YYYY-MM-DD. Error: {str(e)}",
            "results": []
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        })


@tool("get_user_profile", args_schema=GetUserProfileInput)
async def get_user_profile(categories: Optional[List[str]] = None) -> str:
    """Get the user's profile by aggregating semantic memories.

    This provides a comprehensive view of what we know about the user across
    8 life categories: career, finance, health, family, social, growth, leisure, spirit.

    Use this when you need to understand the user's overall characteristics,
    preferences, or life situation.
    """
    try:
        db = Database.get_instance()

        all_categories = ['career', 'finance', 'health', 'family', 'social',
                         'growth', 'leisure', 'spirit', 'knowledge', 'preference']

        if categories:
            categories = [c for c in categories if c in all_categories]
            if not categories:
                categories = all_categories
        else:
            categories = all_categories

        profile = {}
        total_memories = 0

        for category in categories:
            memories = await db.get_semantic_memories(type=category, limit=20)
            if memories:
                profile[category] = [
                    {
                        "content": mem['content'],
                        "confidence": mem.get('confidence', 0.5)
                    }
                    for mem in memories
                ]
                total_memories += len(memories)

        return json.dumps({
            "success": True,
            "categories_included": categories,
            "total_memories": total_memories,
            "profile": profile
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "profile": {}
        })


@tool("get_recent_activity", args_schema=GetRecentActivityInput)
async def get_recent_activity(limit: int = 5) -> str:
    """Get the user's most recent activities from episodic memories.

    Use this when you need to know what the user has been doing recently.
    Returns the most recent episodic memories in chronological order.
    """
    try:
        db = Database.get_instance()
        memories = await db.get_episodic_memories(limit=limit)

        activities = []
        for mem in memories:
            activities.append({
                "id": mem['id'],
                "title": mem['title'],
                "content": mem['content'],
                "start_time": datetime.fromtimestamp(mem['start_time']/1000).isoformat(),
                "end_time": datetime.fromtimestamp(mem['end_time']/1000).isoformat()
            })

        return json.dumps({
            "success": True,
            "results_count": len(activities),
            "activities": activities
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "activities": []
        })


@tool("search_chat_history", args_schema=SearchChatHistoryInput)
async def search_chat_history(
    query: str,
    role: Optional[str] = None,
    limit: int = 20
) -> str:
    """Search through the original chat conversation history.

    Args:
        query: Keyword or phrase to search for in chat messages
        role: Optional filter - "user" or "assistant". Omit to search both.
        limit: Maximum number of results (default: 20)

    Use this to find specific conversations or messages from chat history.
    """
    try:
        db = Database.get_instance()
        conn = db._connection

        # Build query
        pattern = f"%{query}%"
        if role:
            cursor = await conn.execute(
                """SELECT id, role, content, timestamp, conversation_id
                   FROM messages
                   WHERE content LIKE ? AND role = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (pattern, role, limit)
            )
        else:
            cursor = await conn.execute(
                """SELECT id, role, content, timestamp, conversation_id
                   FROM messages
                   WHERE content LIKE ? AND role IN ('user', 'assistant')
                   ORDER BY timestamp DESC LIMIT ?""",
                (pattern, limit)
            )

        rows = await cursor.fetchall()

        messages = []
        for row in rows:
            msg = dict(row)
            content = msg.get('content', '')
            messages.append({
                "id": msg['id'],
                "role": msg['role'],
                "content": content[:500] + "..." if len(content) > 500 else content,
                "timestamp": datetime.fromtimestamp(msg['timestamp']/1000).isoformat() if msg.get('timestamp') else None,
                "conversation_id": msg.get('conversation_id')
            })

        return json.dumps({
            "success": True,
            "query": query,
            "role_filter": role,
            "results_count": len(messages),
            "messages": messages
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "messages": []
        })


# ==================== Reasoning Tool ====================

@tool("think", args_schema=ThinkInput)
def think(thought: str) -> str:
    """Use this tool to think about something.

    This tool allows you to pause and reason through complex problems,
    analyze information from previous tool calls, or plan your next steps.
    It does not retrieve any new information - it simply provides a space
    for structured thinking.

    Use this tool when you need to:
    - Process and synthesize results from multiple tool calls
    - Reason through complex or ambiguous situations
    - Plan a multi-step approach before taking action
    - Verify your understanding before providing a final answer

    The thought will be logged but does not affect the external state.
    """
    # The think tool doesn't do anything - it just returns success
    # The value is in giving the model a space to reason
    return json.dumps({
        "success": True,
        "message": "Thought recorded. Continue with your reasoning or take action."
    })


# ==================== Tool Factory ====================

def get_memory_tools():
    """Get all memory search tools for the agent.

    Returns a list of tool functions decorated with @tool.
    These are compatible with LangChain 1.0's create_agent function.
    """
    return [
        search_episodic_memory,
        search_semantic_memory,
        keyword_search,
        time_filter,
        get_user_profile,
        get_recent_activity,
        search_chat_history,
        think,  # Reasoning tool for complex analysis
    ]


def get_tool_descriptions() -> dict:
    """Get descriptions of all available tools."""
    tools = get_memory_tools()
    return {
        tool.name: tool.description
        for tool in tools
    }


# Legacy class-based exports for backward compatibility
SearchEpisodicMemoryTool = search_episodic_memory
SearchSemanticMemoryTool = search_semantic_memory
KeywordSearchTool = keyword_search
TimeFilterTool = time_filter
GetUserProfileTool = get_user_profile
GetRecentActivityTool = get_recent_activity
