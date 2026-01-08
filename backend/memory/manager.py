"""
Memory Orchestrator - Coordinates batch processing and memory generation

Features:
- Persistent queue to protect against data loss on crash
- Batch processing with configurable size
- Orchestration of memory generation pipelines
"""

import asyncio
import json
from typing import Optional, List, Dict, Any

from storage.database import Database
from config.settings import settings
from .episodic import EpisodicProcessor
from .semantic import SemanticExtractor
from .segmentation import EventSegmenter


# Queue persistence key
QUEUE_PERSISTENCE_KEY = "memory_manager_queue"


class MemoryOrchestrator:
    """Orchestrates memory processing and pipeline coordination"""

    _instance: Optional["MemoryOrchestrator"] = None

    def __init__(self):
        self.db = Database.get_instance()
        self.episodic_processor = EpisodicProcessor()
        self.semantic_extractor = SemanticExtractor()
        self.event_segmenter = EventSegmenter()

        self._batch_queue: List[str] = []  # Message IDs waiting to be processed
        self._batch_size = settings.batch_size
        self._is_processing = False
        self._memory_enabled = True
        self._episodic_since_visualization = 0
        self._queue_loaded = False

    @classmethod
    def get_instance(cls) -> "MemoryOrchestrator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _load_persisted_queue(self) -> None:
        """Load the queue from database on first access"""
        if self._queue_loaded:
            return

        try:
            queue_json = await self.db.get_setting(QUEUE_PERSISTENCE_KEY)
            if queue_json:
                loaded_queue = json.loads(queue_json)
                if isinstance(loaded_queue, list):
                    self._batch_queue = loaded_queue
                    print(f"Loaded {len(self._batch_queue)} items from persisted queue")
        except Exception as e:
            print(f"Failed to load persisted queue: {e}")

        self._queue_loaded = True

    async def _persist_queue(self) -> None:
        """Save the queue to database for crash recovery"""
        try:
            queue_json = json.dumps(self._batch_queue)
            await self.db.set_setting(QUEUE_PERSISTENCE_KEY, queue_json)
        except Exception as e:
            print(f"Failed to persist queue: {e}")

    async def on_new_message(self, message_id: str) -> None:
        """Handle a new message being added"""
        try:
            if not self._memory_enabled:
                return

            # Load persisted queue if needed
            await self._load_persisted_queue()

            # Add to batch queue
            self._batch_queue.append(message_id)
            print(f"Message {message_id} added to batch queue (size: {len(self._batch_queue)})")

            # Persist queue after adding
            await self._persist_queue()

            # Check if we should process
            if len(self._batch_queue) >= self._batch_size:
                await self.process_batch()

        except Exception as e:
            print(f"Error handling new message: {e}")

    async def process_batch(self, force: bool = False) -> None:
        """Process accumulated messages to generate memories"""
        if self._is_processing:
            print("Already processing, skipping")
            return

        try:
            self._is_processing = True

            # Load persisted queue if needed
            await self._load_persisted_queue()

            # Get batch to process
            batch_size = min(len(self._batch_queue), self._batch_size)
            if batch_size == 0:
                return

            if batch_size < self._batch_size and not force:
                print(f"Batch size {batch_size} < {self._batch_size}, waiting for more messages")
                return

            # Get message IDs to process
            item_ids = self._batch_queue[:batch_size]

            print(f"Processing batch of {len(item_ids)} items with event segmenter")

            # Use event segmenter to analyze and segment the event sequence
            segmentations = await self.event_segmenter.analyze_event_sequence(item_ids)

            processed_count = 0

            for segmentation in segmentations:
                segment_size = segmentation.cut_position
                segment_ids = item_ids[processed_count:processed_count + segment_size]

                if segment_ids:
                    print(f"Creating episodic memory for segment of {len(segment_ids)} items: {segmentation.reason}")

                    # Create episodic memory
                    episodic_memory = await self.episodic_processor.create_from_messages(
                        segment_ids,
                        summary=segmentation.summary if segmentation.summary else None
                    )

                    if episodic_memory:
                        self._episodic_since_visualization += 1
                        print(f"Created episodic memory: {episodic_memory.get('title', 'Untitled')}")

                    # Create semantic memories from the same segment
                    try:
                        semantic_memories = await self.semantic_extractor.create_from_segment(
                            segment_ids,
                            summary=segmentation.summary,
                            top_n=5,
                            source_app=['nemori']
                        )
                        print(f"Created {len(semantic_memories)} semantic memories")
                    except Exception as e:
                        print(f"Semantic extractor failed: {e}")

                    processed_count += len(segment_ids)

                # For now, process only the first segmentation
                break

            # Remove processed items from queue
            self._batch_queue = self._batch_queue[processed_count:]
            print(f"Processed {processed_count} items, {len(self._batch_queue)} remaining in batch")

            # Persist updated queue
            await self._persist_queue()

        except Exception as e:
            print(f"Error processing batch: {e}")
        finally:
            self._is_processing = False

    async def flush_batch(self) -> None:
        """Force process all pending messages"""
        await self.process_batch(force=True)

    async def on_screenshot_captured(self, screenshot: Dict[str, Any]) -> None:
        """Handle a screenshot being captured"""
        try:
            if not self._memory_enabled:
                return

            # Create a capture message record
            import uuid
            from datetime import datetime

            capture_message = {
                'id': f"{screenshot['id']}-msg",
                'conversation_id': None,  # Not part of a conversation
                'timestamp': screenshot.get('timestamp', int(datetime.now().timestamp() * 1000)),
                'role': 'capture',
                'content': None,
                'screenshot_id': screenshot['id'],
                'url': screenshot.get('url', ''),
                'title': screenshot.get('title', ''),
                'source': screenshot.get('source', 'desktop')
            }

            # Save the message
            await self.db.save_message(capture_message)

            # Add to batch queue
            await self.on_new_message(capture_message['id'])

            print(f"Screenshot captured and queued for memory processing: {screenshot.get('title', 'Untitled')}")

        except Exception as e:
            print(f"Error handling screenshot capture: {e}")

    async def on_clipboard_action(
        self,
        action: str,
        text: str,
        url: str = "",
        title: str = ""
    ) -> None:
        """Handle clipboard copy/paste events"""
        try:
            if not self._memory_enabled:
                return

            import uuid
            from datetime import datetime

            clipboard_message = {
                'id': str(uuid.uuid4()),
                'conversation_id': None,
                'timestamp': int(datetime.now().timestamp() * 1000),
                'role': 'clipboard',
                'content': f"[{action.upper()}]: {text}",
                'url': url,
                'title': title
            }

            await self.db.save_message(clipboard_message)
            await self.on_new_message(clipboard_message['id'])

        except Exception as e:
            print(f"Error handling clipboard {action} event: {e}")

    def set_memory_enabled(self, enabled: bool) -> None:
        """Enable or disable memory processing"""
        self._memory_enabled = enabled
        print(f"Memory processing {'enabled' if enabled else 'disabled'}")

    async def get_batch_status_async(self) -> Dict[str, Any]:
        """Get current batch processing status (async version)"""
        await self._load_persisted_queue()
        return {
            'queue_size': len(self._batch_queue),
            'batch_size': self._batch_size,
            'is_processing': self._is_processing,
            'memory_enabled': self._memory_enabled,
            'episodic_count': self._episodic_since_visualization
        }

    def get_batch_status(self) -> Dict[str, Any]:
        """Get current batch processing status (sync version, may not reflect persisted queue on first call)"""
        return {
            'queue_size': len(self._batch_queue),
            'batch_size': self._batch_size,
            'is_processing': self._is_processing,
            'memory_enabled': self._memory_enabled,
            'episodic_count': self._episodic_since_visualization
        }

    async def recalculate_embedding(self, memory_id: str) -> None:
        """Recalculate embedding for an episodic memory"""
        memory = await self.db.get_episodic_memory(memory_id)
        if not memory:
            raise ValueError("Memory not found")

        embedding = await self.episodic_processor.generate_embedding(memory['content'])

        # Update in vector store
        from storage.vector_store import VectorStore
        vector_store = VectorStore.get_instance()
        vector_store.delete([memory_id])
        vector_store.add_embedding(
            id=memory_id,
            embedding=embedding,
            metadata={
                'type': 'episodic',
                'title': memory['title'],
                'created_at': memory['created_at']
            },
            document=memory['content']
        )

        print(f"Recalculated embedding for memory: {memory['title']}")


# Backward compatibility alias
MemoryManager = MemoryOrchestrator
