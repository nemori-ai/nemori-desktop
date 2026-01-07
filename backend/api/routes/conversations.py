"""
Conversations API Routes
"""
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from storage.database import Database

router = APIRouter()


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    title: str


@router.get("/")
async def get_conversations(limit: int = 50):
    """Get all conversations (excludes empty ones)"""
    db = Database.get_instance()
    conversations = await db.get_conversations(limit)

    # Filter out empty conversations (no messages)
    non_empty = []
    for conv in conversations:
        messages = await db.get_messages(conv['id'], limit=1)
        if messages:
            non_empty.append(conv)
        else:
            # Delete empty conversation
            await db.delete_conversation(conv['id'])

    return {"conversations": non_empty}


@router.post("/")
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation"""
    db = Database.get_instance()
    conversation_id = str(uuid.uuid4())
    await db.create_conversation(conversation_id, request.title)
    return {
        "id": conversation_id,
        "title": request.title or "New Conversation"
    }


@router.put("/{conversation_id}")
async def update_conversation(conversation_id: str, request: UpdateConversationRequest):
    """Update a conversation"""
    db = Database.get_instance()
    await db.update_conversation(conversation_id, request.title)
    return {"success": True}


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages"""
    db = Database.get_instance()
    await db.delete_conversation(conversation_id)
    return {"success": True}
