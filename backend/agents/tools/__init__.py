"""
Agent Tools - LangChain 1.0 compatible memory and profile tools

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

from .profile_tools import (
    # Profile tool functions
    list_profile_files,
    read_profile,
    write_profile,
    create_profile,
    search_profile,
    get_profile_summary,
    delete_profile,
    # Factory functions
    get_profile_tools,
    get_profile_tool_descriptions,
    # Legacy aliases
    ListProfileFilesTool,
    ReadProfileTool,
    WriteProfileTool,
    CreateProfileTool,
    SearchProfileTool,
    GetProfileSummaryTool,
    DeleteProfileTool,
)

from .proactive_tools import (
    # Proactive agent tools
    create_task,
    get_pending_tasks,
    get_recent_task_history,
    get_profile_status,
    # Factory function
    get_proactive_tools,
)


def get_all_tools(include_proactive: bool = False):
    """Get all available agent tools.

    Returns a list of tool functions compatible with LangChain 1.0's create_agent.
    Includes memory tools, profile tools, and optionally proactive tools.

    Args:
        include_proactive: If True, include proactive tools (create_task, etc.)
                          These are primarily used during self-reflection tasks.
    """
    tools = get_memory_tools() + get_profile_tools()
    if include_proactive:
        tools += get_proactive_tools()
    return tools


__all__ = [
    # Memory tool functions
    'search_episodic_memory',
    'search_semantic_memory',
    'keyword_search',
    'time_filter',
    'get_user_profile',
    'get_recent_activity',
    'search_chat_history',
    'think',
    # Profile tool functions
    'list_profile_files',
    'read_profile',
    'write_profile',
    'create_profile',
    'search_profile',
    'get_profile_summary',
    'delete_profile',
    # Proactive tool functions
    'create_task',
    'get_pending_tasks',
    'get_recent_task_history',
    'get_profile_status',
    # Factory functions
    'get_all_tools',
    'get_memory_tools',
    'get_tool_descriptions',
    'get_profile_tools',
    'get_profile_tool_descriptions',
    'get_proactive_tools',
    # Memory tool legacy aliases
    'SearchEpisodicMemoryTool',
    'SearchSemanticMemoryTool',
    'KeywordSearchTool',
    'TimeFilterTool',
    'GetUserProfileTool',
    'GetRecentActivityTool',
    # Profile tool legacy aliases
    'ListProfileFilesTool',
    'ReadProfileTool',
    'WriteProfileTool',
    'CreateProfileTool',
    'SearchProfileTool',
    'GetProfileSummaryTool',
    'DeleteProfileTool',
]
