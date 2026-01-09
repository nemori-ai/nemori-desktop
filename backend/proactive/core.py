"""
ProactiveCore - The central state machine for the proactive agent

Manages the agent's lifecycle states and coordinates between:
- WakeupManager (sleep/wake control)
- TaskScheduler (task queue management)
- ProfileManager (file-based knowledge)
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

from config.settings import settings


class AgentState(Enum):
    """Agent lifecycle states"""
    SLEEPING = "sleeping"           # Agent is dormant
    WAKING_UP = "waking_up"         # Agent is initializing
    AWAKE = "awake"                 # Agent is idle, ready for tasks
    WORKING = "working"             # Agent is executing a task
    GOING_TO_SLEEP = "going_to_sleep"  # Agent is preparing to sleep


@dataclass
class StateTransition:
    """Record of a state transition"""
    from_state: AgentState
    to_state: AgentState
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Context information for agent decision making"""
    current_state: AgentState
    last_wakeup: Optional[datetime]
    last_sleep: Optional[datetime]
    tasks_completed_today: int
    next_scheduled_task: Optional[datetime]
    user_is_active: bool
    profile_last_updated: Optional[datetime]


class ProactiveCore:
    """
    Central state machine for the proactive agent.

    State transitions:
        SLEEPING -> WAKING_UP (on trigger)
        WAKING_UP -> AWAKE (after initialization)
        AWAKE -> WORKING (when task starts)
        WORKING -> AWAKE (when task completes)
        AWAKE -> GOING_TO_SLEEP (when deciding to sleep)
        GOING_TO_SLEEP -> SLEEPING (after cleanup)
    """

    _instance: Optional["ProactiveCore"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._state = AgentState.SLEEPING
        self._state_lock = asyncio.Lock()
        self._transitions: List[StateTransition] = []
        self._context = AgentContext(
            current_state=AgentState.SLEEPING,
            last_wakeup=None,
            last_sleep=None,
            tasks_completed_today=0,
            next_scheduled_task=None,
            user_is_active=False,
            profile_last_updated=None
        )

        # State change callbacks
        self._on_state_change: List[Callable[[AgentState, AgentState], None]] = []

        # Components (lazy loaded)
        self._wakeup_manager = None
        self._task_scheduler = None
        self._profile_manager = None

        # Configuration
        self._max_working_duration = timedelta(minutes=30)  # Max time in WORKING state
        self._idle_timeout = timedelta(minutes=5)  # Time before auto-sleep

        self._initialized = False
        self._running = False
        self._main_loop_task: Optional[asyncio.Task] = None

    @classmethod
    def get_instance(cls) -> "ProactiveCore":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def state(self) -> AgentState:
        """Current agent state"""
        return self._state

    @property
    def context(self) -> AgentContext:
        """Current agent context"""
        return self._context

    @property
    def is_awake(self) -> bool:
        """Check if agent is awake (AWAKE or WORKING)"""
        return self._state in (AgentState.AWAKE, AgentState.WORKING)

    @property
    def is_sleeping(self) -> bool:
        """Check if agent is sleeping"""
        return self._state == AgentState.SLEEPING

    async def initialize(self) -> None:
        """Initialize the proactive core and all components"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Import here to avoid circular imports
            from services.profile_manager import ProfileManager
            from .wakeup import WakeupManager
            from .task_scheduler import TaskScheduler

            # Initialize components
            self._profile_manager = ProfileManager.get_instance()
            await self._profile_manager.initialize()

            self._wakeup_manager = WakeupManager.get_instance()
            await self._wakeup_manager.initialize(self)

            self._task_scheduler = TaskScheduler.get_instance()
            await self._task_scheduler.initialize(self)

            self._initialized = True
            print("ProactiveCore initialized")

    async def start(self) -> None:
        """Start the proactive agent main loop"""
        await self.initialize()

        if self._running:
            return

        self._running = True
        self._main_loop_task = asyncio.create_task(self._main_loop())
        print("ProactiveCore started")

    async def stop(self) -> None:
        """Stop the proactive agent"""
        self._running = False

        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass

        # Ensure we're in SLEEPING state
        if self._state != AgentState.SLEEPING:
            await self._transition_to(AgentState.SLEEPING, "System shutdown")

        print("ProactiveCore stopped")

    async def _main_loop(self) -> None:
        """Main event loop for the proactive agent"""
        while self._running:
            try:
                # Check for wakeup triggers
                if self._state == AgentState.SLEEPING:
                    # First check wakeup triggers (scheduled wakeups)
                    trigger = await self._wakeup_manager.check_triggers()
                    if trigger:
                        await self.wake_up(trigger.reason)
                    # Also check if there are due tasks that need execution
                    elif self._task_scheduler and self._task_scheduler.has_due_tasks():
                        await self.wake_up("Due tasks in queue")

                # Process tasks if awake
                elif self._state == AgentState.AWAKE:
                    # Check for pending tasks
                    task = await self._task_scheduler.get_next_task()
                    if task:
                        await self._execute_task(task)
                    else:
                        # Check if we should go to sleep
                        if await self._should_sleep():
                            await self.go_to_sleep("No pending tasks")

                # Check for timeout in WORKING state
                elif self._state == AgentState.WORKING:
                    # The task executor handles completion
                    pass

                # Small delay to prevent busy loop
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in proactive main loop: {e}")
                await asyncio.sleep(5)  # Back off on error

    async def wake_up(self, reason: str = "Manual wakeup") -> bool:
        """
        Wake up the agent.

        Args:
            reason: Why the agent is waking up

        Returns:
            True if wakeup successful, False otherwise
        """
        if self._state not in (AgentState.SLEEPING, AgentState.GOING_TO_SLEEP):
            return False  # Already awake or waking up

        # Transition through WAKING_UP state
        await self._transition_to(AgentState.WAKING_UP, reason)

        # Perform wakeup initialization
        await self._on_wakeup()

        # Complete transition to AWAKE
        await self._transition_to(AgentState.AWAKE, "Initialization complete")

        return True

    async def go_to_sleep(self, reason: str = "Idle timeout") -> bool:
        """
        Put the agent to sleep.

        Args:
            reason: Why the agent is going to sleep

        Returns:
            True if transition successful
        """
        if self._state == AgentState.SLEEPING:
            return True  # Already sleeping

        if self._state == AgentState.WORKING:
            return False  # Can't sleep while working

        # Transition through GOING_TO_SLEEP state
        await self._transition_to(AgentState.GOING_TO_SLEEP, reason)

        # Perform sleep preparation
        await self._on_going_to_sleep()

        # Complete transition to SLEEPING
        await self._transition_to(AgentState.SLEEPING, "Sleep preparation complete")

        return True

    async def _transition_to(self, new_state: AgentState, reason: str) -> None:
        """
        Transition to a new state.

        Args:
            new_state: Target state
            reason: Reason for transition
        """
        async with self._state_lock:
            old_state = self._state

            # Validate transition
            if not self._is_valid_transition(old_state, new_state):
                raise ValueError(f"Invalid state transition: {old_state} -> {new_state}")

            # Record transition
            transition = StateTransition(
                from_state=old_state,
                to_state=new_state,
                timestamp=datetime.now(),
                reason=reason
            )
            self._transitions.append(transition)

            # Keep only last 100 transitions
            if len(self._transitions) > 100:
                self._transitions = self._transitions[-100:]

            # Update state
            self._state = new_state
            self._context.current_state = new_state

            # Update timestamps
            if new_state == AgentState.AWAKE:
                self._context.last_wakeup = datetime.now()
            elif new_state == AgentState.SLEEPING:
                self._context.last_sleep = datetime.now()

            print(f"State transition: {old_state.value} -> {new_state.value} ({reason})")

            # Notify listeners
            for callback in self._on_state_change:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    print(f"Error in state change callback: {e}")

    def _is_valid_transition(self, from_state: AgentState, to_state: AgentState) -> bool:
        """Check if a state transition is valid"""
        valid_transitions = {
            AgentState.SLEEPING: {AgentState.WAKING_UP},
            AgentState.WAKING_UP: {AgentState.AWAKE, AgentState.SLEEPING},
            AgentState.AWAKE: {AgentState.WORKING, AgentState.GOING_TO_SLEEP, AgentState.SLEEPING},
            AgentState.WORKING: {AgentState.AWAKE, AgentState.GOING_TO_SLEEP},
            AgentState.GOING_TO_SLEEP: {AgentState.SLEEPING, AgentState.AWAKE},
        }
        return to_state in valid_transitions.get(from_state, set())

    async def _on_wakeup(self) -> None:
        """Called when agent is waking up"""
        # Load profile summary
        if self._profile_manager:
            summary = await self._profile_manager.get_summary()
            self._context.profile_last_updated = summary.last_updated

        # Reset daily counters if new day
        now = datetime.now()
        if self._context.last_wakeup:
            if now.date() > self._context.last_wakeup.date():
                self._context.tasks_completed_today = 0

        # Schedule default tasks if none exist
        if self._task_scheduler:
            await self._task_scheduler.ensure_daily_tasks()

    async def _on_going_to_sleep(self) -> None:
        """Called when agent is going to sleep"""
        # Save any pending state
        pass

    async def _execute_task(self, task) -> None:
        """Execute a task"""
        await self._transition_to(AgentState.WORKING, f"Executing task: {task.title}")

        try:
            # Execute task through task scheduler
            await self._task_scheduler.execute_task(task)
            self._context.tasks_completed_today += 1
        except Exception as e:
            print(f"Error executing task {task.id}: {e}")
        finally:
            # Return to AWAKE state
            if self._state == AgentState.WORKING:
                await self._transition_to(AgentState.AWAKE, "Task completed")

    async def _should_sleep(self) -> bool:
        """Determine if agent should go to sleep"""
        # Don't sleep if there are pending tasks soon
        if self._context.next_scheduled_task:
            time_to_task = self._context.next_scheduled_task - datetime.now()
            if time_to_task < timedelta(minutes=10):
                return False

        # Check idle timeout
        if self._context.last_wakeup:
            idle_time = datetime.now() - self._context.last_wakeup
            if idle_time > self._idle_timeout:
                return True

        return False

    def add_state_change_listener(self, callback: Callable[[AgentState, AgentState], None]) -> None:
        """Add a listener for state changes"""
        self._on_state_change.append(callback)

    def remove_state_change_listener(self, callback: Callable[[AgentState, AgentState], None]) -> None:
        """Remove a state change listener"""
        if callback in self._on_state_change:
            self._on_state_change.remove(callback)

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            "state": self._state.value,
            "is_awake": self.is_awake,
            "last_wakeup": self._context.last_wakeup.isoformat() if self._context.last_wakeup else None,
            "last_sleep": self._context.last_sleep.isoformat() if self._context.last_sleep else None,
            "tasks_completed_today": self._context.tasks_completed_today,
            "next_scheduled_task": self._context.next_scheduled_task.isoformat() if self._context.next_scheduled_task else None,
            "recent_transitions": [
                {
                    "from": t.from_state.value,
                    "to": t.to_state.value,
                    "timestamp": t.timestamp.isoformat(),
                    "reason": t.reason
                }
                for t in self._transitions[-10:]
            ]
        }

    async def force_state(self, new_state: AgentState, reason: str = "Forced by user") -> None:
        """Force a state transition (for debugging/admin)"""
        async with self._state_lock:
            old_state = self._state
            self._state = new_state
            self._context.current_state = new_state

            transition = StateTransition(
                from_state=old_state,
                to_state=new_state,
                timestamp=datetime.now(),
                reason=f"[FORCED] {reason}"
            )
            self._transitions.append(transition)

            print(f"Forced state transition: {old_state.value} -> {new_state.value}")
