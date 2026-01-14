"""
Episodic Memory Prompts

Prompts used by the episodic processor for:
- Generating narrative content from activity logs
- Deciding whether to merge with existing memories
- Creating merged content from multiple memories
"""


def get_episodic_content_prompt(
    events_text: str,
    summary: str = None,
    has_images: bool = False
) -> str:
    """
    Generate prompt for creating episodic content from activity logs.

    Args:
        events_text: Formatted event log text
        summary: Optional summary hint
        has_images: Whether screenshots are attached

    Returns:
        Formatted prompt string
    """
    return f"""You are an assistant that creates a personal journal entry from a user's digital activity.

Here is a log of the user's recent activity:
{events_text}

{f'Summary hint: {summary}' if summary else ''}

{'I have also attached screenshots from this session for visual context.' if has_images else ''}

Please write your response based on the following instructions:
- **Perspective**: Write the 'content' from a first-person or close third-person perspective, as if narrating the user's own experience.
- **Narration Style**: Create a narrative that captures the flow and purpose of the session. Do not include raw IDs or technical details.
- **Focus**: Describe what the user did, thought, or intended to do.
- **Visual Context**: If screenshots are provided, use them to enrich your understanding of the user's activities.

Please write:
- **title**: A concise line capturing what this episode is about (max 100 characters).
- **content**: A detailed narrative of what happened, at least 200 words long.

Return your response in JSON format:
{{
  "title": "...",
  "content": "..."
}}"""


# Template for episodic content prompt
EPISODIC_CONTENT_PROMPT = """You are an assistant that creates a personal journal entry from a user's digital activity.

Here is a log of the user's recent activity:
{events_text}

{summary_hint}

{image_context}

Please write your response based on the following instructions:
- **Perspective**: Write the 'content' from a first-person or close third-person perspective, as if narrating the user's own experience.
- **Narration Style**: Create a narrative that captures the flow and purpose of the session. Do not include raw IDs or technical details.
- **Focus**: Describe what the user did, thought, or intended to do.
- **Visual Context**: If screenshots are provided, use them to enrich your understanding of the user's activities.

Please write:
- **title**: A concise line capturing what this episode is about (max 100 characters).
- **content**: A detailed narrative of what happened, at least 200 words long.

Return your response in JSON format:
{{
  "title": "...",
  "content": "..."
}}"""


def get_merge_decision_prompt(
    start_time: str,
    end_time: str,
    new_title: str,
    new_content: str,
    candidates_summary: str
) -> str:
    """
    Generate prompt for deciding whether to merge with existing memories.

    Args:
        start_time: Start time of the new memory
        end_time: End time of the new memory
        new_title: Title of the new memory
        new_content: Content of the new memory
        candidates_summary: Formatted summary of similar existing memories

    Returns:
        Formatted prompt string
    """
    return f"""You are a memory management assistant. Your task is to decide whether a newly generated episodic memory should be merged with an existing similar memory or kept as a new one.

**Decision Criteria:**
1. **Temporal Proximity:** Are the events close in time? A small gap (e.g., under 15 minutes) suggests they might be part of the same activity.
2. **Contextual Cohesion:** Do the memories describe the same continuous event or task?

**Newly Generated Memory:**
- Time Range: {start_time} to {end_time}
- Title: {new_title}
- Content: {new_content}

**Top Similar Existing Memories:**
{candidates_summary}

**Your Task:**
Based on the criteria, decide whether to merge the new memory with ONE of the candidates or to create a new memory.

- If you decide to merge, set "decision" to "merge" and provide the "merge_target_id".
- If you decide not to merge, set "decision" to "new".

**JSON Response Format:**
{{
  "decision": "merge" | "new",
  "merge_target_id": "...",
  "reason": "..."
}}"""


# Template for merge decision prompt
MERGE_DECISION_PROMPT = """You are a memory management assistant. Your task is to decide whether a newly generated episodic memory should be merged with an existing similar memory or kept as a new one.

**Decision Criteria:**
1. **Temporal Proximity:** Are the events close in time? A small gap (e.g., under 15 minutes) suggests they might be part of the same activity.
2. **Contextual Cohesion:** Do the memories describe the same continuous event or task?

**Newly Generated Memory:**
- Time Range: {start_time} to {end_time}
- Title: {new_title}
- Content: {new_content}

**Top Similar Existing Memories:**
{candidates_summary}

**Your Task:**
Based on the criteria, decide whether to merge the new memory with ONE of the candidates or to create a new memory.

- If you decide to merge, set "decision" to "merge" and provide the "merge_target_id".
- If you decide not to merge, set "decision" to "new".

**JSON Response Format:**
{{
  "decision": "merge" | "new",
  "merge_target_id": "...",
  "reason": "..."
}}"""


def get_merged_content_prompt(
    old_title: str,
    old_content: str,
    new_title: str,
    new_content: str,
    event_details: str,
    has_images: bool = False
) -> str:
    """
    Generate prompt for creating merged content from two memories.

    Args:
        old_title: Title of the old memory
        old_content: Content of the old memory
        new_title: Title of the new memory
        new_content: Content of the new memory
        event_details: Combined event timeline
        has_images: Whether screenshots are attached

    Returns:
        Formatted prompt string
    """
    return f"""You are a memory consolidation assistant. You need to merge two related memories into one coherent narrative.

**Old Memory:**
Title: {old_title}
Content: {old_content}

**New Memory:**
Title: {new_title}
Content: {new_content}

**Combined Event Timeline:**
{event_details}

{'I have also attached screenshots from this session for visual context.' if has_images else ''}

Your task is to create a single, unified memory that combines both narratives into a coherent story. The new narrative should:
- Seamlessly connect the events from both memories
- Focus on creating a logical story from the user's perspective
- Use visual context from screenshots if provided to enrich the narrative
- Not mention screenshots or technical details directly

Please write:
- title: A new, concise title for the combined episode (max 100 characters).
- content: A detailed narrative that merges both memories into one story. At least 300 words.

Return your response in JSON format:
{{
  "title": "...",
  "content": "..."
}}"""


# Template for merged content prompt
MERGED_CONTENT_PROMPT = """You are a memory consolidation assistant. You need to merge two related memories into one coherent narrative.

**Old Memory:**
Title: {old_title}
Content: {old_content}

**New Memory:**
Title: {new_title}
Content: {new_content}

**Combined Event Timeline:**
{event_details}

{image_context}

Your task is to create a single, unified memory that combines both narratives into a coherent story. The new narrative should:
- Seamlessly connect the events from both memories
- Focus on creating a logical story from the user's perspective
- Use visual context from screenshots if provided to enrich the narrative
- Not mention screenshots or technical details directly

Please write:
- title: A new, concise title for the combined episode (max 100 characters).
- content: A detailed narrative that merges both memories into one story. At least 300 words.

Return your response in JSON format:
{{
  "title": "...",
  "content": "..."
}}"""
