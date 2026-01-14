"""
Proactive Task Prompts

Prompts used by the proactive task scheduler for:
- Profile updates
- Learning from history
- Summarizing periods
- Discovering patterns
- Knowledge consolidation
- Filling knowledge gaps
- Exploring topics
- Self-reflection
"""


def get_profile_update_prompt(
    target_file: str,
    task_title: str,
    task_description: str,
    current_content: str
) -> str:
    """
    Generate prompt for updating a profile file.

    Args:
        target_file: Name of the profile file to update
        task_title: Title of the task
        task_description: Description of what to update
        current_content: Current content of the file

    Returns:
        Formatted prompt string
    """
    return PROFILE_UPDATE_PROMPT.format(
        target_file=target_file,
        task_title=task_title,
        task_description=task_description,
        current_content=current_content
    )


PROFILE_UPDATE_PROMPT = """You are updating the user's profile file: {target_file}

Task: {task_title}
Description: {task_description}

Current file content:
{current_content}

Instructions:
1. Use search_episodic_memory and search_semantic_memory to find relevant recent information
2. Use read_profile to read related profile files if needed
3. Update the profile file with new information using write_profile
4. Preserve existing accurate information
5. Update confidence levels based on evidence
6. Add new evidence entries

Please complete this task."""


def get_learn_from_history_prompt(task_title: str, task_description: str) -> str:
    """
    Generate prompt for learning from user history.

    Args:
        task_title: Title of the task
        task_description: Description of what to learn

    Returns:
        Formatted prompt string
    """
    return LEARN_FROM_HISTORY_PROMPT.format(
        task_title=task_title,
        task_description=task_description
    )


LEARN_FROM_HISTORY_PROMPT = """Task: {task_title}
Description: {task_description}

Instructions:
1. Use get_recent_activity to retrieve recent user activities
2. Use search_episodic_memory to find relevant historical context
3. Identify new information about the user
4. Use list_profile_files to see available profile files
5. Update relevant profile files with new insights using write_profile
6. If you discover a significant new topic, create a new file in topics/

Focus on:
- New skills or interests the user has shown
- Changes in goals or priorities
- New relationships or projects mentioned
- Any patterns in user behavior

Please complete this task and report what you learned."""


def get_summarize_period_prompt(
    task_title: str,
    task_description: str,
    period: str
) -> str:
    """
    Generate prompt for summarizing a time period.

    Args:
        task_title: Title of the task
        task_description: Description of the summary task
        period: Time period to summarize (e.g., "today", "this week")

    Returns:
        Formatted prompt string
    """
    return SUMMARIZE_PERIOD_PROMPT.format(
        task_title=task_title,
        task_description=task_description,
        period=period
    )


SUMMARIZE_PERIOD_PROMPT = """Task: {task_title}
Description: {task_description}

Instructions:
1. Use time_filter to get activities from {period}
2. Summarize the key activities and events
3. Identify any notable patterns or insights
4. Update relevant profile files:
   - 30-daily-patterns.md for routine patterns
   - 51-patterns-insights.md for behavioral insights
   - Other relevant files based on content

Please complete this summary task."""


def get_discover_patterns_prompt(task_title: str, task_description: str) -> str:
    """
    Generate prompt for discovering behavioral patterns.

    Args:
        task_title: Title of the task
        task_description: Description of the pattern discovery task

    Returns:
        Formatted prompt string
    """
    return DISCOVER_PATTERNS_PROMPT.format(
        task_title=task_title,
        task_description=task_description
    )


DISCOVER_PATTERNS_PROMPT = """Task: {task_title}
Description: {task_description}

Instructions:
1. Use time_filter with days_ago=7 to get this week's activities
2. Analyze for recurring patterns:
   - Time patterns (when user is most active)
   - Topic patterns (what user focuses on)
   - Behavioral patterns (how user approaches tasks)
3. Update 51-patterns-insights.md with discovered patterns
4. Update 30-daily-patterns.md if you find routine patterns

Please complete this pattern discovery task."""


def get_consolidate_knowledge_prompt(
    task_title: str,
    task_description: str
) -> str:
    """
    Generate prompt for consolidating knowledge.

    Args:
        task_title: Title of the task
        task_description: Description of the consolidation task

    Returns:
        Formatted prompt string
    """
    return CONSOLIDATE_KNOWLEDGE_PROMPT.format(
        task_title=task_title,
        task_description=task_description
    )


CONSOLIDATE_KNOWLEDGE_PROMPT = """Task: {task_title}
Description: {task_description}

Instructions:
1. Use list_profile_files to see all profile files
2. Use get_profile_summary to understand current state
3. Look for:
   - Duplicate information across files
   - Outdated information that should be updated
   - Related information that should be linked
4. Update files to:
   - Remove duplicates
   - Add cross-references using related_files in YAML front matter
   - Improve organization

Please complete this consolidation task."""


def get_fill_gap_prompt(
    task_title: str,
    task_description: str,
    target_file: str = None
) -> str:
    """
    Generate prompt for filling knowledge gaps.

    Args:
        task_title: Title of the task
        task_description: Description of the gap to fill
        target_file: Optional specific file to update

    Returns:
        Formatted prompt string
    """
    target_file_instruction = f"Target file to update: {target_file}" if target_file else "Determine the appropriate file(s) to update based on the information found."
    return FILL_GAP_PROMPT.format(
        task_title=task_title,
        task_description=task_description,
        target_file_instruction=target_file_instruction
    )


FILL_GAP_PROMPT = """Task: {task_title}
Description: {task_description}

You are tasked with filling a knowledge gap in the user's profile.

## Instructions

1. **Search for Information**
   - Use `search_episodic_memory` to find relevant historical conversations and activities
   - Use `search_semantic_memory` to find related stored knowledge
   - Use `get_recent_activity` to check recent user activities for clues

2. **Analyze What's Missing**
   - Use `list_profile_files` and `read_profile` to understand current profile state
   - Identify specific gaps mentioned in the task description

3. **Fill the Gaps**
   - If you find relevant information, use `write_profile` to update the appropriate file
   - Be conservative - only add information you're confident about
   - Update confidence levels appropriately (lower for inferred, higher for explicit)
   - Add evidence entries with dates and sources

4. **Report Results**
   - Summarize what information you found
   - List what was updated
   - Note any gaps that couldn't be filled (need more data)

{target_file_instruction}

Please complete this task."""


def get_explore_topic_prompt(
    task_title: str,
    task_description: str,
    topic: str
) -> str:
    """
    Generate prompt for exploring a topic.

    Args:
        task_title: Title of the task
        task_description: Description of the exploration task
        topic: The topic to explore

    Returns:
        Formatted prompt string
    """
    return EXPLORE_TOPIC_PROMPT.format(
        task_title=task_title,
        task_description=task_description,
        topic=topic
    )


EXPLORE_TOPIC_PROMPT = """Task: {task_title}
Description: {task_description}

You are tasked with deeply exploring a specific topic related to the user.

## Topic to Explore
{topic}

## Instructions

1. **Gather Information**
   - Use `search_episodic_memory` with various related keywords to find all mentions of this topic
   - Use `search_semantic_memory` to find stored knowledge about this topic
   - Use `get_recent_activity` to see if there's recent activity related to this topic

2. **Analyze Comprehensively**
   - When did the user first show interest in this topic?
   - How has their engagement with this topic evolved?
   - What specific aspects are they most interested in?
   - Are there related topics that connect to this one?
   - What's their skill/knowledge level in this area?

3. **Update Profile**
   - Check if there's an existing topic file in `topics/` folder
   - If yes, use `read_profile` to read it and then `write_profile` to update it
   - If no, consider creating a new topic file if there's enough information
   - Also update related files like `23-interests.md`, `21-knowledge.md` if appropriate

4. **Report Findings**
   - Summarize key insights about the user's relationship with this topic
   - Note any interesting patterns or connections discovered
   - List files that were updated

Please complete this exploration task."""


def get_self_reflection_prompt(current_time: str, time_context: str, focus_suggestion: str) -> str:
    """
    Generate prompt for self-reflection task.

    Args:
        current_time: Current time string
        time_context: Context based on time of day (morning, afternoon, etc.)
        focus_suggestion: Suggested focus area based on time

    Returns:
        Formatted prompt string
    """
    return SELF_REFLECTION_PROMPT.format(
        current_time=current_time,
        time_context=time_context,
        focus_suggestion=focus_suggestion
    )


SELF_REFLECTION_PROMPT = """# Self-Reflection Time

Current time: {current_time} ({time_context})

You are now in self-reflection mode. This is your time to think deeply, analyze comprehensively, and plan strategically.
Focus on: {focus_suggestion}

## Your Tools

You have special tools for this task:
- `get_profile_status`: See the current state of user profile files
- `get_pending_tasks`: See what tasks are already scheduled
- `get_recent_task_history`: See what you've already done recently
- `create_task`: Schedule new tasks for yourself (you can schedule MULTIPLE tasks at DIFFERENT times!)

Plus your usual tools:
- `search_episodic_memory`, `search_semantic_memory`: Search user memories
- `get_recent_activity`: Get recent user activities
- `list_profile_files`, `read_profile`: Access profile files

## Your Mission

1. **Understand Current State**
   - Use `get_profile_status` to see which profile files exist and when they were last updated
   - Use `get_pending_tasks` to see what's already scheduled
   - Use `get_recent_task_history` to avoid repeating recent work

2. **Analyze Deeply**
   - Use `get_recent_activity` to see what the user has been doing
   - Use `search_episodic_memory` to look for interesting patterns or new information
   - Use `search_semantic_memory` to find related knowledge
   - Identify what profile files might need updating
   - Look for gaps in your understanding of the user

3. **Plan Your Work - BE PROACTIVE!**

   You should create MULTIPLE tasks scheduled at DIFFERENT future times. Think about:

   **Immediate tasks (next 1-2 hours):**
   - "learn_from_history" for recent activity you haven't processed
   - "update_profile" for files that clearly need updating now

   **Later today tasks (3-6 hours from now):**
   - "discover_patterns" to analyze behavioral patterns
   - "summarize_period" to create summaries

   **Tomorrow/Future tasks:**
   - "explore_topic" for topics worth investigating deeper
   - "consolidate_knowledge" to merge related information
   - "fill_gap" for information you're curious about

   Use `scheduled_time` to spread tasks throughout the day! For example:
   - Schedule one task for 30 minutes from now
   - Schedule another for 2 hours from now
   - Schedule another for tomorrow morning

4. **Be Ambitious and Thorough**
   - Create 5-10 tasks if you identify that many areas to work on
   - Different task types help build a complete picture of the user
   - Schedule tasks at various times to stay continuously engaged
   - The more you work, the better you understand the user!
   - Use priority to determine order: 10 = urgent, 5 = normal, 1 = low
   - Don't be afraid to schedule tasks for days ahead

## Task Types Available
- `update_profile`: Update a specific profile file with new information
- `learn_from_history`: Learn from recent user activities
- `discover_patterns`: Find patterns in user behavior
- `summarize_period`: Summarize a time period
- `explore_topic`: Explore a topic mentioned by the user
- `consolidate_knowledge`: Merge and organize related knowledge
- `fill_gap`: Research a specific area to fill knowledge gaps
- `health_check`: Run a quick system health check
- `self_reflection`: Schedule another reflection session!

## Example Strategy

"Let me check my state... Profile has 19 files, some updated recently, others stale.
Recent activity shows the user worked on Python and discussed AI concepts.
The skills file is 3 days old - needs updating.
I notice the user mentioned a new project but I don't have details.

I'll create:
1. (now) learn_from_history - process today's Python coding session
2. (in 1 hour) update_profile for skills file - add Python frameworks
3. (in 3 hours) explore_topic - research the new project they mentioned
4. (tomorrow morning) discover_patterns - analyze this week's work patterns
5. (tomorrow evening) self_reflection - check progress and plan more"

Now, please reflect and plan. Be thorough - check your current state, analyze all available information, and create a comprehensive set of tasks to keep yourself productively engaged!"""
