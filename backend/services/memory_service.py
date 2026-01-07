"""
Memory Service for managing episodic and semantic memories
Uses the new agent-based architecture for memory generation
"""
import asyncio
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from config.settings import settings
from storage.database import Database
from storage.vector_store import VectorStore
from .llm_service import LLMService


class MemoryService:
    """Service for memory processing and retrieval"""

    _instance: Optional["MemoryService"] = None

    def __init__(self):
        self._memory_manager = None  # Lazy initialization

    @classmethod
    def get_instance(cls) -> "MemoryService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_memory_manager(self):
        """Get or create the memory manager (lazy initialization)"""
        if self._memory_manager is None:
            from agents.memory_manager import MemoryManager
            self._memory_manager = MemoryManager.get_instance()
        return self._memory_manager

    async def add_to_batch(self, message: Dict[str, Any]) -> None:
        """Add a message to the processing batch"""
        # Save the message to database first
        db = Database.get_instance()
        message_id = message.get('id') or str(uuid.uuid4())
        message['id'] = message_id

        await db.save_message(message)

        # Then queue for memory processing
        manager = self._get_memory_manager()
        await manager.on_new_message(message_id)

    async def process_batch(self) -> None:
        """Process accumulated messages to extract memories"""
        manager = self._get_memory_manager()
        await manager.process_batch()

    async def flush_batch(self) -> None:
        """Force process all pending messages"""
        manager = self._get_memory_manager()
        await manager.flush_batch()

    async def on_screenshot_captured(self, screenshot: Dict[str, Any]) -> None:
        """Handle a screenshot being captured"""
        manager = self._get_memory_manager()
        await manager.on_screenshot_captured(screenshot)

    def get_batch_status(self) -> Dict[str, Any]:
        """Get current batch processing status"""
        manager = self._get_memory_manager()
        return manager.get_batch_status()

    async def search_memories(
        self,
        query: str,
        limit: int = 10,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search memories using semantic similarity"""
        llm = LLMService.get_instance()
        vector_store = VectorStore.get_instance()

        if not llm.is_configured():
            # Fallback to text search
            db = Database.get_instance()
            return await db.search_episodic_memories(query, limit)

        try:
            # Generate query embedding
            query_embedding = await llm.embed_single(query)

            # Build filter
            where_filter = None
            if memory_type:
                where_filter = {"type": memory_type}

            # Query vector store
            results = vector_store.query(
                query_embedding=query_embedding,
                n_results=limit,
                where=where_filter
            )

            # Format results
            memories = []
            if results["ids"] and results["ids"][0]:
                for i, id in enumerate(results["ids"][0]):
                    memories.append({
                        "id": id,
                        "content": results["documents"][0][i] if results["documents"] else "",
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0
                    })

            return memories

        except Exception as e:
            print(f"Memory search error: {e}")
            # Fallback to text search
            db = Database.get_instance()
            return await db.search_episodic_memories(query, limit)

    async def get_episodic_memories(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get episodic memories from database"""
        db = Database.get_instance()
        return await db.get_episodic_memories(limit, offset)

    async def get_semantic_memories(
        self,
        memory_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get semantic memories from database"""
        db = Database.get_instance()
        return await db.get_semantic_memories(memory_type, limit)

    async def get_memory_context(
        self,
        query: str,
        max_tokens: int = 2000
    ) -> str:
        """Get relevant memory context for a query"""
        memories = await self.search_memories(query, limit=5)

        if not memories:
            return ""

        context_parts = []
        total_length = 0

        for mem in memories:
            content = mem.get("content", "")
            metadata = mem.get("metadata", {})
            mem_type = metadata.get("type", "unknown")

            entry = f"[{mem_type}] {content}"

            if total_length + len(entry) > max_tokens:
                break

            context_parts.append(entry)
            total_length += len(entry)

        return "\n".join(context_parts)

    async def delete_memory(self, memory_id: str, memory_type: str) -> bool:
        """Delete a memory by ID"""
        db = Database.get_instance()
        vector_store = VectorStore.get_instance()

        try:
            # Delete from vector store
            vector_store.delete([memory_id])

            # Delete from database (would need to add delete methods)
            # For now, just remove from vector store
            return True
        except Exception as e:
            print(f"Delete memory error: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        db = Database.get_instance()
        vector_store = VectorStore.get_instance()

        db_stats = await db.get_stats()
        vector_count = vector_store.count()

        manager = self._get_memory_manager()
        batch_status = manager.get_batch_status()

        return {
            **db_stats,
            "vector_embeddings": vector_count,
            "pending_batch": batch_status.get("queue_size", 0)
        }

    async def get_episodic_memories_since(
        self,
        since_timestamp: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get episodic memories created after a timestamp for incremental loading"""
        db = Database.get_instance()
        return await db.get_episodic_memories_since(since_timestamp, limit)

    async def get_semantic_memories_since(
        self,
        since_timestamp: int,
        memory_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get semantic memories created after a timestamp for incremental loading"""
        db = Database.get_instance()
        return await db.get_semantic_memories_since(since_timestamp, memory_type, limit)
