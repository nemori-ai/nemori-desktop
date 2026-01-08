"""
Nemori Agent Module - Tool-using conversational agent for memory-augmented interactions

This module contains the actual AI agent that can use tools to interact with the memory system.
For memory processing workflows (episodic, semantic, profile generation), see the `memory` module.
"""

from .executor import AgentExecutor, run_agent
from .model_adapter import create_chat_model, NemoriChatModel
from .tools import get_all_tools, get_memory_tools, get_tool_descriptions
from .middleware.summarization import SummarizationMiddleware, SummarizationConfig

__all__ = [
    # Agent (tool-using)
    'AgentExecutor',
    'run_agent',
    # Model adapter
    'create_chat_model',
    'NemoriChatModel',
    # Tools
    'get_all_tools',
    'get_memory_tools',
    'get_tool_descriptions',
    # Middleware
    'SummarizationMiddleware',
    'SummarizationConfig',
]
