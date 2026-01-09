"""
Proactive Agent API Routes

API endpoints for managing the proactive agent system:
- Agent state and lifecycle control
- Task management
- Wakeup triggers and schedule
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

router = APIRouter()


# ==================== Request/Response Models ====================

class WakeupRequest(BaseModel):
    """Request to wake up the agent"""
    reason: str = Field(default="User request", description="Reason for waking up")


class SleepRequest(BaseModel):
    """Request to put agent to sleep"""
    reason: str = Field(default="User request", description="Reason for sleeping")


class ScheduleWakeupRequest(BaseModel):
    """Request to schedule a wakeup"""
    when: datetime = Field(..., description="When to wake up")
    reason: str = Field(default="Scheduled wakeup", description="Reason")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1-10)")


class CreateTaskRequest(BaseModel):
    """Request to create a new task"""
    type: str = Field(..., description="Task type (update_profile, learn_from_history, etc.)")
    title: str = Field(..., description="Task title")
    description: str = Field(default="", description="Task description")
    scheduled_time: Optional[datetime] = Field(None, description="When to execute")
    priority: int = Field(default=5, ge=1, le=10, description="Priority (1-10)")
    recurring: bool = Field(default=False, description="Whether task recurs")
    recurrence_hours: Optional[float] = Field(None, description="Hours between recurrences")
    target_file: Optional[str] = Field(None, description="Target profile file")


class UpdateScheduleRequest(BaseModel):
    """Request to update wakeup schedule"""
    morning_hour: Optional[int] = Field(None, ge=0, le=23)
    morning_minute: Optional[int] = Field(None, ge=0, le=59)
    evening_hour: Optional[int] = Field(None, ge=0, le=23)
    evening_minute: Optional[int] = Field(None, ge=0, le=59)
    active_days: Optional[List[int]] = Field(None, description="Active days (0=Monday, 6=Sunday)")
    enabled: bool = Field(default=True)


class CreateTriggerRequest(BaseModel):
    """Request to create a wakeup trigger"""
    type: str = Field(..., description="Trigger type (scheduled, periodic)")
    name: str = Field(..., description="Trigger name")
    scheduled_time: Optional[datetime] = Field(None, description="For scheduled triggers")
    interval_hours: Optional[float] = Field(None, description="For periodic triggers")
    priority: int = Field(default=5, ge=1, le=10)
    reason: str = Field(default="", description="Trigger reason")


# ==================== Helper Functions ====================

def _get_proactive_core():
    """Get the ProactiveCore instance"""
    from proactive.core import ProactiveCore
    return ProactiveCore.get_instance()


def _get_wakeup_manager():
    """Get the WakeupManager instance"""
    from proactive.wakeup import WakeupManager
    return WakeupManager.get_instance()


async def _get_task_scheduler_async():
    """Get the TaskScheduler instance, ensuring it's loaded from database"""
    from proactive.task_scheduler import TaskScheduler
    scheduler = TaskScheduler.get_instance()
    # Ensure tasks are loaded from database on first access
    if not scheduler._initialized:
        await scheduler._load_tasks_from_db()
        scheduler._initialized = True
    return scheduler


def _get_task_scheduler():
    """Get the TaskScheduler instance (sync version)"""
    from proactive.task_scheduler import TaskScheduler
    return TaskScheduler.get_instance()


# ==================== Agent Status Endpoints ====================

@router.get("/status")
async def get_agent_status() -> dict:
    """Get the current status of the proactive agent."""
    try:
        core = _get_proactive_core()
        wakeup = _get_wakeup_manager()
        scheduler = _get_task_scheduler()

        return {
            "success": True,
            "agent": core.get_status(),
            "wakeup": wakeup.get_status(),
            "scheduler": scheduler.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_agent(background_tasks: BackgroundTasks) -> dict:
    """Start the proactive agent."""
    try:
        core = _get_proactive_core()
        background_tasks.add_task(core.start)
        return {
            "success": True,
            "message": "Proactive agent starting"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_agent() -> dict:
    """Stop the proactive agent."""
    try:
        core = _get_proactive_core()
        await core.stop()
        return {
            "success": True,
            "message": "Proactive agent stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wake")
async def wake_agent(request: WakeupRequest, background_tasks: BackgroundTasks) -> dict:
    """Wake up the proactive agent."""
    try:
        core = _get_proactive_core()

        # Initialize and start the main loop if not running
        if not core._running:
            await core.initialize()
            background_tasks.add_task(core.start)

        success = await core.wake_up(request.reason)
        return {
            "success": success,
            "message": "Agent woken up" if success else "Agent was already awake",
            "state": core.state.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sleep")
async def sleep_agent(request: SleepRequest) -> dict:
    """Put the proactive agent to sleep."""
    try:
        core = _get_proactive_core()
        success = await core.go_to_sleep(request.reason)
        return {
            "success": success,
            "message": "Agent going to sleep" if success else "Agent cannot sleep (may be working)",
            "state": core.state.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Task Endpoints ====================

@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50) -> dict:
    """List proactive tasks."""
    try:
        scheduler = await _get_task_scheduler_async()
        tasks = scheduler.list_tasks()

        if status:
            tasks = [t for t in tasks if t.get('status') == status]

        return {
            "success": True,
            "count": len(tasks),
            "tasks": tasks[:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/history")
async def get_task_history(limit: int = 50) -> dict:
    """Get task execution history."""
    try:
        scheduler = await _get_task_scheduler_async()
        history = scheduler.list_history(limit)
        return {
            "success": True,
            "count": len(history),
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    """Get a specific task."""
    try:
        scheduler = _get_task_scheduler()
        task = scheduler.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return {
            "success": True,
            "task": task.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks")
async def create_task(request: CreateTaskRequest) -> dict:
    """Create a new proactive task."""
    try:
        from proactive.task_scheduler import TaskScheduler, ProactiveTask, TaskType

        scheduler = _get_task_scheduler()

        # Parse task type
        try:
            task_type = TaskType(request.type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid task type: {request.type}")

        # Create task
        task = ProactiveTask(
            id=scheduler._generate_task_id(),
            type=task_type,
            title=request.title,
            description=request.description,
            scheduled_time=request.scheduled_time,
            priority=request.priority,
            recurring=request.recurring,
            recurrence_interval=timedelta(hours=request.recurrence_hours) if request.recurrence_hours else None,
            target_file=request.target_file
        )

        task_id = await scheduler.add_task(task)

        return {
            "success": True,
            "task_id": task_id,
            "message": f"Task created: {request.title}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str) -> dict:
    """Cancel a pending task."""
    try:
        scheduler = _get_task_scheduler()
        success = scheduler.cancel_task(task_id)
        if success:
            return {
                "success": True,
                "message": f"Task cancelled: {task_id}"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Task not found or cannot be cancelled (may already be completed)"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/history/{task_id}")
async def delete_task_history(task_id: str) -> dict:
    """Delete a task from history."""
    try:
        scheduler = _get_task_scheduler()
        success = await scheduler.delete_from_history(task_id)
        if success:
            return {
                "success": True,
                "message": f"Task deleted from history: {task_id}"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail="Task not found in history"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Wakeup Schedule Endpoints ====================

@router.get("/schedule")
async def get_schedule() -> dict:
    """Get the wakeup schedule."""
    try:
        wakeup = _get_wakeup_manager()
        return {
            "success": True,
            "schedule": wakeup.get_schedule()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schedule")
async def update_schedule(request: UpdateScheduleRequest) -> dict:
    """Update the wakeup schedule."""
    try:
        from datetime import time

        wakeup = _get_wakeup_manager()

        morning = None
        if request.morning_hour is not None and request.morning_minute is not None:
            morning = time(request.morning_hour, request.morning_minute)

        evening = None
        if request.evening_hour is not None and request.evening_minute is not None:
            evening = time(request.evening_hour, request.evening_minute)

        wakeup.set_schedule(
            morning=morning,
            evening=evening,
            active_days=request.active_days,
            enabled=request.enabled
        )

        return {
            "success": True,
            "message": "Schedule updated",
            "schedule": wakeup.get_schedule()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule/wakeup")
async def schedule_wakeup(request: ScheduleWakeupRequest) -> dict:
    """Schedule a one-time wakeup."""
    try:
        wakeup = _get_wakeup_manager()
        trigger_id = await wakeup.schedule_wakeup(
            when=request.when,
            reason=request.reason,
            priority=request.priority
        )
        return {
            "success": True,
            "trigger_id": trigger_id,
            "message": f"Wakeup scheduled for {request.when.isoformat()}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Trigger Endpoints ====================

@router.get("/triggers")
async def list_triggers() -> dict:
    """List all wakeup triggers."""
    try:
        wakeup = _get_wakeup_manager()
        triggers = wakeup.list_triggers()
        return {
            "success": True,
            "count": len(triggers),
            "triggers": triggers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triggers")
async def create_trigger(request: CreateTriggerRequest) -> dict:
    """Create a new wakeup trigger."""
    try:
        from proactive.wakeup import WakeupManager, WakeupTrigger, WakeupTriggerType

        wakeup = _get_wakeup_manager()

        # Parse trigger type
        try:
            trigger_type = WakeupTriggerType(request.type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid trigger type: {request.type}")

        trigger = WakeupTrigger(
            id=wakeup._next_trigger_id(),
            type=trigger_type,
            name=request.name,
            scheduled_time=request.scheduled_time,
            interval=timedelta(hours=request.interval_hours) if request.interval_hours else None,
            priority=request.priority,
            reason=request.reason
        )

        trigger_id = wakeup.add_trigger(trigger)

        return {
            "success": True,
            "trigger_id": trigger_id,
            "message": f"Trigger created: {request.name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str) -> dict:
    """Delete a wakeup trigger."""
    try:
        wakeup = _get_wakeup_manager()
        success = wakeup.remove_trigger(trigger_id)
        if success:
            return {
                "success": True,
                "message": f"Trigger deleted: {trigger_id}"
            }
        else:
            raise HTTPException(status_code=404, detail=f"Trigger not found: {trigger_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Quick Actions ====================

@router.post("/actions/immediate-wakeup")
async def immediate_wakeup(reason: str = "User requested immediate wakeup") -> dict:
    """Trigger an immediate wakeup."""
    try:
        wakeup = _get_wakeup_manager()
        success = await wakeup.request_immediate_wakeup(reason)
        return {
            "success": success,
            "message": "Agent woken up" if success else "Agent was already awake"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/run-task")
async def run_task_now(task_type: str, title: str = "Manual task", background_tasks: BackgroundTasks = None) -> dict:
    """Create and immediately queue a task."""
    try:
        from proactive.task_scheduler import TaskScheduler, ProactiveTask, TaskType

        scheduler = _get_task_scheduler()
        core = _get_proactive_core()

        # Initialize and start the main loop if not running
        if not core._running:
            await core.initialize()
            if background_tasks:
                background_tasks.add_task(core.start)

        # Ensure agent is awake
        if not core.is_awake:
            await core.wake_up("Running manual task")

        # Parse task type
        try:
            task_type_enum = TaskType(task_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid task type: {task_type}")

        task = ProactiveTask(
            id=scheduler._generate_task_id(),
            type=task_type_enum,
            title=title,
            description=f"Manual {task_type} task",
            priority=10  # High priority for manual tasks
        )

        task_id = await scheduler.add_task(task)

        return {
            "success": True,
            "task_id": task_id,
            "message": f"Task queued: {title}",
            "agent_state": core.state.value
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task-types")
async def get_task_types() -> dict:
    """Get available task types."""
    from proactive.task_scheduler import TaskType

    return {
        "success": True,
        "task_types": [
            {"value": t.value, "name": t.name}
            for t in TaskType
        ]
    }
