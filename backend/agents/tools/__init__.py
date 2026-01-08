"""
Agent Tools - LangChain 1.0 compatible memory search tools

Uses the modern @tool decorator pattern for defining tools.
"""

from .memory_tools import (
    # Tool functions (LangChain 1.0 style)
    search_episodic_memory,
    search_semantic_memory,
    keyword_search,
    time_filter,
    get_user_profile,
    get_recent_activity,
    search_chat_history,
    think,  # Reasoning tool
    # Factory functions
    get_memory_tools,
    get_tool_descriptions,
    # Legacy aliases for backward compatibility
    SearchEpisodicMemoryTool,
    SearchSemanticMemoryTool,
    KeywordSearchTool,
    TimeFilterTool,
    GetUserProfileTool,
    GetRecentActivityTool,
)


def get_all_tools():
    """Get all available agent tools.

    Returns a list of tool functions compatible with LangChain 1.0's create_agent.
    """
    return get_memory_tools()


__all__ = [
    # Modern tool functions
    'search_episodic_memory',
    'search_semantic_memory',
    'keyword_search',
    'time_filter',
    'get_user_profile',
    'get_recent_activity',
    'search_chat_history',
    'think',
    # Factory functions
    'get_all_tools',
    'get_memory_tools',
    'get_tool_descriptions',
    # Legacy aliases
    'SearchEpisodicMemoryTool',
    'SearchSemanticMemoryTool',
    'KeywordSearchTool',
    'TimeFilterTool',
    'GetUserProfileTool',
    'GetRecentActivityTool',
]
