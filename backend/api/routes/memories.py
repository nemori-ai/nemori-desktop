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
    from agents.memory_manager import MemoryManager

    db = Database.get_instance()
    memory_manager = MemoryManager.get_instance()

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
