"""
Chat API Routes
"""
import uuid
import json
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.llm_service import LLMService
from services.memory_service import MemoryService
from storage.database import Database

router = APIRouter()


class ChatRequest(BaseModel):
    content: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None
    use_memory: bool = True


class ChatResponse(BaseModel):
    success: bool
    message: Optional[dict] = None
    conversation_id: Optional[str] = None
    error: Optional[str] = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    timestamp: int
    conversation_id: str


@router.post("/send", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a chat message and get a response"""
    llm = LLMService.get_instance()
    db = Database.get_instance()
    memory = MemoryService.get_instance()

    if not llm.is_configured():
        raise HTTPException(
            status_code=400,
            detail="LLM service not configured. Please set your API key in settings."
        )

    # Create or use conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp() * 1000)

    # Check if conversation exists
    if not request.conversation_id:
        await db.create_conversation(conversation_id, "New Conversation")

    # Save user message
    user_message_id = str(uuid.uuid4())
    await db.save_message({
        "id": user_message_id,
        "role": "user",
        "content": request.content,
        "timestamp": timestamp,
        "conversation_id": conversation_id
    })

    try:
        # Get conversation history
        history = await db.get_messages(conversation_id, limit=20)

        # Build system context
        system_content = (
            "You are Nemori, a helpful AI assistant with access to the user's "
            "memories and past activities. Be concise, helpful, and friendly."
        )

        # Get memory context if enabled
        if request.use_memory:
            memory_context = await memory.get_memory_context(request.content)
            if memory_context:
                system_content += f"\n\nRelevant memories from past interactions:\n{memory_context}"

        # Build messages for LLM
        messages = [{"role": "system", "content": system_content}]
        messages.extend([
            {"role": m["role"], "content": m["content"]}
            for m in history
        ])
        messages.append({"role": "user", "content": request.content})

        # Get response from LLM
        response_content = await llm.chat(
            messages=messages,
            model=request.model
        )

        # Save assistant message
        assistant_message_id = str(uuid.uuid4())
        assistant_timestamp = int(datetime.now().timestamp() * 1000)
        await db.save_message({
            "id": assistant_message_id,
            "role": "assistant",
            "content": response_content,
            "timestamp": assistant_timestamp,
            "conversation_id": conversation_id
        })

        # Add both user and assistant messages to memory batch for processing
        await memory.add_to_batch({
            "id": user_message_id,
            "role": "user",
            "content": request.content,
            "timestamp": timestamp,
            "conversation_id": conversation_id
        })
        await memory.add_to_batch({
            "id": assistant_message_id,
            "role": "assistant",
            "content": response_content,
            "timestamp": assistant_timestamp,
            "conversation_id": conversation_id
        })

        # Update conversation title to user's first message
        if len(history) <= 1:
            # Use first 50 chars of user message as title
            title = request.content[:50].strip()
            if len(request.content) > 50:
                title = title.rsplit(' ', 1)[0] + '...'  # Cut at word boundary
            await db.update_conversation(conversation_id, title)

        return ChatResponse(
            success=True,
            message={
                "id": assistant_message_id,
                "role": "assistant",
                "content": response_content,
                "timestamp": assistant_timestamp,
                "conversation_id": conversation_id
            },
            conversation_id=conversation_id
        )

    except Exception as e:
        return ChatResponse(
            success=False,
            error=str(e),
            conversation_id=conversation_id
        )


@router.post("/stream")
async def stream_message(request: ChatRequest):
    """Stream a chat response"""
    llm = LLMService.get_instance()
    db = Database.get_instance()
    memory = MemoryService.get_instance()

    if not llm.is_configured():
        raise HTTPException(
            status_code=400,
            detail="LLM service not configured"
        )

    conversation_id = request.conversation_id or str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp() * 1000)
    is_new_conversation = not request.conversation_id

    # Create conversation if new
    if is_new_conversation:
        await db.create_conversation(conversation_id, "New Conversation")

    # Save user message
    user_message_id = str(uuid.uuid4())
    await db.save_message({
        "id": user_message_id,
        "role": "user",
        "content": request.content,
        "timestamp": timestamp,
        "conversation_id": conversation_id
    })

    # Get context
    history = await db.get_messages(conversation_id, limit=20)

    system_content = "You are Nemori, a helpful AI assistant."
    if request.use_memory:
        memory_context = await memory.get_memory_context(request.content)
        if memory_context:
            system_content += f"\n\nRelevant memories:\n{memory_context}"

    messages = [{"role": "system", "content": system_content}]
    messages.extend([{"role": m["role"], "content": m["content"]} for m in history])
    messages.append({"role": "user", "content": request.content})

    # Store user content for title generation
    user_content = request.content

    async def generate():
        full_response = ""
        async for chunk in llm.chat_stream(messages=messages, model=request.model):
            full_response += chunk
            # JSON encode the chunk to properly handle newlines and special characters
            yield f"data: {json.dumps(chunk)}\n\n"

        # Save complete response
        assistant_message_id = str(uuid.uuid4())
        assistant_timestamp = int(datetime.now().timestamp() * 1000)
        await db.save_message({
            "id": assistant_message_id,
            "role": "assistant",
            "content": full_response,
            "timestamp": assistant_timestamp,
            "conversation_id": conversation_id
        })

        # Add both user and assistant messages to memory batch for processing
        await memory.add_to_batch({
            "id": user_message_id,
            "role": "user",
            "content": user_content,
            "timestamp": timestamp,
            "conversation_id": conversation_id
        })
        await memory.add_to_batch({
            "id": assistant_message_id,
            "role": "assistant",
            "content": full_response,
            "timestamp": assistant_timestamp,
            "conversation_id": conversation_id
        })

        # Update title to user's first message for new conversation
        if is_new_conversation or len(history) <= 1:
            try:
                # Use first 50 chars of user message as title
                title = user_content[:50].strip()
                if len(user_content) > 50:
                    title = title.rsplit(' ', 1)[0] + '...'  # Cut at word boundary
                await db.update_conversation(conversation_id, title)
            except Exception as e:
                print(f"Failed to update title: {e}")

        yield f"data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Conversation-Id": conversation_id
        }
    )


@router.get("/messages/{conversation_id}")
async def get_messages(conversation_id: str, limit: int = 100):
    """Get messages for a conversation"""
    db = Database.get_instance()
    messages = await db.get_messages(conversation_id, limit)
    return {"messages": messages}


@router.get("/recent")
async def get_recent_messages(limit: int = 50):
    """Get recent messages across all conversations"""
    db = Database.get_instance()
    messages = await db.get_recent_messages(limit)
    return {"messages": messages}
