"""
Profile Scheduler - Simple scheduler for automated profile maintenance

Runs the Profile Agent every 6 hours automatically.
Much simpler than the complex calendar system it replaces.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .profile_agent import ProfileAgent

logger = logging.getLogger(__name__)


class ProfileScheduler:
    """
    Simple scheduler that triggers ProfileAgent every 6 hours.

    Features:
    - Automatic execution every INTERVAL_HOURS
    - Manual trigger support (unlimited)
    - Graceful start/stop
    """

    _instance: Optional["ProfileScheduler"] = None
    INTERVAL_HOURS = 6  # Run every 6 hours

    def __init__(self):
        self._agent: Optional[ProfileAgent] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._next_run: Optional[datetime] = None

    @classmethod
    def get_instance(cls) -> "ProfileScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """Initialize the scheduler with the profile agent."""
        self._agent = ProfileAgent.get_instance()
        await self._agent.initialize()
        logger.info("ProfileScheduler initialized")

    async def start(self) -> None:
        """Start the scheduler loop."""
        if self._running:
            logger.warning("ProfileScheduler is already running")
            return

        if not self._agent:
            await self.initialize()

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"ProfileScheduler started (interval: {self.INTERVAL_HOURS} hours)")

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self._next_run = None
        logger.info("ProfileScheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Calculate next run time
                self._next_run = datetime.now() + timedelta(hours=self.INTERVAL_HOURS)
                logger.info(f"Next profile maintenance scheduled at: {self._next_run}")

                # Wait for the interval
                await asyncio.sleep(self.INTERVAL_HOURS * 3600)

                if not self._running:
                    break

                # Run the profile agent
                logger.info("Triggering scheduled profile maintenance...")
                result = await self._agent.run(trigger="auto")

                if result.get("success"):
                    logger.info(f"Scheduled profile maintenance completed: {result.get('work_type')}")
                else:
                    logger.warning(f"Scheduled profile maintenance failed: {result.get('error')}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)

    async def trigger_now(self) -> dict:
        """
        Manually trigger the profile agent.

        Returns:
            Result from ProfileAgent.run()
        """
        if not self._agent:
            await self.initialize()

        logger.info("Manual profile maintenance triggered")
        return await self._agent.run(trigger="manual")

    def get_status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "interval_hours": self.INTERVAL_HOURS,
            "next_run": self._next_run.isoformat() if self._next_run else None,
            "agent_status": {
                "is_running": self._agent._is_running if self._agent else False,
                "last_run": self._agent._last_run.isoformat() if self._agent and self._agent._last_run else None
            }
        }

    async def get_task_history(self, limit: int = 20) -> list:
        """Get task history from the agent."""
        if not self._agent:
            await self.initialize()
        return await self._agent.get_task_history(limit)
