"""
Profile Agent - Simplified automated profile maintenance agent

This agent runs periodically (every 6 hours) or on-demand to:
- Analyze recent conversations
- Choose a topic to update or expand in the user profile
- Track task history to avoid repetition

Unlike the complex calendar system, this is a simple, focused agent
that does ONE thing per execution.
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from services.llm_service import LLMService
from services.profile_manager import ProfileManager
from storage.database import Database
from agents.executor import AgentExecutor
from agents.tools import get_all_tools
from prompts.profile_agent_prompts import get_profile_agent_prompt

logger = logging.getLogger(__name__)


class ProfileAgent:
    """
    Automated profile maintenance agent.

    Capabilities (same as chat agent):
    - Search memories (episodic, semantic, chat history)
    - View and edit all profile files
    - Create new profile topics

    Execution:
    - Triggered every 6 hours automatically
    - Can be triggered manually by user (unlimited)
    - Does ONE thing per execution
    - Tracks history to avoid repetition
    """

    _instance: Optional["ProfileAgent"] = None
    HISTORY_LIMIT = 5  # Number of recent tasks to show for avoiding repetition

    def __init__(self):
        self._llm: Optional[LLMService] = None
        self._db: Optional[Database] = None
        self._profile_manager: Optional[ProfileManager] = None
        self._initialized = False
        self._last_run: Optional[datetime] = None
        self._is_running = False

    @classmethod
    def get_instance(cls) -> "ProfileAgent":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """Initialize the agent with required services."""
        if self._initialized:
            return

        self._llm = LLMService.get_instance()
        self._db = Database.get_instance()
        self._profile_manager = ProfileManager.get_instance()
        await self._profile_manager.initialize()

        # Ensure task history table exists
        await self._ensure_tables()

        self._initialized = True
        logger.info("ProfileAgent initialized")

    async def _ensure_tables(self) -> None:
        """Ensure the task history table exists."""
        async with self._db._lock:
            await self._db._connection.execute("""
                CREATE TABLE IF NOT EXISTS profile_agent_tasks (
                    id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    work_type TEXT,
                    summary TEXT,
                    files_modified TEXT,
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    status TEXT NOT NULL DEFAULT 'running'
                )
            """)
            await self._db._connection.commit()

    async def run(self, trigger: str = "auto") -> Dict[str, Any]:
        """
        Execute one profile maintenance task.

        Args:
            trigger: "auto" for scheduled runs, "manual" for user-triggered

        Returns:
            Dict with task results
        """
        if not self._initialized:
            await self.initialize()

        if self._is_running:
            return {
                "success": False,
                "error": "Profile agent is already running",
                "task_id": None
            }

        self._is_running = True
        task_id = f"pa_{uuid.uuid4().hex[:12]}"
        created_at = int(datetime.now().timestamp() * 1000)

        try:
            # Record task start
            await self._save_task(task_id, trigger, created_at, "running")

            # Get context for the agent
            recent_tasks = await self._get_recent_tasks()
            profile_status = await self._get_profile_status()

            # Build system prompt
            language = self._llm.language if self._llm else "en"
            system_prompt = get_profile_agent_prompt(
                recent_tasks=recent_tasks,
                profile_status=profile_status,
                language=language
            )

            # Create agent executor with all tools
            tools = get_all_tools(include_proactive=False)
            executor = AgentExecutor(max_steps=15, tools=tools)

            # Override system prompt
            original_build = executor._build_system_prompt
            executor._build_system_prompt = lambda: system_prompt

            # Run the agent
            user_prompt = self._get_trigger_prompt(trigger, language)
            response = await executor.execute(user_prompt)

            # Parse and save results
            work_type, summary, files_modified = self._parse_response(response)

            await self._update_task(
                task_id,
                status="completed",
                work_type=work_type,
                summary=summary,
                files_modified=files_modified
            )

            self._last_run = datetime.now()
            logger.info(f"ProfileAgent task completed: {task_id}")

            # Parse files_modified from JSON string to list
            try:
                files_list = json.loads(files_modified) if files_modified else []
            except:
                files_list = []

            return {
                "success": True,
                "task_id": task_id,
                "trigger": trigger,
                "work_type": work_type,
                "summary": summary,
                "files_modified": files_list,
                "response": response
            }

        except Exception as e:
            logger.error(f"ProfileAgent task failed: {e}")
            await self._update_task(task_id, status="failed", summary=str(e))
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e)
            }
        finally:
            self._is_running = False

    def _get_trigger_prompt(self, trigger: str, language: str) -> str:
        """Get the user prompt based on trigger type."""
        if language == "zh":
            if trigger == "manual":
                return "用户主动触发了档案维护。请分析最近的对话，选择一个有价值的方向来更新用户档案。"
            else:
                return "定时档案维护任务启动。请分析最近的对话，选择一个有价值的方向来更新用户档案。"
        else:
            if trigger == "manual":
                return "User triggered profile maintenance. Please analyze recent conversations and choose a valuable direction to update the user profile."
            else:
                return "Scheduled profile maintenance task started. Please analyze recent conversations and choose a valuable direction to update the user profile."

    async def _get_recent_tasks(self) -> str:
        """Get recent task history formatted as string."""
        try:
            async with self._db._lock:
                cursor = await self._db._connection.execute("""
                    SELECT work_type, summary, files_modified, created_at
                    FROM profile_agent_tasks
                    WHERE status = 'completed'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (self.HISTORY_LIMIT,))
                rows = await cursor.fetchall()

            if not rows:
                return "(No previous tasks)"

            lines = []
            for row in rows:
                work_type = row[0] or "Unknown"
                summary = row[1] or "No summary"
                files = row[2] or "[]"
                timestamp = datetime.fromtimestamp(row[3] / 1000).strftime("%Y-%m-%d %H:%M")

                # Truncate summary if too long
                if len(summary) > 100:
                    summary = summary[:100] + "..."

                lines.append(f"- [{timestamp}] {work_type}: {summary}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to get recent tasks: {e}")
            return "(Error loading task history)"

    async def _get_profile_status(self) -> str:
        """Get current profile files summary."""
        try:
            files = await self._profile_manager.list_files(include_topics=True)

            if not files:
                return "(No profile files yet)"

            lines = []
            for f in files[:15]:  # Limit to avoid token overflow
                lines.append(f"- {f.relative_path}: {f.title}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Failed to get profile status: {e}")
            return "(Error loading profile status)"

    def _parse_response(self, response: str) -> tuple:
        """Parse agent response to extract work type, summary, and files modified."""
        work_type = "unknown"
        summary = response[:500] if response else "No response"
        files_modified = []

        # Try to extract work type from response
        response_lower = response.lower()
        if "extract" in response_lower or "new information" in response_lower or "补充" in response_lower:
            work_type = "extract_new"
        elif "deepen" in response_lower or "expand" in response_lower or "深化" in response_lower:
            work_type = "deepen_topic"
        elif "organize" in response_lower or "summarize" in response_lower or "整理" in response_lower:
            work_type = "organize"
        elif "update" in response_lower or "outdated" in response_lower or "修正" in response_lower:
            work_type = "update_outdated"
        elif "create" in response_lower or "new topic" in response_lower or "创建" in response_lower:
            work_type = "create_topic"
        elif "no update" in response_lower or "no meaningful" in response_lower or "无需" in response_lower:
            work_type = "no_update_needed"

        # Extract first sentence or paragraph as summary
        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:
                summary = line[:200]
                break

        return work_type, summary, json.dumps(files_modified)

    async def _save_task(self, task_id: str, trigger: str, created_at: int, status: str) -> None:
        """Save a new task record."""
        async with self._db._lock:
            await self._db._connection.execute("""
                INSERT INTO profile_agent_tasks (id, trigger, created_at, status)
                VALUES (?, ?, ?, ?)
            """, (task_id, trigger, created_at, status))
            await self._db._connection.commit()

    async def _update_task(
        self,
        task_id: str,
        status: str,
        work_type: str = None,
        summary: str = None,
        files_modified: str = None
    ) -> None:
        """Update task record with results."""
        completed_at = int(datetime.now().timestamp() * 1000)
        async with self._db._lock:
            await self._db._connection.execute("""
                UPDATE profile_agent_tasks
                SET status = ?, work_type = ?, summary = ?, files_modified = ?, completed_at = ?
                WHERE id = ?
            """, (status, work_type, summary, files_modified, completed_at, task_id))
            await self._db._connection.commit()

    async def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "initialized": self._initialized,
            "is_running": self._is_running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
        }

    async def get_task_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get task history."""
        try:
            async with self._db._lock:
                cursor = await self._db._connection.execute("""
                    SELECT id, trigger, work_type, summary, files_modified, created_at, completed_at, status
                    FROM profile_agent_tasks
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                rows = await cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "trigger": row[1],
                    "work_type": row[2],
                    "summary": row[3],
                    "files_modified": json.loads(row[4]) if row[4] else [],
                    "created_at": datetime.fromtimestamp(row[5] / 1000).isoformat() if row[5] else None,
                    "completed_at": datetime.fromtimestamp(row[6] / 1000).isoformat() if row[6] else None,
                    "status": row[7]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get task history: {e}")
            return []
