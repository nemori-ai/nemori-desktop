"""
Prompts package - Centralized prompt management with language injection support

This package contains all LLM prompts used in the Nemori application.
All prompts support dynamic language injection to ensure responses are
generated in the user's preferred language.
"""

from .language import inject_language, get_language_instruction
from .semantic_prompts import (
    CONSOLIDATION_DECISION_PROMPT,
    RECONSTRUCTION_PROMPT,
    CALIBRATION_PROMPT,
    SEMANTIC_CATEGORIES,
)
from .episodic_prompts import (
    EPISODIC_CONTENT_PROMPT,
    MERGE_DECISION_PROMPT,
    MERGED_CONTENT_PROMPT,
)
from .agent_prompts import AGENT_SYSTEM_PROMPT
from .proactive_prompts import (
    PROFILE_UPDATE_PROMPT,
    LEARN_FROM_HISTORY_PROMPT,
    SUMMARIZE_PERIOD_PROMPT,
    DISCOVER_PATTERNS_PROMPT,
    CONSOLIDATE_KNOWLEDGE_PROMPT,
    FILL_GAP_PROMPT,
    EXPLORE_TOPIC_PROMPT,
    SELF_REFLECTION_PROMPT,
)
from .summarization_prompts import SUMMARIZATION_PROMPT

__all__ = [
    # Language utilities
    'inject_language',
    'get_language_instruction',
    # Semantic prompts
    'CONSOLIDATION_DECISION_PROMPT',
    'RECONSTRUCTION_PROMPT',
    'CALIBRATION_PROMPT',
    'SEMANTIC_CATEGORIES',
    # Episodic prompts
    'EPISODIC_CONTENT_PROMPT',
    'MERGE_DECISION_PROMPT',
    'MERGED_CONTENT_PROMPT',
    # Agent prompts
    'AGENT_SYSTEM_PROMPT',
    # Proactive prompts
    'PROFILE_UPDATE_PROMPT',
    'LEARN_FROM_HISTORY_PROMPT',
    'SUMMARIZE_PERIOD_PROMPT',
    'DISCOVER_PATTERNS_PROMPT',
    'CONSOLIDATE_KNOWLEDGE_PROMPT',
    'FILL_GAP_PROMPT',
    'EXPLORE_TOPIC_PROMPT',
    'SELF_REFLECTION_PROMPT',
    # Summarization prompts
    'SUMMARIZATION_PROMPT',
]
