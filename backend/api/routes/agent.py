"""
Agent API Routes - SSE streaming agent conversations
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
from agents.executor import AgentExecutor
from agents.tools import get_tool_descriptions
from models.agent_schemas import AgentChatRequest, StreamEvent, EventType

router = APIRouter()


class AgentInfoResponse(BaseModel):
    """Response for agent info endpoint"""
    available_tools: dict
    max_steps: int
    version: str


class AgentSessionResponse(BaseModel):
    """Response for agent session info"""
    session_id: str
    conversation_id: str
    status: str
    current_step: int
    tool_calls_count: int
    created_at: int
    completed_at: Optional[int] = None


@router.get("/info")
async def get_agent_info() -> AgentInfoResponse:
    """Get information about the agent and available tools."""
    return AgentInfoResponse(
        available_tools=get_tool_descriptions(),
        max_steps=10,
        version="1.0.0"
    )


@router.post("/chat")
async def agent_chat(request: AgentChatRequest):
    """Start an agent conversation with SSE streaming.

    This endpoint streams events for the entire agent execution:
    - session_start: Agent session started
    - thinking_start/end: Agent is reasoning
    - tool_call_start/args/result/error: Tool execution events
    - response_start/chunk/end: Final response streaming
    - session_end: Agent session completed
    - error: Error occurred

    Events are sent as SSE with JSON data.
    """
    llm = LLMService.get_instance()
    db = Database.get_instance()
    memory = MemoryService.get_instance()

    if not llm.is_configured():
        raise HTTPException(
            status_code=400,
            detail="LLM service not configured. Please set your API key in settings."
        )

    # Generate IDs
    conversation_id = request.conversation_id or str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    timestamp = int(datetime.now().timestamp() * 1000)
    is_new_conversation = not request.conversation_id

    # Create conversation if new
    if is_new_conversation:
        await db.create_conversation(conversation_id, "Agent Conversation")

    # Save user message
    user_message_id = str(uuid.uuid4())
    await db.save_message({
        "id": user_message_id,
        "role": "user",
        "content": request.content,
        "timestamp": timestamp,
        "conversation_id": conversation_id
    })

    # Get conversation history for context
    history = await db.get_messages(conversation_id, limit=20)
    existing_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[:-1]  # Exclude the message we just saved
    ]

    # Create executor
    max_steps = request.max_steps
    executor = AgentExecutor(max_steps=max_steps)

    async def generate_events():
        """Generate SSE events from agent execution."""
        final_response = ""

        try:
            async for event in executor.run(
                user_input=request.content,
                conversation_id=conversation_id,
                session_id=session_id,
                existing_messages=existing_messages
            ):
                # Track final response
                if event.type == EventType.RESPONSE_END:
                    final_response = event.data.get("content", "")

                # Serialize event to JSON
                event_data = {
                    "type": event.type.value,
                    "session_id": event.session_id,
                    "timestamp": event.timestamp,
                    "step": event.step,
                    "tool_call_id": event.tool_call_id,
                    "data": event.data
                }

                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            # Save assistant response after completion
            if final_response:
                assistant_message_id = str(uuid.uuid4())
                assistant_timestamp = int(datetime.now().timestamp() * 1000)
                await db.save_message({
                    "id": assistant_message_id,
                    "role": "assistant",
                    "content": final_response,
                    "timestamp": assistant_timestamp,
                    "conversation_id": conversation_id,
                    "metadata": {"session_id": session_id, "is_agent": True}
                })

                # Add both user and assistant messages to memory batch for processing
                # Note: Include metadata to preserve session_id when add_to_batch saves
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
                    "content": final_response,
                    "timestamp": assistant_timestamp,
                    "conversation_id": conversation_id,
                    "metadata": {"session_id": session_id, "is_agent": True}
                })

                # Update conversation title for new conversations
                if is_new_conversation or len(history) <= 1:
                    title = request.content[:50].strip()
                    if len(request.content) > 50:
                        title = title.rsplit(' ', 1)[0] + '...'
                    await db.update_conversation(conversation_id, title)

        except Exception as e:
            # Send error event
            error_event = {
                "type": "error",
                "session_id": session_id,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "data": {
                    "code": "stream_error",
                    "message": str(e),
                    "recoverable": False
                }
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Conversation-Id": conversation_id,
            "X-Session-Id": session_id
        }
    )


@router.get("/sessions")
async def get_agent_sessions(
    conversation_id: Optional[str] = None,
    limit: int = 20
) -> List[AgentSessionResponse]:
    """Get agent sessions, optionally filtered by conversation."""
    db = Database.get_instance()
    conn = db._connection

    if conversation_id:
        cursor = await conn.execute(
            """SELECT * FROM agent_sessions
               WHERE conversation_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (conversation_id, limit)
        )
    else:
        cursor = await conn.execute(
            "SELECT * FROM agent_sessions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )

    rows = await cursor.fetchall()
    sessions = []

    for row in rows:
        session = dict(row)
        # Count tool calls for this session
        tc_cursor = await conn.execute(
            "SELECT COUNT(*) as count FROM tool_calls WHERE session_id = ?",
            (session['id'],)
        )
        tc_row = await tc_cursor.fetchone()

        sessions.append(AgentSessionResponse(
            session_id=session['id'],
            conversation_id=session['conversation_id'],
            status=session['status'],
            current_step=session['current_step'],
            tool_calls_count=tc_row['count'] if tc_row else 0,
            created_at=session['created_at'],
            completed_at=session.get('completed_at')
        ))

    return sessions


@router.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about an agent session including tool calls."""
    db = Database.get_instance()
    conn = db._connection

    # Get session
    cursor = await conn.execute(
        "SELECT * FROM agent_sessions WHERE id = ?",
        (session_id,)
    )
    session_row = await cursor.fetchone()

    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found")

    session = dict(session_row)

    # Get tool calls
    tc_cursor = await conn.execute(
        "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY step ASC",
        (session_id,)
    )
    tc_rows = await tc_cursor.fetchall()

    tool_calls = []
    for row in tc_rows:
        tc = dict(row)
        # Parse JSON fields
        if tc.get('tool_args'):
            try:
                tc['tool_args'] = json.loads(tc['tool_args'])
            except:
                pass
        if tc.get('result'):
            try:
                tc['result'] = json.loads(tc['result'])
            except:
                pass
        tool_calls.append(tc)

    return {
        "session": session,
        "tool_calls": tool_calls
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete an agent session and its tool calls."""
    db = Database.get_instance()
    conn = db._connection

    # Check if session exists
    cursor = await conn.execute(
        "SELECT id FROM agent_sessions WHERE id = ?",
        (session_id,)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete tool calls first (foreign key)
    await conn.execute(
        "DELETE FROM tool_calls WHERE session_id = ?",
        (session_id,)
    )

    # Delete session
    await conn.execute(
        "DELETE FROM agent_sessions WHERE id = ?",
        (session_id,)
    )

    await conn.commit()

    return {"success": True, "message": "Session deleted"}


@router.get("/tools")
async def list_tools():
    """List all available tools with their descriptions and schemas."""
    from agents.tools import get_all_tools

    tools = get_all_tools()
    tool_info = []

    for tool in tools:
        info = {
            "name": tool.name,
            "description": tool.description,
        }

        # Get input schema if available
        if hasattr(tool, 'args_schema') and tool.args_schema:
            try:
                info["input_schema"] = tool.args_schema.model_json_schema()
            except:
                pass

        tool_info.append(info)

    return {"tools": tool_info}
