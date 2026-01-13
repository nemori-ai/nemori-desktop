"""
SQLite Database Service for Nemori Backend
"""
import sqlite3
import json
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
import aiosqlite
import asyncio

from config.settings import settings


class Database:
    """Async SQLite database manager"""

    _instance: Optional["Database"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.db_path = settings.db_path
        self._connection: Optional[aiosqlite.Connection] = None

    @classmethod
    def get_instance(cls) -> "Database":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def initialize(self) -> None:
        """Initialize database connection and create tables"""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrent access
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")

        await self._create_tables()
        await self._connection.commit()

    async def _create_tables(self) -> None:
        """Create all necessary tables"""
        # Screenshots table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS screenshots (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                window_title TEXT,
                app_name TEXT,
                url TEXT,
                phash TEXT,
                processed INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_screenshots_timestamp ON screenshots(timestamp)"
        )
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_screenshots_phash ON screenshots(phash)"
        )

        # Messages table (supports chat, capture, clipboard roles)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'capture', 'clipboard')),
                content TEXT,
                timestamp INTEGER NOT NULL,
                conversation_id TEXT,
                screenshot_id TEXT,
                url TEXT,
                title TEXT,
                source TEXT,
                metadata TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)"
        )
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)"
        )

        # Conversations table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)

        # Episodic memories table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                participants TEXT,
                urls TEXT,
                screenshot_ids TEXT,
                event_ids TEXT,
                embedding_id TEXT,
                source_app TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodic_time ON episodic_memories(start_time, end_time)"
        )

        # Semantic memories table (8 life categories)
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS semantic_memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL CHECK(type IN ('knowledge', 'preference', 'career', 'finance', 'health', 'family', 'social', 'growth', 'leisure', 'spirit')),
                content TEXT NOT NULL,
                context TEXT,
                source_summary TEXT,
                source_message_ids TEXT,
                related_memory_ids TEXT,
                confidence REAL DEFAULT 0.5,
                embedding_id TEXT,
                source_app TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_type ON semantic_memories(type)"
        )

        # Settings table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)

        # Memory batches table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS memory_batches (
                id TEXT PRIMARY KEY,
                message_ids TEXT NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)

        # Agent sessions table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'idle',
                current_step INTEGER DEFAULT 0,
                max_steps INTEGER DEFAULT 10,
                config TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                started_at INTEGER,
                completed_at INTEGER
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_sessions_conversation ON agent_sessions(conversation_id)"
        )

        # Tool calls table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                step INTEGER NOT NULL,
                tool_name TEXT NOT NULL,
                tool_args TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                error TEXT,
                started_at INTEGER,
                completed_at INTEGER,
                duration_ms INTEGER,
                FOREIGN KEY (session_id) REFERENCES agent_sessions(id)
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id)"
        )

        # Agent messages table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS agent_messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                thinking TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES agent_sessions(id)
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_messages_session ON agent_messages(session_id)"
        )

        # Proactive agent state table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS proactive_agent_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT NOT NULL DEFAULT 'sleeping',
                last_wakeup INTEGER,
                last_sleep INTEGER,
                tasks_completed_today INTEGER DEFAULT 0,
                last_daily_reset INTEGER,
                config TEXT,
                updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)

        # Proactive tasks table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS proactive_tasks (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                scheduled_time INTEGER,
                recurring INTEGER DEFAULT 0,
                recurrence_interval_seconds INTEGER,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'scheduled', 'in_progress', 'completed', 'failed', 'cancelled')),
                target_file TEXT,
                context TEXT,
                result TEXT,
                error TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
                started_at INTEGER,
                completed_at INTEGER,
                execution_time_ms INTEGER
            )
        """)
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_proactive_tasks_status ON proactive_tasks(status)"
        )
        await self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_proactive_tasks_scheduled ON proactive_tasks(scheduled_time)"
        )

        # Wakeup triggers table
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS wakeup_triggers (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                scheduled_time INTEGER,
                interval_seconds INTEGER,
                last_triggered INTEGER,
                priority INTEGER DEFAULT 5,
                reason TEXT,
                metadata TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
            )
        """)

    def is_connected(self) -> bool:
        return self._connection is not None

    async def close(self) -> None:
        """Close database connection with proper WAL checkpoint"""
        if self._connection:
            try:
                # Force WAL checkpoint to ensure all changes are written to main database
                await self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                await self._connection.commit()
                print("Database: WAL checkpoint completed")
            except Exception as e:
                print(f"Database: WAL checkpoint failed (non-critical): {e}")
            finally:
                await self._connection.close()
                self._connection = None
                print("Database: Connection closed")

    # ==================== Screenshot Operations ====================

    async def save_screenshot(self, screenshot: Dict[str, Any]) -> None:
        async with self._lock:
            await self._connection.execute(
                """
                INSERT OR REPLACE INTO screenshots
                (id, timestamp, file_path, window_title, app_name, url, phash, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    screenshot["id"],
                    screenshot["timestamp"],
                    screenshot["file_path"],
                    screenshot.get("window_title"),
                    screenshot.get("app_name"),
                    screenshot.get("url"),
                    screenshot.get("phash"),
                    1 if screenshot.get("processed") else 0,
                ),
            )
            await self._connection.commit()

    async def get_screenshots(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM screenshots ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_screenshot_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM screenshots WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_screenshot(self, id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_screenshot_by_id"""
        return await self.get_screenshot_by_id(id)

    async def find_similar_screenshot(self, phash: str) -> Optional[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM screenshots WHERE phash = ? LIMIT 1", (phash,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def delete_screenshot(self, id: str) -> None:
        async with self._lock:
            await self._connection.execute(
                "DELETE FROM screenshots WHERE id = ?", (id,)
            )
            await self._connection.commit()

    async def get_screenshots_by_date(
        self, date_str: str, limit: int = 500, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get screenshots for a specific date (YYYY-MM-DD format) with pagination"""
        # Convert date string to timestamp range (start and end of day in milliseconds)
        from datetime import datetime
        date = datetime.strptime(date_str, "%Y-%m-%d")
        start_ts = int(date.timestamp() * 1000)
        end_ts = start_ts + 24 * 60 * 60 * 1000  # Add 24 hours

        cursor = await self._connection.execute(
            """SELECT * FROM screenshots
               WHERE timestamp >= ? AND timestamp < ?
               ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            (start_ts, end_ts, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_screenshot_count_by_date(self, date_str: str) -> int:
        """Get total count of screenshots for a specific date"""
        from datetime import datetime
        date = datetime.strptime(date_str, "%Y-%m-%d")
        start_ts = int(date.timestamp() * 1000)
        end_ts = start_ts + 24 * 60 * 60 * 1000

        cursor = await self._connection.execute(
            """SELECT COUNT(*) as count FROM screenshots
               WHERE timestamp >= ? AND timestamp < ?""",
            (start_ts, end_ts),
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0

    async def get_screenshot_dates(self) -> List[str]:
        """Get list of dates that have screenshots (YYYY-MM-DD format)"""
        cursor = await self._connection.execute(
            """SELECT DISTINCT date(timestamp/1000, 'unixepoch', 'localtime') as date
               FROM screenshots
               ORDER BY date DESC"""
        )
        rows = await cursor.fetchall()
        return [row["date"] for row in rows if row["date"]]

    # ==================== Message Operations ====================

    async def save_message(self, message: Dict[str, Any]) -> None:
        async with self._lock:
            await self._connection.execute(
                """
                INSERT OR REPLACE INTO messages
                (id, role, content, timestamp, conversation_id, screenshot_id, url, title, source, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["id"],
                    message["role"],
                    message.get("content"),
                    message["timestamp"],
                    message.get("conversation_id"),
                    message.get("screenshot_id"),
                    message.get("url"),
                    message.get("title"),
                    message.get("source"),
                    json.dumps(message.get("metadata")) if message.get("metadata") else None,
                ),
            )
            await self._connection.commit()

    async def get_messages_by_ids(self, ids: List[str]) -> List[Dict[str, Any]]:
        """Get multiple messages by their IDs"""
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        cursor = await self._connection.execute(
            f"SELECT * FROM messages WHERE id IN ({placeholders})",
            ids
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_messages(
        self, conversation_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        cursor = await self._connection.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (conversation_id, limit),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            msg = dict(row)
            # Parse metadata JSON
            if msg.get('metadata') and isinstance(msg['metadata'], str):
                try:
                    msg['metadata'] = json.loads(msg['metadata'])
                except:
                    pass
            results.append(msg)
        return results

    async def get_recent_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== Conversation Operations ====================

    async def create_conversation(self, id: str, title: Optional[str] = None) -> None:
        async with self._lock:
            now = int(time.time() * 1000)
            await self._connection.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (id, title or "New Conversation", now, now),
            )
            await self._connection.commit()

    async def get_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_conversation(self, id: str, title: str) -> None:
        async with self._lock:
            now = int(time.time() * 1000)
            await self._connection.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, id),
            )
            await self._connection.commit()

    async def delete_conversation(self, id: str) -> None:
        async with self._lock:
            await self._connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (id,)
            )
            await self._connection.execute(
                "DELETE FROM conversations WHERE id = ?", (id,)
            )
            await self._connection.commit()

    # ==================== Episodic Memory Operations ====================

    async def save_episodic_memory(self, memory: Dict[str, Any]) -> None:
        async with self._lock:
            await self._connection.execute(
                """
                INSERT OR REPLACE INTO episodic_memories
                (id, title, content, start_time, end_time, participants, urls, screenshot_ids, event_ids, embedding_id, source_app, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory["id"],
                    memory["title"],
                    memory["content"],
                    memory["start_time"],
                    memory["end_time"],
                    json.dumps(memory.get("participants")) if memory.get("participants") else None,
                    json.dumps(memory.get("urls")) if memory.get("urls") else None,
                    json.dumps(memory.get("screenshot_ids")) if memory.get("screenshot_ids") else None,
                    json.dumps(memory.get("event_ids")) if memory.get("event_ids") else None,
                    memory.get("embedding_id"),
                    json.dumps(memory.get("source_app")) if memory.get("source_app") else None,
                    memory.get("created_at", int(time.time() * 1000)),
                ),
            )
            await self._connection.commit()

    async def get_episodic_memories(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        cursor = await self._connection.execute(
            "SELECT * FROM episodic_memories ORDER BY start_time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Parse JSON fields
            for field in ['participants', 'urls', 'screenshot_ids', 'event_ids', 'source_app']:
                if result.get(field) and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except:
                        pass
            results.append(result)
        return results

    async def search_episodic_memories(
        self, query: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        pattern = f"%{query}%"
        cursor = await self._connection.execute(
            """
            SELECT * FROM episodic_memories
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY start_time DESC LIMIT ?
            """,
            (pattern, pattern, limit),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            # Parse JSON fields
            for field in ['participants', 'urls', 'screenshot_ids', 'event_ids', 'source_app']:
                if result.get(field) and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except:
                        pass
            results.append(result)
        return results

    async def get_episodic_memory(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a single episodic memory by ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM episodic_memories WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            # Parse JSON fields
            for field in ['participants', 'urls', 'screenshot_ids', 'event_ids', 'source_app']:
                if result.get(field) and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except:
                        pass
            return result
        return None

    async def delete_episodic_memory(self, id: str) -> None:
        """Delete an episodic memory by ID"""
        async with self._lock:
            await self._connection.execute(
                "DELETE FROM episodic_memories WHERE id = ?", (id,)
            )
            await self._connection.commit()

    # ==================== Semantic Memory Operations ====================

    async def save_semantic_memory(self, memory: Dict[str, Any]) -> None:
        async with self._lock:
            await self._connection.execute(
                """
                INSERT OR REPLACE INTO semantic_memories
                (id, type, content, context, source_summary, source_message_ids, related_memory_ids, confidence, embedding_id, source_app, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory["id"],
                    memory["type"],
                    memory["content"],
                    memory.get("context"),
                    memory.get("source_summary"),
                    json.dumps(memory.get("source_message_ids")) if memory.get("source_message_ids") else None,
                    json.dumps(memory.get("related_memory_ids")) if memory.get("related_memory_ids") else None,
                    memory.get("confidence", 0.5),
                    memory.get("embedding_id"),
                    json.dumps(memory.get("source_app")) if memory.get("source_app") else None,
                    memory.get("created_at", int(time.time() * 1000)),
                ),
            )
            await self._connection.commit()

    async def get_semantic_memories(
        self, type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        if type:
            cursor = await self._connection.execute(
                "SELECT * FROM semantic_memories WHERE type = ? ORDER BY created_at DESC LIMIT ?",
                (type, limit),
            )
        else:
            cursor = await self._connection.execute(
                "SELECT * FROM semantic_memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_semantic_memory(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a single semantic memory by ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM semantic_memories WHERE id = ?", (id,)
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            # Parse JSON fields
            for field in ['source_message_ids', 'related_memory_ids', 'source_app']:
                if result.get(field) and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except:
                        pass
            return result
        return None

    async def delete_semantic_memory(self, id: str) -> None:
        """Delete a semantic memory by ID"""
        async with self._lock:
            await self._connection.execute(
                "DELETE FROM semantic_memories WHERE id = ?", (id,)
            )
            await self._connection.commit()

    # ==================== Settings Operations ====================

    async def get_setting(self, key: str) -> Optional[str]:
        cursor = await self._connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        async with self._lock:
            now = int(time.time() * 1000)
            await self._connection.execute(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, now),
            )
            await self._connection.commit()

    async def get_all_settings(self) -> Dict[str, str]:
        cursor = await self._connection.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}

    # ==================== Statistics ====================

    async def get_stats(self) -> Dict[str, int]:
        stats = {}

        for table in ["screenshots", "messages", "episodic_memories", "semantic_memories", "conversations"]:
            cursor = await self._connection.execute(f"SELECT COUNT(*) as count FROM {table}")
            row = await cursor.fetchone()
            stats[f"{table}_count"] = row["count"]

        return stats

    # ==================== Incremental Query Operations ====================

    async def get_screenshots_since(
        self, since_timestamp: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get screenshots created after a timestamp for incremental loading"""
        cursor = await self._connection.execute(
            "SELECT * FROM screenshots WHERE created_at > ? ORDER BY timestamp DESC LIMIT ?",
            (since_timestamp, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_screenshots_count(self) -> int:
        """Get total count of screenshots for pagination"""
        cursor = await self._connection.execute("SELECT COUNT(*) as count FROM screenshots")
        row = await cursor.fetchone()
        return row["count"]

    async def get_screenshots_paginated(
        self, page: int = 1, page_size: int = 50
    ) -> Dict[str, Any]:
        """Get paginated screenshots with total count"""
        offset = (page - 1) * page_size
        total = await self.get_screenshots_count()

        cursor = await self._connection.execute(
            "SELECT * FROM screenshots ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )
        rows = await cursor.fetchall()

        return {
            "items": [dict(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    async def get_episodic_memories_since(
        self, since_timestamp: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get episodic memories created after a timestamp for incremental loading"""
        cursor = await self._connection.execute(
            "SELECT * FROM episodic_memories WHERE created_at > ? ORDER BY start_time DESC LIMIT ?",
            (since_timestamp, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_semantic_memories_since(
        self, since_timestamp: int, type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get semantic memories created after a timestamp for incremental loading"""
        if type:
            cursor = await self._connection.execute(
                "SELECT * FROM semantic_memories WHERE created_at > ? AND type = ? ORDER BY created_at DESC LIMIT ?",
                (since_timestamp, type, limit),
            )
        else:
            cursor = await self._connection.execute(
                "SELECT * FROM semantic_memories WHERE created_at > ? ORDER BY created_at DESC LIMIT ?",
                (since_timestamp, limit),
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_messages_since(
        self, since_timestamp: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get messages created after a timestamp for incremental loading"""
        cursor = await self._connection.execute(
            "SELECT * FROM messages WHERE created_at > ? ORDER BY timestamp DESC LIMIT ?",
            (since_timestamp, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # ==================== Proactive Agent Operations ====================

    async def get_proactive_agent_state(self) -> Optional[Dict[str, Any]]:
        """Get the proactive agent's persisted state"""
        cursor = await self._connection.execute(
            "SELECT * FROM proactive_agent_state WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            if result.get('config') and isinstance(result['config'], str):
                try:
                    result['config'] = json.loads(result['config'])
                except:
                    pass
            return result
        return None

    async def save_proactive_agent_state(self, state: Dict[str, Any]) -> None:
        """Save the proactive agent's state"""
        async with self._lock:
            now = int(time.time() * 1000)
            config_json = json.dumps(state.get('config')) if state.get('config') else None

            await self._connection.execute(
                """
                INSERT OR REPLACE INTO proactive_agent_state
                (id, state, last_wakeup, last_sleep, tasks_completed_today, last_daily_reset, config, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state.get('state', 'sleeping'),
                    state.get('last_wakeup'),
                    state.get('last_sleep'),
                    state.get('tasks_completed_today', 0),
                    state.get('last_daily_reset'),
                    config_json,
                    now,
                ),
            )
            await self._connection.commit()

    async def save_proactive_task(self, task: Dict[str, Any]) -> None:
        """Save a proactive task"""
        async with self._lock:
            context_json = json.dumps(task.get('context')) if task.get('context') else None

            await self._connection.execute(
                """
                INSERT OR REPLACE INTO proactive_tasks
                (id, type, title, description, scheduled_time, recurring, recurrence_interval_seconds,
                 priority, status, target_file, context, result, error, created_at, started_at, completed_at, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task['id'],
                    task['type'],
                    task['title'],
                    task.get('description'),
                    task.get('scheduled_time'),
                    1 if task.get('recurring') else 0,
                    task.get('recurrence_interval_seconds'),
                    task.get('priority', 5),
                    task.get('status', 'pending'),
                    task.get('target_file'),
                    context_json,
                    task.get('result'),
                    task.get('error'),
                    task.get('created_at', int(time.time() * 1000)),
                    task.get('started_at'),
                    task.get('completed_at'),
                    task.get('execution_time_ms'),
                ),
            )
            await self._connection.commit()

    async def get_proactive_tasks(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get proactive tasks, optionally filtered by status"""
        if status:
            cursor = await self._connection.execute(
                "SELECT * FROM proactive_tasks WHERE status = ? ORDER BY priority DESC, scheduled_time ASC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await self._connection.execute(
                "SELECT * FROM proactive_tasks ORDER BY priority DESC, scheduled_time ASC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('context') and isinstance(result['context'], str):
                try:
                    result['context'] = json.loads(result['context'])
                except:
                    pass
            results.append(result)
        return results

    async def get_proactive_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single proactive task by ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM proactive_tasks WHERE id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            if result.get('context') and isinstance(result['context'], str):
                try:
                    result['context'] = json.loads(result['context'])
                except:
                    pass
            return result
        return None

    async def update_proactive_task_status(
        self, task_id: str, status: str, result: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """Update a proactive task's status"""
        async with self._lock:
            now = int(time.time() * 1000)

            if status == 'in_progress':
                await self._connection.execute(
                    "UPDATE proactive_tasks SET status = ?, started_at = ? WHERE id = ?",
                    (status, now, task_id),
                )
            elif status in ('completed', 'failed', 'cancelled'):
                # Get started_at for execution time calculation
                cursor = await self._connection.execute(
                    "SELECT started_at FROM proactive_tasks WHERE id = ?", (task_id,)
                )
                row = await cursor.fetchone()
                execution_time = None
                if row and row['started_at']:
                    execution_time = now - row['started_at']

                await self._connection.execute(
                    """UPDATE proactive_tasks
                       SET status = ?, result = ?, error = ?, completed_at = ?, execution_time_ms = ?
                       WHERE id = ?""",
                    (status, result, error, now, execution_time, task_id),
                )
            else:
                await self._connection.execute(
                    "UPDATE proactive_tasks SET status = ? WHERE id = ?",
                    (status, task_id),
                )
            await self._connection.commit()

    async def delete_proactive_task(self, task_id: str) -> None:
        """Delete a proactive task"""
        async with self._lock:
            await self._connection.execute(
                "DELETE FROM proactive_tasks WHERE id = ?", (task_id,)
            )
            await self._connection.commit()

    async def get_pending_proactive_tasks(self) -> List[Dict[str, Any]]:
        """Get pending proactive tasks that are due"""
        now = int(time.time() * 1000)
        cursor = await self._connection.execute(
            """SELECT * FROM proactive_tasks
               WHERE status IN ('pending', 'scheduled')
               AND (scheduled_time IS NULL OR scheduled_time <= ?)
               ORDER BY priority DESC, scheduled_time ASC""",
            (now,),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('context') and isinstance(result['context'], str):
                try:
                    result['context'] = json.loads(result['context'])
                except:
                    pass
            results.append(result)
        return results

    # ==================== Wakeup Trigger Operations ====================

    async def save_wakeup_trigger(self, trigger: Dict[str, Any]) -> None:
        """Save a wakeup trigger"""
        async with self._lock:
            metadata_json = json.dumps(trigger.get('metadata')) if trigger.get('metadata') else None

            await self._connection.execute(
                """
                INSERT OR REPLACE INTO wakeup_triggers
                (id, type, name, enabled, scheduled_time, interval_seconds, last_triggered, priority, reason, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trigger['id'],
                    trigger['type'],
                    trigger['name'],
                    1 if trigger.get('enabled', True) else 0,
                    trigger.get('scheduled_time'),
                    trigger.get('interval_seconds'),
                    trigger.get('last_triggered'),
                    trigger.get('priority', 5),
                    trigger.get('reason'),
                    metadata_json,
                ),
            )
            await self._connection.commit()

    async def get_wakeup_triggers(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """Get wakeup triggers"""
        if enabled_only:
            cursor = await self._connection.execute(
                "SELECT * FROM wakeup_triggers WHERE enabled = 1 ORDER BY priority DESC"
            )
        else:
            cursor = await self._connection.execute(
                "SELECT * FROM wakeup_triggers ORDER BY priority DESC"
            )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('metadata') and isinstance(result['metadata'], str):
                try:
                    result['metadata'] = json.loads(result['metadata'])
                except:
                    pass
            results.append(result)
        return results

    async def update_wakeup_trigger(self, trigger_id: str, updates: Dict[str, Any]) -> None:
        """Update a wakeup trigger"""
        async with self._lock:
            # Build update query dynamically
            set_clauses = []
            values = []

            for key, value in updates.items():
                if key in ('enabled', 'scheduled_time', 'interval_seconds', 'last_triggered', 'priority', 'reason'):
                    set_clauses.append(f"{key} = ?")
                    if key == 'enabled':
                        values.append(1 if value else 0)
                    else:
                        values.append(value)
                elif key == 'metadata':
                    set_clauses.append("metadata = ?")
                    values.append(json.dumps(value) if value else None)

            if set_clauses:
                values.append(trigger_id)
                query = f"UPDATE wakeup_triggers SET {', '.join(set_clauses)} WHERE id = ?"
                await self._connection.execute(query, values)
                await self._connection.commit()

    async def delete_wakeup_trigger(self, trigger_id: str) -> None:
        """Delete a wakeup trigger"""
        async with self._lock:
            await self._connection.execute(
                "DELETE FROM wakeup_triggers WHERE id = ?", (trigger_id,)
            )
            await self._connection.commit()
