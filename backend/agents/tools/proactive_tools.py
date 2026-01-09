"""
Proactive Agent Tools

Tools that allow the agent to manage its own tasks and reflect on its work.
These tools are primarily used during self-reflection to plan future work.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from langchain_core.tools import tool


@tool
def create_task(
    task_type: str,
    title: str,
    description: str,
    priority: int = 5,
    scheduled_hours_from_now: Optional[float] = None,
    target_file: Optional[str] = None
) -> str:
    """
    Create a new task for yourself to execute later.

    Use this tool during self-reflection to plan your future work.
    You can schedule tasks to run immediately, or at a specific time in the future.

    Args:
        task_type: Type of task. Must be one of:
            - "update_profile": Update a specific profile file
            - "learn_from_history": Learn from recent memories and conversations
            - "discover_patterns": Analyze behavior patterns
            - "summarize_period": Create a summary of activities
            - "explore_topic": Deep dive into a specific topic
            - "fill_gap": Fill missing information in profile
            - "consolidate": Merge and organize knowledge
            - "health_check": Check system health
            - "cleanup": Clean up old data
        title: Short title for the task (will be shown in task list)
        description: Detailed description of what the task should accomplish
        priority: Priority level from 1 (low) to 10 (urgent). Default is 5.
            - 1-3: Low priority, can wait
            - 4-6: Normal priority
            - 7-8: High priority, should be done soon
            - 9-10: Urgent, do as soon as possible
        scheduled_hours_from_now: Optional hours from now to schedule the task.
            If not provided, task will be queued for immediate execution.
            Examples: 0.5 (30 minutes), 1 (1 hour), 24 (tomorrow)
        target_file: Optional profile file to target (for update_profile tasks)
            Example: "23-interests-hobbies.md" or "topics/python-learning.md"

    Returns:
        Success message with task ID, or error message

    Example usage:
        # Create an immediate task to update hobbies
        create_task(
            task_type="update_profile",
            title="Update user's hobbies",
            description="Add the new hobby of photography that was mentioned in recent conversation",
            priority=6,
            target_file="23-interests-hobbies.md"
        )

        # Schedule a task for later
        create_task(
            task_type="discover_patterns",
            title="Analyze work patterns",
            description="Look at the user's work schedule over the past week",
            priority=5,
            scheduled_hours_from_now=4
        )
    """
    from proactive.task_scheduler import TaskScheduler, TaskType, ProactiveTask

    # Validate task type
    valid_types = [
        "update_profile", "learn_from_history", "discover_patterns",
        "summarize_period", "explore_topic", "fill_gap",
        "consolidate", "health_check", "cleanup"
    ]

    if task_type not in valid_types:
        return f"Error: Invalid task type '{task_type}'. Must be one of: {', '.join(valid_types)}"

    # Validate priority
    if priority < 1 or priority > 10:
        return f"Error: Priority must be between 1 and 10, got {priority}"

    try:
        scheduler = TaskScheduler.get_instance()

        # Calculate scheduled time
        scheduled_time = None
        if scheduled_hours_from_now is not None and scheduled_hours_from_now > 0:
            scheduled_time = datetime.now() + timedelta(hours=scheduled_hours_from_now)

        # Create the task
        task = ProactiveTask(
            id=scheduler._generate_task_id(),
            type=TaskType(task_type),
            title=title,
            description=description,
            priority=priority,
            scheduled_time=scheduled_time,
            target_file=target_file
        )

        # Add to scheduler - use sync method to avoid async issues in tool context
        import asyncio

        async def add_task_async():
            return await scheduler.add_task(task)

        # Try to run in current loop or create new one
        try:
            loop = asyncio.get_running_loop()
            # We're in async context - need to use nest_asyncio or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, add_task_async())
                future.result(timeout=10)  # Wait up to 10 seconds
        except RuntimeError:
            # No running loop, we can use asyncio.run directly
            asyncio.run(add_task_async())

        time_info = f" scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}" if scheduled_time else " (immediate)"

        return f"Successfully created task: '{title}' (ID: {task.id}, priority: {priority}){time_info}"

    except Exception as e:
        import traceback
        return f"Error creating task: {str(e)}\n{traceback.format_exc()}"


@tool
def get_pending_tasks() -> str:
    """
    Get the list of currently pending tasks in the queue.

    Use this during self-reflection to see what tasks are already scheduled,
    so you don't create duplicate tasks.

    Returns:
        List of pending tasks with their types, priorities, and scheduled times
    """
    from proactive.task_scheduler import TaskScheduler, TaskStatus

    try:
        scheduler = TaskScheduler.get_instance()
        tasks = scheduler.list_tasks()

        pending = [t for t in tasks if t.get('status') in ['pending', 'scheduled']]

        if not pending:
            return "No pending tasks in the queue. You can create new tasks as needed."

        lines = ["Current pending tasks:"]
        for task in pending[:15]:  # Limit to 15 tasks
            time_info = ""
            if task.get('scheduled_time'):
                time_info = f" @ {task['scheduled_time']}"
            lines.append(
                f"- [{task['priority']}] {task['title']} ({task['type']}){time_info}"
            )

        if len(pending) > 15:
            lines.append(f"... and {len(pending) - 15} more tasks")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting tasks: {str(e)}"


@tool
def get_recent_task_history(limit: int = 10) -> str:
    """
    Get the history of recently completed tasks.

    Use this during self-reflection to understand what you've already done,
    and to avoid repeating work unnecessarily.

    Args:
        limit: Maximum number of tasks to return (default 10, max 20)

    Returns:
        List of recent tasks with their outcomes
    """
    from proactive.task_scheduler import TaskScheduler

    try:
        scheduler = TaskScheduler.get_instance()
        limit = min(limit, 20)
        history = scheduler.list_history(limit)

        if not history:
            return "No task history available yet."

        lines = ["Recent task history:"]
        for task in history:
            status = task.get('status', 'unknown')
            status_icon = "✓" if status == 'completed' else "✗" if status == 'failed' else "?"

            result_preview = ""
            if task.get('result'):
                result_preview = f" - {task['result'][:100]}..." if len(task.get('result', '')) > 100 else f" - {task['result']}"
            elif task.get('error'):
                result_preview = f" - Error: {task['error'][:50]}..."

            lines.append(
                f"{status_icon} {task['title']} ({task['type']}){result_preview}"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting task history: {str(e)}"


@tool
def get_profile_status() -> str:
    """
    Get an overview of the current profile status.

    Use this during self-reflection to understand which profile files
    exist, which ones need updating, and where there are gaps.

    Returns:
        Overview of profile files including last update times and completeness
    """
    from services.profile_manager import ProfileManager
    import asyncio

    try:
        manager = ProfileManager.get_instance()

        # Get summary
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We need to handle this differently in async context
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, manager.get_summary())
                summary = future.result()
        else:
            summary = loop.run_until_complete(manager.get_summary())

        lines = [
            f"Profile Status Overview:",
            f"- Total files: {summary.total_files}",
            f"- Last updated: {summary.last_updated.strftime('%Y-%m-%d %H:%M') if summary.last_updated else 'Never'}",
            "",
            "Files by category:"
        ]

        for category, count in summary.categories.items():
            lines.append(f"  - {category}: {count} files")

        if summary.recent_changes:
            lines.append("")
            lines.append("Recent changes:")
            for change in summary.recent_changes[:5]:
                lines.append(f"  - {change.get('filename', 'unknown')}: {change.get('description', 'updated')}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting profile status: {str(e)}"


# Export all tools
def get_proactive_tools():
    """Get all proactive agent tools"""
    return [
        create_task,
        get_pending_tasks,
        get_recent_task_history,
        get_profile_status
    ]
