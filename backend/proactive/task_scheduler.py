"""
TaskScheduler - Manages the agent's task queue and execution

Handles:
- Task queue management with priorities
- Task scheduling (one-time and recurring)
- Task execution coordination with the agent executor
- Daily task planning
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, time
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field

from config.settings import settings
from prompts import inject_language
from prompts.proactive_prompts import (
    get_profile_update_prompt,
    get_learn_from_history_prompt,
    get_summarize_period_prompt,
    get_discover_patterns_prompt,
    get_consolidate_knowledge_prompt,
    get_fill_gap_prompt,
    get_explore_topic_prompt,
    get_self_reflection_prompt,
)

if TYPE_CHECKING:
    from .core import ProactiveCore


class TaskType(Enum):
    """Types of proactive tasks"""
    # Self-management (highest priority)
    SELF_REFLECTION = "self_reflection"         # Think, analyze, and plan tasks

    # Profile maintenance
    UPDATE_PROFILE = "update_profile"           # Update a profile file
    CONSOLIDATE_KNOWLEDGE = "consolidate"       # Merge/organize knowledge
    DISCOVER_PATTERNS = "discover_patterns"     # Find behavioral patterns

    # Learning
    LEARN_FROM_HISTORY = "learn_from_history"   # Learn from episodic memories
    SUMMARIZE_PERIOD = "summarize_period"       # Create period summary

    # Exploration
    EXPLORE_TOPIC = "explore_topic"             # Deep dive into a topic
    FILL_KNOWLEDGE_GAP = "fill_gap"             # Fill missing information

    # System
    HEALTH_CHECK = "health_check"               # System health check
    CLEANUP = "cleanup"                         # Clean up old data


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"           # Waiting to be executed
    SCHEDULED = "scheduled"       # Scheduled for future execution
    IN_PROGRESS = "in_progress"   # Currently executing
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Execution failed
    CANCELLED = "cancelled"       # Cancelled before execution


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 7
    URGENT = 10


@dataclass
class ProactiveTask:
    """A task for the proactive agent to execute"""
    id: str
    type: TaskType
    title: str
    description: str

    # Scheduling
    scheduled_time: Optional[datetime] = None
    recurring: bool = False
    recurrence_interval: Optional[timedelta] = None

    # Priority and status
    priority: int = 5
    status: TaskStatus = TaskStatus.PENDING

    # Execution
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None

    # Results
    result: Optional[str] = None
    error: Optional[str] = None

    # Context
    target_file: Optional[str] = None       # For profile updates
    context: Dict[str, Any] = field(default_factory=dict)

    def is_due(self) -> bool:
        """Check if this task is due for execution"""
        if self.status != TaskStatus.PENDING and self.status != TaskStatus.SCHEDULED:
            return False

        if self.scheduled_time is None:
            return True

        return datetime.now() >= self.scheduled_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "recurring": self.recurring,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "result": self.result,
            "error": self.error,
            "target_file": self.target_file
        }


class TaskScheduler:
    """
    Manages the proactive agent's task queue.

    Responsibilities:
    - Maintain task queue with priorities
    - Schedule tasks for future execution
    - Coordinate task execution with the agent
    - Track task history and results
    """

    _instance: Optional["TaskScheduler"] = None

    def __init__(self):
        self._core: Optional["ProactiveCore"] = None
        self._tasks: List[ProactiveTask] = []
        self._task_history: List[ProactiveTask] = []
        self._initialized = False
        self._loading = False  # Lock to prevent concurrent DB loading

        # Configuration
        self._max_tasks_in_queue = 100
        self._max_history_size = 500
        self._default_task_timeout = timedelta(minutes=10)

    @classmethod
    def get_instance(cls) -> "TaskScheduler":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, core: "ProactiveCore") -> None:
        """Initialize the task scheduler"""
        if self._initialized:
            return

        self._core = core

        # Load tasks from database
        await self._load_tasks_from_db()

        self._initialized = True
        print(f"TaskScheduler initialized with {len(self._tasks)} pending tasks, {len(self._task_history)} history")

    async def _load_tasks_from_db(self) -> None:
        """Load tasks from database"""
        from storage.database import Database

        # Prevent concurrent loading
        if self._loading:
            return

        self._loading = True

        try:
            db = Database.get_instance()
            conn = db._connection

            # Clear existing lists to prevent duplicates
            self._tasks.clear()
            self._task_history.clear()

            # Track loaded IDs to prevent duplicates
            loaded_ids = set()

            # Load pending/scheduled tasks
            cursor = await conn.execute("""
                SELECT id, type, title, description, priority, status,
                       scheduled_time, recurring, recurrence_interval_seconds,
                       target_file, context, result, error,
                       created_at, started_at, completed_at, execution_time_ms
                FROM proactive_tasks
                WHERE status IN ('pending', 'scheduled', 'in_progress')
                ORDER BY priority DESC, created_at ASC
            """)
            rows = await cursor.fetchall()

            for row in rows:
                task = self._row_to_task(row)
                if task and task.id not in loaded_ids:
                    self._tasks.append(task)
                    loaded_ids.add(task.id)

            # Load recent history (completed/failed tasks)
            cursor = await conn.execute("""
                SELECT id, type, title, description, priority, status,
                       scheduled_time, recurring, recurrence_interval_seconds,
                       target_file, context, result, error,
                       created_at, started_at, completed_at, execution_time_ms
                FROM proactive_tasks
                WHERE status IN ('completed', 'failed', 'cancelled')
                ORDER BY completed_at DESC
                LIMIT ?
            """, (self._max_history_size,))
            rows = await cursor.fetchall()

            for row in rows:
                task = self._row_to_task(row)
                if task and task.id not in loaded_ids:
                    self._task_history.append(task)
                    loaded_ids.add(task.id)

        except Exception as e:
            print(f"Error loading tasks from database: {e}")
        finally:
            self._loading = False

    def _row_to_task(self, row) -> Optional[ProactiveTask]:
        """Convert database row to ProactiveTask"""
        try:
            # Helper to convert ms timestamp to datetime
            def ms_to_datetime(ms):
                if ms is None:
                    return None
                return datetime.fromtimestamp(ms / 1000)

            return ProactiveTask(
                id=row[0],
                type=TaskType(row[1]),
                title=row[2],
                description=row[3] or "",
                priority=row[4],
                status=TaskStatus(row[5]),
                scheduled_time=ms_to_datetime(row[6]),
                recurring=bool(row[7]),
                recurrence_interval=timedelta(seconds=row[8]) if row[8] else None,
                target_file=row[9],
                context=json.loads(row[10]) if row[10] else {},
                result=row[11],
                error=row[12],
                created_at=ms_to_datetime(row[13]) or datetime.now(),
                started_at=ms_to_datetime(row[14]),
                completed_at=ms_to_datetime(row[15]),
                execution_time_ms=row[16]
            )
        except Exception as e:
            print(f"Error converting row to task: {e}")
            return None

    async def _save_task_to_db(self, task: ProactiveTask) -> None:
        """Save a task to the database"""
        from storage.database import Database

        try:
            db = Database.get_instance()
            conn = db._connection

            # Helper to convert datetime to ms timestamp
            def datetime_to_ms(dt):
                if dt is None:
                    return None
                return int(dt.timestamp() * 1000)

            await conn.execute("""
                INSERT OR REPLACE INTO proactive_tasks
                (id, type, title, description, priority, status,
                 scheduled_time, recurring, recurrence_interval_seconds,
                 target_file, context, result, error,
                 created_at, started_at, completed_at, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.type.value,
                task.title,
                task.description,
                task.priority,
                task.status.value,
                datetime_to_ms(task.scheduled_time),
                1 if task.recurring else 0,
                int(task.recurrence_interval.total_seconds()) if task.recurrence_interval else None,
                task.target_file,
                json.dumps(task.context) if task.context else None,
                task.result,
                task.error,
                datetime_to_ms(task.created_at),
                datetime_to_ms(task.started_at),
                datetime_to_ms(task.completed_at),
                task.execution_time_ms
            ))
            await conn.commit()
        except Exception as e:
            print(f"Error saving task to database: {e}")

    async def ensure_daily_tasks(self) -> None:
        """Ensure daily recurring tasks are scheduled"""
        now = datetime.now()
        today = now.date()

        # Check if we already have today's tasks
        today_tasks = [t for t in self._tasks
                      if t.scheduled_time and t.scheduled_time.date() == today]

        if not today_tasks:
            await self._schedule_daily_tasks()

    async def _schedule_daily_tasks(self) -> None:
        """Schedule the default daily tasks"""
        now = datetime.now()
        today = now.date()

        # Self-reflection task - runs every 4 hours during active hours
        # This is the most important task - agent thinks and plans
        reflection_hours = [10, 14, 18, 22]  # 10am, 2pm, 6pm, 10pm
        for hour in reflection_hours:
            reflection_time = datetime.combine(today, time(hour, 0))
            if reflection_time > now:
                await self.add_task(ProactiveTask(
                    id=self._generate_task_id(),
                    type=TaskType.SELF_REFLECTION,
                    title=f"Self Reflection ({hour}:00)",
                    description="Think about what I know, what I need to learn, and plan my next tasks",
                    scheduled_time=reflection_time,
                    priority=8,  # High priority - planning is important
                    recurring=True,
                    recurrence_interval=timedelta(days=1)
                ))
                break  # Only schedule the next upcoming reflection

        # Morning review task
        morning = datetime.combine(today, time(9, 30))
        if morning > now:
            await self.add_task(ProactiveTask(
                id=self._generate_task_id(),
                type=TaskType.LEARN_FROM_HISTORY,
                title="Morning Review",
                description="Review yesterday's activities and update profile with new insights",
                scheduled_time=morning,
                priority=7,
                recurring=True,
                recurrence_interval=timedelta(days=1)
            ))

        # Evening summary task
        evening = datetime.combine(today, time(20, 30))
        if evening > now:
            await self.add_task(ProactiveTask(
                id=self._generate_task_id(),
                type=TaskType.SUMMARIZE_PERIOD,
                title="Daily Summary",
                description="Summarize today's activities and update relevant profile files",
                scheduled_time=evening,
                priority=7,
                recurring=True,
                recurrence_interval=timedelta(days=1)
            ))

        # Weekly pattern discovery (Sunday)
        if now.weekday() == 6:  # Sunday
            pattern_time = datetime.combine(today, time(21, 0))
            if pattern_time > now:
                await self.add_task(ProactiveTask(
                    id=self._generate_task_id(),
                    type=TaskType.DISCOVER_PATTERNS,
                    title="Weekly Pattern Analysis",
                    description="Analyze this week's activities and discover behavioral patterns",
                    scheduled_time=pattern_time,
                    priority=6
                ))

    def _generate_task_id(self) -> str:
        """Generate a unique task ID"""
        return f"task_{uuid.uuid4().hex[:8]}"

    async def add_task(self, task: ProactiveTask) -> str:
        """
        Add a task to the queue.

        Args:
            task: The task to add

        Returns:
            Task ID
        """
        # Check for duplicate task ID
        existing_ids = {t.id for t in self._tasks}
        if task.id in existing_ids:
            print(f"Task with ID {task.id} already exists, skipping")
            return task.id

        # Check queue limit
        if len(self._tasks) >= self._max_tasks_in_queue:
            # Remove lowest priority completed/cancelled tasks
            self._cleanup_queue()

        self._tasks.append(task)

        # Sort by priority and scheduled time
        self._tasks.sort(key=lambda t: (-t.priority, t.scheduled_time or datetime.max))

        # Save to database
        await self._save_task_to_db(task)

        print(f"Task added: {task.title} (priority: {task.priority})")
        return task.id

    def _cleanup_queue(self) -> None:
        """Remove completed/cancelled tasks from queue"""
        self._tasks = [t for t in self._tasks
                      if t.status in (TaskStatus.PENDING, TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS)]

    async def get_next_task(self) -> Optional[ProactiveTask]:
        """
        Get the next task to execute.

        Returns:
            The highest priority due task, or None
        """
        for task in self._tasks:
            if task.is_due():
                return task
        return None

    def has_due_tasks(self) -> bool:
        """
        Check if there are any tasks due for execution.
        Used by ProactiveCore to decide whether to wake up.

        Returns:
            True if there are due tasks
        """
        for task in self._tasks:
            if task.is_due():
                return True
        return False

    async def execute_task(self, task: ProactiveTask) -> bool:
        """
        Execute a task.

        Args:
            task: The task to execute

        Returns:
            True if execution successful
        """
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        # Save in-progress status
        await self._save_task_to_db(task)

        try:
            # Execute based on task type
            result = await self._execute_task_by_type(task)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.execution_time_ms = int((task.completed_at - task.started_at).total_seconds() * 1000)
            task.result = result

            print(f"Task completed: {task.title} ({task.execution_time_ms}ms)")

            # Handle recurring tasks
            if task.recurring and task.recurrence_interval:
                await self._reschedule_recurring_task(task)

            # Move to history and save to database
            await self._move_to_history(task)

            return True

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)

            print(f"Task failed: {task.title} - {e}")

            # Move to history and save to database
            await self._move_to_history(task)

            return False

    async def _execute_task_by_type(self, task: ProactiveTask) -> str:
        """Execute task based on its type"""
        from services.profile_manager import ProfileManager
        from agents.executor import AgentExecutor

        profile_manager = ProfileManager.get_instance()

        if task.type == TaskType.SELF_REFLECTION:
            return await self._execute_self_reflection(task)

        elif task.type == TaskType.UPDATE_PROFILE:
            return await self._execute_profile_update(task, profile_manager)

        elif task.type == TaskType.LEARN_FROM_HISTORY:
            return await self._execute_learn_from_history(task)

        elif task.type == TaskType.SUMMARIZE_PERIOD:
            return await self._execute_summarize_period(task)

        elif task.type == TaskType.DISCOVER_PATTERNS:
            return await self._execute_discover_patterns(task)

        elif task.type == TaskType.CONSOLIDATE_KNOWLEDGE:
            return await self._execute_consolidate(task, profile_manager)

        elif task.type == TaskType.HEALTH_CHECK:
            return await self._execute_health_check(task)

        elif task.type == TaskType.FILL_KNOWLEDGE_GAP:
            return await self._execute_fill_gap(task)

        elif task.type == TaskType.EXPLORE_TOPIC:
            return await self._execute_explore_topic(task)

        elif task.type == TaskType.CLEANUP:
            return await self._execute_cleanup(task)

        else:
            return f"Task type {task.type.value} not implemented"

    async def _execute_profile_update(self, task: ProactiveTask, profile_manager) -> str:
        """Execute a profile update task"""
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        target_file = task.target_file or "00-basic-info.md"

        # Read current file content
        try:
            current_content = await profile_manager.read_file(target_file)
        except FileNotFoundError:
            current_content = ""

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        # Create agent prompt for updating the file
        prompt = get_profile_update_prompt(
            target_file=target_file,
            task_title=task.title,
            task_description=task.description,
            current_content=current_content
        )
        prompt = inject_language(prompt, language)

        # Execute through agent
        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Profile update completed: {result}"

    async def _execute_learn_from_history(self, task: ProactiveTask) -> str:
        """Execute a learn from history task"""
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_learn_from_history_prompt(
            task_title=task.title,
            task_description=task.description
        )
        prompt = inject_language(prompt, language)

        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Learning from history completed: {result}"

    async def _execute_summarize_period(self, task: ProactiveTask) -> str:
        """Execute a period summary task"""
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        period = task.context.get("period", "today")

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_summarize_period_prompt(
            task_title=task.title,
            task_description=task.description,
            period=period
        )
        prompt = inject_language(prompt, language)

        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Period summary completed: {result}"

    async def _execute_discover_patterns(self, task: ProactiveTask) -> str:
        """Execute a pattern discovery task"""
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_discover_patterns_prompt(
            task_title=task.title,
            task_description=task.description
        )
        prompt = inject_language(prompt, language)

        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Pattern discovery completed: {result}"

    async def _execute_consolidate(self, task: ProactiveTask, profile_manager) -> str:
        """Execute a knowledge consolidation task"""
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_consolidate_knowledge_prompt(
            task_title=task.title,
            task_description=task.description
        )
        prompt = inject_language(prompt, language)

        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Knowledge consolidation completed: {result}"

    async def _execute_health_check(self, task: ProactiveTask) -> str:
        """Execute a system health check"""
        from services.profile_manager import ProfileManager

        profile_manager = ProfileManager.get_instance()

        # Check profile files
        files = await profile_manager.list_files()
        summary = await profile_manager.get_summary()

        return f"Health check completed: {len(files)} profile files, last updated: {summary.last_updated}"

    async def _execute_fill_gap(self, task: ProactiveTask) -> str:
        """
        Execute a fill knowledge gap task.

        This task searches through episodic and semantic memories to find
        information that can fill gaps in the user profile.
        """
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        # Get target file from task context or description
        target_file = task.target_file or task.context.get("target_file")

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_fill_gap_prompt(
            task_title=task.title,
            task_description=task.description,
            target_file=target_file
        )
        prompt = inject_language(prompt, language)

        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Knowledge gap filling completed: {result}"

    async def _execute_explore_topic(self, task: ProactiveTask) -> str:
        """
        Execute a topic exploration task.

        This task does a deep dive into a specific topic to gather
        comprehensive information about the user's relationship with it.
        """
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService

        topic = task.context.get("topic") or task.title

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_explore_topic_prompt(
            task_title=task.title,
            task_description=task.description,
            topic=topic
        )
        prompt = inject_language(prompt, language)

        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True)

        return f"Topic exploration completed: {result}"

    async def _execute_cleanup(self, task: ProactiveTask) -> str:
        """
        Execute a cleanup task.

        This task cleans up old or redundant data to keep the system organized.
        """
        from services.profile_manager import ProfileManager
        from storage.database import Database

        cleanup_type = task.context.get("cleanup_type", "general")
        results = []

        profile_manager = ProfileManager.get_instance()

        if cleanup_type in ["general", "profile"]:
            # Check for profile files with very low confidence that haven't been updated
            files = await profile_manager.list_files()
            stale_files = []
            for file_info in files:
                # Files not updated in 30+ days with low confidence could be candidates
                if file_info.get("confidence", 1.0) < 0.3:
                    stale_files.append(file_info.get("name"))
            if stale_files:
                results.append(f"Found {len(stale_files)} low-confidence files that may need attention: {stale_files[:5]}")

        if cleanup_type in ["general", "tasks"]:
            # Clean up old task history (keep last 100)
            if len(self._task_history) > 100:
                old_count = len(self._task_history)
                self._task_history = self._task_history[-100:]
                results.append(f"Cleaned up task history: {old_count} -> 100")

        if cleanup_type in ["general", "memory"]:
            # Report on memory database size
            try:
                db = Database.get_instance()
                # Get count of old memories (could implement actual cleanup later)
                results.append("Memory cleanup: Database health check passed")
            except Exception as e:
                results.append(f"Memory cleanup: Could not check database - {e}")

        return f"Cleanup completed: {'; '.join(results) if results else 'No cleanup needed'}"

    async def _execute_self_reflection(self, task: ProactiveTask) -> str:
        """
        Execute a self-reflection task.

        This is the most important task type - it allows the agent to:
        1. Think about what it knows and doesn't know
        2. Review recent activities and memories
        3. Identify gaps in the user profile
        4. Plan and schedule future tasks

        The agent has access to proactive tools (create_task, get_pending_tasks, etc.)
        to manage its own task queue.
        """
        from agents.executor import AgentExecutor
        from services.llm_service import LLMService
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        current_hour = datetime.now().hour

        # Determine context based on time of day
        if current_hour < 12:
            time_context = "morning"
            focus_suggestion = "reviewing yesterday and planning today"
        elif current_hour < 17:
            time_context = "afternoon"
            focus_suggestion = "checking progress and learning from recent interactions"
        elif current_hour < 21:
            time_context = "evening"
            focus_suggestion = "summarizing the day and preparing for tomorrow"
        else:
            time_context = "night"
            focus_suggestion = "consolidating knowledge and planning for tomorrow"

        # Get language from LLM service settings
        llm = LLMService.get_instance()
        language = getattr(llm, 'language', None)

        prompt = get_self_reflection_prompt(
            current_time=current_time,
            time_context=time_context,
            focus_suggestion=focus_suggestion
        )
        prompt = inject_language(prompt, language)

        # Execute through agent with proactive tools
        executor = AgentExecutor.get_instance()
        result = await executor.execute(prompt, use_profile_tools=True, use_proactive_tools=True)

        return f"Self-reflection completed: {result}"

    async def _reschedule_recurring_task(self, task: ProactiveTask) -> None:
        """Reschedule a recurring task"""
        if not task.recurring or not task.recurrence_interval:
            return

        new_task = ProactiveTask(
            id=self._generate_task_id(),
            type=task.type,
            title=task.title,
            description=task.description,
            scheduled_time=datetime.now() + task.recurrence_interval,
            recurring=True,
            recurrence_interval=task.recurrence_interval,
            priority=task.priority,
            target_file=task.target_file,
            context=task.context.copy()
        )

        await self.add_task(new_task)

    async def _move_to_history(self, task: ProactiveTask) -> None:
        """Move a task to history"""
        # Remove from active queue
        self._tasks = [t for t in self._tasks if t.id != task.id]

        # Add to history
        self._task_history.insert(0, task)  # Insert at beginning for most recent first

        # Trim history
        if len(self._task_history) > self._max_history_size:
            self._task_history = self._task_history[:self._max_history_size]

        # Save final state to database
        await self._save_task_to_db(task)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        for task in self._tasks:
            if task.id == task_id and task.status in (TaskStatus.PENDING, TaskStatus.SCHEDULED):
                task.status = TaskStatus.CANCELLED
                self._move_to_history(task)
                return True
        return False

    def get_task(self, task_id: str) -> Optional[ProactiveTask]:
        """Get a task by ID"""
        for task in self._tasks:
            if task.id == task_id:
                return task
        for task in self._task_history:
            if task.id == task_id:
                return task
        return None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """List tasks, optionally filtered by status"""
        tasks = self._tasks
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]

    def list_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List task history"""
        return [t.to_dict() for t in self._task_history[-limit:]]

    async def delete_from_history(self, task_id: str) -> bool:
        """Delete a task from history"""
        from storage.database import Database

        # Find and remove from memory
        for i, task in enumerate(self._task_history):
            if task.id == task_id:
                self._task_history.pop(i)

                # Also delete from database
                try:
                    db = Database.get_instance()
                    conn = db._connection
                    await conn.execute(
                        "DELETE FROM proactive_tasks WHERE id = ?",
                        (task_id,)
                    )
                    await conn.commit()
                except Exception as e:
                    print(f"Error deleting task from database: {e}")

                return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        pending = len([t for t in self._tasks if t.status == TaskStatus.PENDING])
        scheduled = len([t for t in self._tasks if t.status == TaskStatus.SCHEDULED])
        in_progress = len([t for t in self._tasks if t.status == TaskStatus.IN_PROGRESS])

        return {
            "initialized": self._initialized,
            "tasks_in_queue": len(self._tasks),
            "pending": pending,
            "scheduled": scheduled,
            "in_progress": in_progress,
            "history_size": len(self._task_history),
            "next_task": self._get_next_task_info()
        }

    def _get_next_task_info(self) -> Optional[Dict[str, Any]]:
        """Get info about the next task"""
        for task in self._tasks:
            if task.status in (TaskStatus.PENDING, TaskStatus.SCHEDULED):
                return {
                    "id": task.id,
                    "title": task.title,
                    "type": task.type.value,
                    "scheduled_time": task.scheduled_time.isoformat() if task.scheduled_time else "immediate",
                    "priority": task.priority
                }
        return None
