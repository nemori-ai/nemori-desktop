"""
Profile Agent API Routes - REST endpoints for the profile maintenance agent

Provides endpoints for:
- Getting agent/scheduler status
- Manually triggering profile maintenance
- Viewing task history
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.profile_scheduler import ProfileScheduler

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== Response Models ====================

class AgentStatusResponse(BaseModel):
    """Response containing agent status"""
    running: bool
    interval_hours: int
    next_run: Optional[str]
    agent_is_running: bool
    agent_last_run: Optional[str]


class TaskResponse(BaseModel):
    """Response containing a task record"""
    id: str
    trigger: str
    work_type: Optional[str]
    summary: Optional[str]
    files_modified: List[str]
    created_at: Optional[str]
    completed_at: Optional[str]
    status: str


class TriggerResponse(BaseModel):
    """Response from triggering the agent"""
    success: bool
    task_id: Optional[str] = None
    trigger: Optional[str] = None
    work_type: Optional[str] = None
    summary: Optional[str] = None
    files_modified: Optional[List[str]] = None
    error: Optional[str] = None
    response: Optional[str] = None


# ==================== Endpoints ====================

@router.get("/status")
async def get_status() -> AgentStatusResponse:
    """Get profile agent and scheduler status"""
    scheduler = ProfileScheduler.get_instance()
    status = scheduler.get_status()

    return AgentStatusResponse(
        running=status["running"],
        interval_hours=status["interval_hours"],
        next_run=status["next_run"],
        agent_is_running=status["agent_status"]["is_running"],
        agent_last_run=status["agent_status"]["last_run"]
    )


@router.post("/trigger")
async def trigger_maintenance() -> TriggerResponse:
    """Manually trigger profile maintenance"""
    scheduler = ProfileScheduler.get_instance()

    try:
        result = await scheduler.trigger_now()

        return TriggerResponse(
            success=result.get("success", False),
            task_id=result.get("task_id"),
            trigger=result.get("trigger"),
            work_type=result.get("work_type"),
            summary=result.get("summary"),
            files_modified=result.get("files_modified", []),
            error=result.get("error"),
            response=result.get("response")
        )

    except Exception as e:
        logger.error(f"Failed to trigger profile maintenance: {e}")
        return TriggerResponse(
            success=False,
            task_id=None,
            error=str(e)
        )


@router.get("/history")
async def get_task_history(
    limit: int = Query(20, ge=1, le=100)
) -> List[TaskResponse]:
    """Get profile agent task history"""
    scheduler = ProfileScheduler.get_instance()

    try:
        tasks = await scheduler.get_task_history(limit)

        return [
            TaskResponse(
                id=task["id"],
                trigger=task["trigger"],
                work_type=task.get("work_type"),
                summary=task.get("summary"),
                files_modified=task.get("files_modified", []),
                created_at=task.get("created_at"),
                completed_at=task.get("completed_at"),
                status=task["status"]
            )
            for task in tasks
        ]

    except Exception as e:
        logger.error(f"Failed to get task history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_scheduler() -> dict:
    """Start the profile scheduler"""
    scheduler = ProfileScheduler.get_instance()
    await scheduler.start()
    return {"success": True, "message": "Profile scheduler started"}


@router.post("/stop")
async def stop_scheduler() -> dict:
    """Stop the profile scheduler"""
    scheduler = ProfileScheduler.get_instance()
    await scheduler.stop()
    return {"success": True, "message": "Profile scheduler stopped"}
