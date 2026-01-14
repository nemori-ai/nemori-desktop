"""
Semantic Memory Prompts

Prompts used by the semantic extractor for:
- Consolidation decisions (merge, new, conflict)
- Scene reconstruction from summaries
- Calibration and insight extraction
"""

# 8 life categories for semantic memories
SEMANTIC_CATEGORIES = {
    'career': 'Career goals, work projects, professional skills, job experiences',
    'finance': 'Financial goals, investments, spending habits, income sources',
    'health': 'Physical health, exercise, diet, medical conditions, sleep',
    'family': 'Family members, romantic relationships, home life',
    'social': 'Friendships, social activities, networking, community',
    'growth': 'Learning, education, self-improvement, skills development',
    'leisure': 'Hobbies, entertainment, travel, relaxation activities',
    'spirit': 'Mental health, meditation, values, life philosophy, emotions',
}


def get_consolidation_decision_prompt(
    new_item_type: str,
    new_item_content: str,
    candidates_summary: str
) -> str:
    """
    Generate prompt for deciding how to consolidate a new semantic item.

    Args:
        new_item_type: Type/category of the new item
        new_item_content: Content of the new item
        candidates_summary: Formatted summary of similar existing items

    Returns:
        Formatted prompt string
    """
    return f"""You are a Knowledge Base Administrator responsible for maintaining a clean and accurate set of semantic memories about a user.

A new semantic item has been extracted. You must decide how to integrate it into the knowledge base.

**New Item:**
- Type: {new_item_type}
- Content: "{new_item_content}"

**Existing Similar Items:**
{candidates_summary}

**Your Task:**
Choose ONE of the following actions:

1. **NEW**: If the new item is a completely new concept that doesn't overlap with existing items.
2. **MERGE**: If the new item and an existing item are semantically identical but phrased differently.
3. **CONFLICT_DELETE**: If the new item directly contradicts or makes an existing item obsolete.

**Response Format (JSON):**
- For NEW: {{"decision": "NEW", "reason": "..."}}
- For MERGE: {{"decision": "MERGE", "target_ids": ["id"], "new_content": "canonical version", "reason": "..."}}
- For CONFLICT_DELETE: {{"decision": "CONFLICT_DELETE", "target_ids": ["id"], "reason": "..."}}

Provide only the JSON response."""


# Template for consolidation decision prompt
CONSOLIDATION_DECISION_PROMPT = """You are a Knowledge Base Administrator responsible for maintaining a clean and accurate set of semantic memories about a user.

A new semantic item has been extracted. You must decide how to integrate it into the knowledge base.

**New Item:**
- Type: {new_item_type}
- Content: "{new_item_content}"

**Existing Similar Items:**
{candidates_summary}

**Your Task:**
Choose ONE of the following actions:

1. **NEW**: If the new item is a completely new concept that doesn't overlap with existing items.
2. **MERGE**: If the new item and an existing item are semantically identical but phrased differently.
3. **CONFLICT_DELETE**: If the new item directly contradicts or makes an existing item obsolete.

**Response Format (JSON):**
- For NEW: {{"decision": "NEW", "reason": "..."}}
- For MERGE: {{"decision": "MERGE", "target_ids": ["id"], "new_content": "canonical version", "reason": "..."}}
- For CONFLICT_DELETE: {{"decision": "CONFLICT_DELETE", "target_ids": ["id"], "reason": "..."}}

Provide only the JSON response."""


def get_reconstruction_prompt(summary: str, similar_context: str) -> str:
    """
    Generate prompt for reconstructing detailed scene from summary.

    Args:
        summary: The session summary
        similar_context: Context from similar semantic memories

    Returns:
        Formatted prompt string
    """
    return f"""You are a semantic memory agent. Given a short session summary and similar past semantic memories, reconstruct what likely happened in detail.

Summary:
{summary}

Similar semantic memories:
{similar_context}

Based on the summary, reconstruct what the user was doing in detail. Focus on:
- What specific content was being viewed/accessed
- What actions the user took
- What the user's goals or interests might have been

Return JSON: {{"reconstructed_details": "detailed description (max 300 words)"}}"""


# Template for reconstruction prompt
RECONSTRUCTION_PROMPT = """You are a semantic memory agent. Given a short session summary and similar past semantic memories, reconstruct what likely happened in detail.

Summary:
{summary}

Similar semantic memories:
{similar_context}

Based on the summary, reconstruct what the user was doing in detail. Focus on:
- What specific content was being viewed/accessed
- What actions the user took
- What the user's goals or interests might have been

Return JSON: {{"reconstructed_details": "detailed description (max 300 words)"}}"""


def get_calibration_prompt(
    categories_desc: str,
    reconstructed: str,
    compact_events: str
) -> str:
    """
    Generate prompt for extracting life insights from a session.

    Args:
        categories_desc: Formatted description of the 8 life categories
        reconstructed: Reconstructed session details
        compact_events: Compact summary of original events

    Returns:
        Formatted prompt string
    """
    return f"""You are a life insights extraction agent. Analyze the session and extract meaningful, lasting insights about the user into 8 life categories.

**8 Life Categories:**
{categories_desc}

**Session Context:**
{reconstructed}

**Original Events:**
{compact_events}

**Guidelines:**
1. Each insight must be self-contained and meaningful on its own
2. Focus on lasting facts, preferences, goals, or habits - avoid transient details
3. Write from the user's perspective (e.g., "User prefers...", "User is working on...")
4. Only extract if there's clear evidence in the session
5. It's OK to leave categories empty if no relevant insights are found

**Good Examples:**
- career: "User is developing a personal AI assistant app called Nemori"
- health: "User exercises in the morning before work"
- growth: "User is learning about memory systems and embeddings"
- leisure: "User enjoys watching tech YouTube videos"

**Bad Examples (DO NOT extract):**
- "User clicked a button" (too specific, not lasting)
- "The document has 10 pages" (not about the user)
- "User is typing" (transient action)

Return JSON with arrays for each category (empty arrays are fine):
{{"career": [...], "finance": [...], "health": [...], "family": [...], "social": [...], "growth": [...], "leisure": [...], "spirit": [...]}}

Maximum 2 items per category, 8 items total."""


# Template for calibration prompt
CALIBRATION_PROMPT = """You are a life insights extraction agent. Analyze the session and extract meaningful, lasting insights about the user into 8 life categories.

**8 Life Categories:**
{categories_desc}

**Session Context:**
{reconstructed}

**Original Events:**
{compact_events}

**Guidelines:**
1. Each insight must be self-contained and meaningful on its own
2. Focus on lasting facts, preferences, goals, or habits - avoid transient details
3. Write from the user's perspective (e.g., "User prefers...", "User is working on...")
4. Only extract if there's clear evidence in the session
5. It's OK to leave categories empty if no relevant insights are found

**Good Examples:**
- career: "User is developing a personal AI assistant app called Nemori"
- health: "User exercises in the morning before work"
- growth: "User is learning about memory systems and embeddings"
- leisure: "User enjoys watching tech YouTube videos"

**Bad Examples (DO NOT extract):**
- "User clicked a button" (too specific, not lasting)
- "The document has 10 pages" (not about the user)
- "User is typing" (transient action)

Return JSON with arrays for each category (empty arrays are fine):
{{"career": [...], "finance": [...], "health": [...], "family": [...], "social": [...], "growth": [...], "leisure": [...], "spirit": [...]}}

Maximum 2 items per category, 8 items total."""
