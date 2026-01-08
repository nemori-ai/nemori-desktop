"""
Memories API Routes
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.memory_service import MemoryService
from storage.database import Database

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    memory_type: Optional[str] = None


@router.get("/episodic")
async def get_episodic_memories(limit: int = 100, offset: int = 0):
    """Get episodic memories"""
    memory = MemoryService.get_instance()
    memories = await memory.get_episodic_memories(limit, offset)
    return {"memories": memories}


@router.get("/episodic/since/{since_timestamp}")
async def get_episodic_memories_since(since_timestamp: int, limit: int = 100):
    """Get episodic memories created after a timestamp for incremental loading"""
    memory = MemoryService.get_instance()
    memories = await memory.get_episodic_memories_since(since_timestamp, limit)
    return {"memories": memories, "since": since_timestamp}


@router.get("/semantic")
async def get_semantic_memories(
    type: Optional[str] = None,
    limit: int = 100
):
    """Get semantic memories"""
    memory = MemoryService.get_instance()
    memories = await memory.get_semantic_memories(type, limit)
    return {"memories": memories}


@router.get("/semantic/since/{since_timestamp}")
async def get_semantic_memories_since(
    since_timestamp: int,
    type: Optional[str] = None,
    limit: int = 100
):
    """Get semantic memories created after a timestamp for incremental loading"""
    memory = MemoryService.get_instance()
    memories = await memory.get_semantic_memories_since(since_timestamp, type, limit)
    return {"memories": memories, "since": since_timestamp}


@router.post("/search")
async def search_memories(request: SearchRequest):
    """Search memories using semantic similarity"""
    memory = MemoryService.get_instance()
    results = await memory.search_memories(
        request.query,
        request.limit,
        request.memory_type
    )
    return {"results": results}


@router.get("/search")
async def search_memories_get(
    query: str,
    limit: int = 10,
    type: Optional[str] = None
):
    """Search memories using GET request"""
    memory = MemoryService.get_instance()
    results = await memory.search_memories(query, limit, type)
    return {"results": results}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, memory_type: str):
    """Delete a memory"""
    memory = MemoryService.get_instance()
    success = await memory.delete_memory(memory_id, memory_type)
    return {"success": success}


@router.get("/stats")
async def get_memory_stats():
    """Get memory statistics"""
    memory = MemoryService.get_instance()
    stats = await memory.get_stats()
    return stats


@router.post("/process-batch")
async def trigger_batch_processing():
    """Manually trigger batch processing"""
    memory = MemoryService.get_instance()
    await memory.process_batch()
    return {"success": True, "message": "Batch processing triggered"}


@router.post("/backfill-screenshots")
async def backfill_screenshots():
    """
    Backfill existing screenshots that weren't added to the message queue.
    This is a one-time fix for screenshots captured before the memory manager integration.
    """
    from memory import MemoryOrchestrator

    db = Database.get_instance()
    memory_manager = MemoryOrchestrator.get_instance()

    # Get all screenshots
    screenshots = await db.get_screenshots(limit=1000)

    # Get existing capture messages
    all_messages = await db.get_recent_messages(limit=10000)
    existing_screenshot_ids = {
        m.get('screenshot_id') for m in all_messages
        if m.get('role') == 'capture' and m.get('screenshot_id')
    }

    # Find screenshots without capture messages
    missing_screenshots = [s for s in screenshots if s['id'] not in existing_screenshot_ids]

    # Sort by timestamp (oldest first) for proper memory generation
    missing_screenshots.sort(key=lambda s: s.get('timestamp', 0))

    processed_count = 0
    for screenshot in missing_screenshots:
        try:
            await memory_manager.on_screenshot_captured(screenshot)
            processed_count += 1
        except Exception as e:
            print(f"Failed to backfill screenshot {screenshot['id']}: {e}")

    return {
        "success": True,
        "total_screenshots": len(screenshots),
        "missing_screenshots": len(missing_screenshots),
        "processed": processed_count,
        "message": f"Backfilled {processed_count} screenshots. Queue size: {memory_manager.get_batch_status()['queue_size']}"
    }


@router.post("/regenerate-semantic")
async def regenerate_semantic_memories():
    """
    Regenerate semantic memories from existing episodic memories.
    Useful when semantic memories were lost due to schema issues.
    """
    from memory import SemanticExtractor

    db = Database.get_instance()
    semantic_agent = SemanticExtractor()

    # Get all episodic memories
    episodic_memories = await db.get_episodic_memories(limit=1000)

    created_count = 0
    errors = []

    for episodic in episodic_memories:
        try:
            # Get the event_ids (original message IDs) from the episodic memory
            event_ids = episodic.get('event_ids', [])
            if isinstance(event_ids, str):
                import json
                event_ids = json.loads(event_ids)

            if not event_ids:
                continue

            # Get source_app from episodic memory
            source_app = episodic.get('source_app', ['nemori'])
            if isinstance(source_app, str):
                import json
                source_app = json.loads(source_app)

            # Create semantic memories from the segment
            semantic_memories = await semantic_agent.create_from_segment(
                message_ids=event_ids,
                summary=episodic.get('content'),
                top_n=5,
                source_app=source_app
            )

            created_count += len(semantic_memories)
            print(f"Created {len(semantic_memories)} semantic memories from episodic: {episodic.get('title', 'Untitled')}")

        except Exception as e:
            error_msg = f"Failed to process episodic {episodic.get('id')}: {str(e)}"
            print(error_msg)
            errors.append(error_msg)

    return {
        "success": True,
        "episodic_count": len(episodic_memories),
        "semantic_created": created_count,
        "errors": errors[:10] if errors else [],  # Only return first 10 errors
        "message": f"Regenerated {created_count} semantic memories from {len(episodic_memories)} episodic memories"
    }
