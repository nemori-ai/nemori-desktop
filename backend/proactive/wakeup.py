"""
WakeupManager - Controls the agent's sleep/wake cycles

Manages various triggers that can wake up the proactive agent:
- Scheduled time triggers
- Periodic triggers
- Task due triggers
- New data thresholds
- User manual triggers
"""

import asyncio
from datetime import datetime, timedelta, time
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
import json

from config.settings import settings

if TYPE_CHECKING:
    from .core import ProactiveCore


class WakeupTriggerType(Enum):
    """Types of wakeup triggers"""
    SCHEDULED = "scheduled"           # Specific time trigger
    PERIODIC = "periodic"             # Recurring trigger
    TASK_DUE = "task_due"             # Task is due
    NEW_DATA = "new_data"             # New data threshold reached
    USER_REQUEST = "user_request"     # Manual user trigger
    SYSTEM = "system"                 # System event


@dataclass
class WakeupTrigger:
    """A trigger that can wake up the agent"""
    id: str
    type: WakeupTriggerType
    name: str
    enabled: bool = True

    # Timing
    scheduled_time: Optional[datetime] = None  # For SCHEDULED
    interval: Optional[timedelta] = None       # For PERIODIC
    last_triggered: Optional[datetime] = None

    # Conditions
    condition: Optional[str] = None            # Custom condition
    priority: int = 5                          # 1-10, higher = more urgent

    # Metadata
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_due(self) -> bool:
        """Check if this trigger is due"""
        if not self.enabled:
            return False

        now = datetime.now()

        if self.type == WakeupTriggerType.SCHEDULED:
            if self.scheduled_time and now >= self.scheduled_time:
                # Only trigger once
                if self.last_triggered and self.last_triggered >= self.scheduled_time:
                    return False
                return True

        elif self.type == WakeupTriggerType.PERIODIC:
            if self.interval:
                if self.last_triggered is None:
                    return True
                if now - self.last_triggered >= self.interval:
                    return True

        return False


@dataclass
class WakeupSchedule:
    """Daily wakeup schedule"""
    enabled: bool = True
    morning_wakeup: time = field(default_factory=lambda: time(9, 0))   # 9:00 AM
    evening_wakeup: time = field(default_factory=lambda: time(20, 0))  # 8:00 PM
    active_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # All days

    def get_next_wakeup(self) -> Optional[datetime]:
        """Get the next scheduled wakeup time"""
        now = datetime.now()
        today = now.date()

        # Check if today's wakeups are still pending
        morning = datetime.combine(today, self.morning_wakeup)
        evening = datetime.combine(today, self.evening_wakeup)

        if now < morning and today.weekday() in self.active_days:
            return morning
        if now < evening and today.weekday() in self.active_days:
            return evening

        # Find next active day
        for days_ahead in range(1, 8):
            next_day = today + timedelta(days=days_ahead)
            if next_day.weekday() in self.active_days:
                return datetime.combine(next_day, self.morning_wakeup)

        return None


class WakeupManager:
    """
    Manages the agent's wakeup triggers and schedule.

    Responsibilities:
    - Maintain list of active triggers
    - Check for due triggers
    - Manage the daily wakeup schedule
    - Handle user-initiated wakeups
    """

    _instance: Optional["WakeupManager"] = None

    def __init__(self):
        self._core: Optional["ProactiveCore"] = None
        self._triggers: List[WakeupTrigger] = []
        self._schedule = WakeupSchedule()
        self._initialized = False
        self._trigger_id_counter = 0

        # Configuration
        self._min_sleep_duration = timedelta(minutes=5)
        self._max_sleep_duration = timedelta(hours=24)

    @classmethod
    def get_instance(cls) -> "WakeupManager":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self, core: "ProactiveCore") -> None:
        """Initialize the wakeup manager"""
        if self._initialized:
            return

        self._core = core

        # Add default periodic triggers
        await self._setup_default_triggers()

        self._initialized = True
        print("WakeupManager initialized")

    async def _setup_default_triggers(self) -> None:
        """Setup default wakeup triggers"""
        # Morning wakeup
        morning_time = datetime.combine(
            datetime.now().date(),
            self._schedule.morning_wakeup
        )
        if morning_time < datetime.now():
            morning_time += timedelta(days=1)

        self.add_trigger(WakeupTrigger(
            id=self._next_trigger_id(),
            type=WakeupTriggerType.SCHEDULED,
            name="Morning Wakeup",
            scheduled_time=morning_time,
            priority=7,
            reason="Daily morning routine"
        ))

        # Evening wakeup
        evening_time = datetime.combine(
            datetime.now().date(),
            self._schedule.evening_wakeup
        )
        if evening_time < datetime.now():
            evening_time += timedelta(days=1)

        self.add_trigger(WakeupTrigger(
            id=self._next_trigger_id(),
            type=WakeupTriggerType.SCHEDULED,
            name="Evening Wakeup",
            scheduled_time=evening_time,
            priority=7,
            reason="Daily evening review"
        ))

        # Periodic health check (every 2 hours)
        self.add_trigger(WakeupTrigger(
            id=self._next_trigger_id(),
            type=WakeupTriggerType.PERIODIC,
            name="Periodic Health Check",
            interval=timedelta(hours=2),
            priority=3,
            reason="Regular system health check"
        ))

    def _next_trigger_id(self) -> str:
        """Generate next trigger ID"""
        self._trigger_id_counter += 1
        return f"trigger_{self._trigger_id_counter}"

    async def check_triggers(self) -> Optional[WakeupTrigger]:
        """
        Check all triggers and return the highest priority due trigger.

        Returns:
            The highest priority trigger that is due, or None
        """
        due_triggers = [t for t in self._triggers if t.is_due()]

        if not due_triggers:
            return None

        # Sort by priority (highest first)
        due_triggers.sort(key=lambda t: t.priority, reverse=True)
        trigger = due_triggers[0]

        # Mark as triggered
        trigger.last_triggered = datetime.now()

        # Reschedule if periodic
        if trigger.type == WakeupTriggerType.SCHEDULED:
            trigger.enabled = False  # One-shot triggers are disabled

        return trigger

    def add_trigger(self, trigger: WakeupTrigger) -> str:
        """Add a new wakeup trigger"""
        self._triggers.append(trigger)
        return trigger.id

    def remove_trigger(self, trigger_id: str) -> bool:
        """Remove a trigger by ID"""
        for i, t in enumerate(self._triggers):
            if t.id == trigger_id:
                self._triggers.pop(i)
                return True
        return False

    def get_trigger(self, trigger_id: str) -> Optional[WakeupTrigger]:
        """Get a trigger by ID"""
        for t in self._triggers:
            if t.id == trigger_id:
                return t
        return None

    def list_triggers(self) -> List[Dict[str, Any]]:
        """List all triggers"""
        return [
            {
                "id": t.id,
                "type": t.type.value,
                "name": t.name,
                "enabled": t.enabled,
                "scheduled_time": t.scheduled_time.isoformat() if t.scheduled_time else None,
                "interval_minutes": t.interval.total_seconds() / 60 if t.interval else None,
                "last_triggered": t.last_triggered.isoformat() if t.last_triggered else None,
                "priority": t.priority,
                "reason": t.reason
            }
            for t in self._triggers
        ]

    async def schedule_wakeup(
        self,
        when: datetime,
        reason: str = "Scheduled wakeup",
        priority: int = 5
    ) -> str:
        """
        Schedule a one-time wakeup.

        Args:
            when: When to wake up
            reason: Why to wake up
            priority: Trigger priority (1-10)

        Returns:
            Trigger ID
        """
        trigger = WakeupTrigger(
            id=self._next_trigger_id(),
            type=WakeupTriggerType.SCHEDULED,
            name=f"Scheduled: {reason}",
            scheduled_time=when,
            priority=priority,
            reason=reason
        )
        self._triggers.append(trigger)
        return trigger.id

    async def request_immediate_wakeup(self, reason: str = "User request") -> bool:
        """
        Request immediate wakeup (user-initiated).

        Returns:
            True if wakeup initiated
        """
        if self._core and self._core.is_sleeping:
            trigger = WakeupTrigger(
                id=self._next_trigger_id(),
                type=WakeupTriggerType.USER_REQUEST,
                name="Immediate Wakeup",
                scheduled_time=datetime.now(),
                priority=10,
                reason=reason
            )
            trigger.last_triggered = datetime.now()

            # Wake up the core
            return await self._core.wake_up(reason)
        return False

    def set_schedule(
        self,
        morning: Optional[time] = None,
        evening: Optional[time] = None,
        active_days: Optional[List[int]] = None,
        enabled: bool = True
    ) -> None:
        """Update the wakeup schedule"""
        if morning is not None:
            self._schedule.morning_wakeup = morning
        if evening is not None:
            self._schedule.evening_wakeup = evening
        if active_days is not None:
            self._schedule.active_days = active_days
        self._schedule.enabled = enabled

    def get_schedule(self) -> Dict[str, Any]:
        """Get current wakeup schedule"""
        return {
            "enabled": self._schedule.enabled,
            "morning_wakeup": self._schedule.morning_wakeup.isoformat(),
            "evening_wakeup": self._schedule.evening_wakeup.isoformat(),
            "active_days": self._schedule.active_days,
            "next_wakeup": self._schedule.get_next_wakeup().isoformat() if self._schedule.get_next_wakeup() else None
        }

    def calculate_sleep_duration(self, context: Optional[Dict[str, Any]] = None) -> timedelta:
        """
        Calculate recommended sleep duration based on context.

        Args:
            context: Optional context for decision making

        Returns:
            Recommended sleep duration
        """
        # Get next scheduled wakeup
        next_wakeup = self._schedule.get_next_wakeup()

        if next_wakeup:
            time_to_wakeup = next_wakeup - datetime.now()

            # Wake up 5 minutes early
            sleep_duration = time_to_wakeup - timedelta(minutes=5)

            # Clamp to min/max
            if sleep_duration < self._min_sleep_duration:
                return self._min_sleep_duration
            if sleep_duration > self._max_sleep_duration:
                return self._max_sleep_duration

            return sleep_duration

        # Default: 1 hour
        return timedelta(hours=1)

    def get_status(self) -> Dict[str, Any]:
        """Get wakeup manager status"""
        return {
            "initialized": self._initialized,
            "triggers_count": len(self._triggers),
            "enabled_triggers": len([t for t in self._triggers if t.enabled]),
            "schedule": self.get_schedule(),
            "next_trigger": self._get_next_trigger_info()
        }

    def _format_time_until(self, delta: timedelta) -> str:
        """Format a timedelta as human-readable string"""
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "Now"

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 and hours == 0:  # Only show seconds if less than 1 hour
            parts.append(f"{seconds}s")

        return " ".join(parts) if parts else "Now"

    def _get_next_trigger_info(self) -> Optional[Dict[str, Any]]:
        """Get info about the next trigger to fire"""
        now = datetime.now()
        next_trigger = None
        next_time = None

        for t in self._triggers:
            if not t.enabled:
                continue

            trigger_time = None
            if t.type == WakeupTriggerType.SCHEDULED and t.scheduled_time:
                if t.scheduled_time > now:
                    trigger_time = t.scheduled_time
            elif t.type == WakeupTriggerType.PERIODIC and t.interval:
                if t.last_triggered:
                    trigger_time = t.last_triggered + t.interval
                else:
                    trigger_time = now  # Will trigger immediately

            if trigger_time and (next_time is None or trigger_time < next_time):
                next_time = trigger_time
                next_trigger = t

        if next_trigger:
            time_until = self._format_time_until(next_time - now) if next_time else None
            return {
                "id": next_trigger.id,
                "name": next_trigger.name,
                "type": next_trigger.type.value,
                "scheduled_for": next_time.isoformat() if next_time else None,
                "time_until": time_until
            }
        return None
