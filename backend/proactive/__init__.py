"""
Proactive Agent Module

This module implements the autonomous proactive agent system that can:
- Self-schedule tasks
- Control its own sleep/wake cycles
- Accumulate knowledge about the user in Profile files
"""

from .core import ProactiveCore, AgentState
from .wakeup import WakeupManager, WakeupTriggerType
from .task_scheduler import TaskScheduler, ProactiveTask, TaskType, TaskStatus

__all__ = [
    'ProactiveCore',
    'AgentState',
    'WakeupManager',
    'WakeupTriggerType',
    'TaskScheduler',
    'ProactiveTask',
    'TaskType',
    'TaskStatus',
]
