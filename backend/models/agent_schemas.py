"""
Agent Data Models - Pydantic schemas for agent functionality
"""

import uuid
import time
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent session status"""
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    STREAMING = "streaming"
    COMPLETED = "completed"
    ERROR = "error"


class ToolCallStatus(str, Enum):
    """Tool call execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


class EventType(str, Enum):
    """SSE event types"""
    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Thinking process
    THINKING_START = "thinking_start"
    THINKING_CHUNK = "thinking_chunk"
    THINKING_END = "thinking_end"

    # Tool calls
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_ARGS = "tool_call_args"
    TOOL_CALL_RESULT = "tool_call_result"
    TOOL_CALL_ERROR = "tool_call_error"

    # Response output
    RESPONSE_START = "response_start"
    RESPONSE_CHUNK = "response_chunk"
    RESPONSE_END = "response_end"

    # Error
    ERROR = "error"


class ToolCall(BaseModel):
    """Tool call record"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    step: int = 0
    tool_name: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    duration_ms: Optional[int] = None

    def start(self):
        """Mark tool call as started"""
        self.status = ToolCallStatus.RUNNING
        self.started_at = int(time.time() * 1000)

    def complete(self, result: Any):
        """Mark tool call as completed"""
        self.status = ToolCallStatus.COMPLETED
        self.result = result
        self.completed_at = int(time.time() * 1000)
        if self.started_at:
            self.duration_ms = self.completed_at - self.started_at

    def fail(self, error: str):
        """Mark tool call as failed"""
        self.status = ToolCallStatus.ERROR
        self.error = error
        self.completed_at = int(time.time() * 1000)
        if self.started_at:
            self.duration_ms = self.completed_at - self.started_at


class AgentSession(BaseModel):
    """Agent session state"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    status: AgentStatus = AgentStatus.IDLE
    current_step: int = 0
    max_steps: int = 10
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_calls_count: int = 0
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    started_at: Optional[int] = None
    completed_at: Optional[int] = None

    @classmethod
    def create(
        cls,
        conversation_id: Optional[str] = None,
        max_steps: int = 10
    ) -> "AgentSession":
        """Create a new agent session"""
        return cls(
            conversation_id=conversation_id or str(uuid.uuid4()),
            max_steps=max_steps
        )

    def start(self):
        """Start the session"""
        self.status = AgentStatus.THINKING
        self.started_at = int(time.time() * 1000)
        self.updated_at = self.started_at

    def complete(self):
        """Complete the session"""
        self.status = AgentStatus.COMPLETED
        self.completed_at = int(time.time() * 1000)
        self.updated_at = self.completed_at

    def fail(self):
        """Mark session as failed"""
        self.status = AgentStatus.ERROR
        self.completed_at = int(time.time() * 1000)
        self.updated_at = self.completed_at

    @property
    def duration_ms(self) -> Optional[int]:
        """Get session duration in milliseconds"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    def add_tool_call(self, tool_call: ToolCall):
        """Add a tool call to the session"""
        self.tool_calls.append(tool_call)
        self.tool_calls_count = len(self.tool_calls)
        self.updated_at = int(time.time() * 1000)


class StreamEvent(BaseModel):
    """SSE stream event"""
    type: EventType
    session_id: str
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))
    step: Optional[int] = None
    tool_call_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def session_start(
        cls,
        session_id: str,
        conversation_id: str,
        max_steps: int,
        tools: List[str]
    ) -> "StreamEvent":
        return cls(
            type=EventType.SESSION_START,
            session_id=session_id,
            data={
                "conversation_id": conversation_id,
                "max_steps": max_steps,
                "tools": tools
            }
        )

    @classmethod
    def session_end(
        cls,
        session_id: str,
        total_steps: int,
        tool_calls_count: int,
        total_duration_ms: int
    ) -> "StreamEvent":
        return cls(
            type=EventType.SESSION_END,
            session_id=session_id,
            data={
                "total_steps": total_steps,
                "tool_calls_count": tool_calls_count,
                "total_duration_ms": total_duration_ms
            }
        )

    @classmethod
    def thinking_start(cls, session_id: str, step: int) -> "StreamEvent":
        return cls(
            type=EventType.THINKING_START,
            session_id=session_id,
            step=step,
            data={}
        )

    @classmethod
    def thinking_chunk(cls, session_id: str, step: int, content: str) -> "StreamEvent":
        return cls(
            type=EventType.THINKING_CHUNK,
            session_id=session_id,
            step=step,
            data={"content": content}
        )

    @classmethod
    def thinking_end(cls, session_id: str, step: int, duration_ms: int) -> "StreamEvent":
        return cls(
            type=EventType.THINKING_END,
            session_id=session_id,
            step=step,
            data={"duration_ms": duration_ms}
        )

    @classmethod
    def tool_call_start(
        cls,
        session_id: str,
        step: int,
        tool_call_id: str,
        tool_name: str
    ) -> "StreamEvent":
        return cls(
            type=EventType.TOOL_CALL_START,
            session_id=session_id,
            step=step,
            tool_call_id=tool_call_id,
            data={"tool_call_id": tool_call_id, "tool_name": tool_name}
        )

    @classmethod
    def tool_call_args(
        cls,
        session_id: str,
        step: int,
        tool_call_id: str,
        args: Dict[str, Any]
    ) -> "StreamEvent":
        return cls(
            type=EventType.TOOL_CALL_ARGS,
            session_id=session_id,
            step=step,
            tool_call_id=tool_call_id,
            data={"tool_call_id": tool_call_id, "args": args}
        )

    @classmethod
    def tool_call_result(
        cls,
        session_id: str,
        step: int,
        tool_call_id: str,
        result: Any,
        duration_ms: int
    ) -> "StreamEvent":
        return cls(
            type=EventType.TOOL_CALL_RESULT,
            session_id=session_id,
            step=step,
            tool_call_id=tool_call_id,
            data={
                "tool_call_id": tool_call_id,
                "result": result,
                "duration_ms": duration_ms
            }
        )

    @classmethod
    def tool_call_error(
        cls,
        session_id: str,
        step: int,
        tool_call_id: str,
        error: str
    ) -> "StreamEvent":
        return cls(
            type=EventType.TOOL_CALL_ERROR,
            session_id=session_id,
            step=step,
            tool_call_id=tool_call_id,
            data={"tool_call_id": tool_call_id, "error": error}
        )

    @classmethod
    def response_start(cls, session_id: str, step: int) -> "StreamEvent":
        return cls(
            type=EventType.RESPONSE_START,
            session_id=session_id,
            step=step,
            data={}
        )

    @classmethod
    def response_chunk(cls, session_id: str, step: int, content: str) -> "StreamEvent":
        return cls(
            type=EventType.RESPONSE_CHUNK,
            session_id=session_id,
            step=step,
            data={"content": content}
        )

    @classmethod
    def response_end(cls, session_id: str, step: int, content: str) -> "StreamEvent":
        return cls(
            type=EventType.RESPONSE_END,
            session_id=session_id,
            step=step,
            data={"content": content}
        )

    @classmethod
    def error(
        cls,
        session_id: str,
        code: str,
        message: str,
        recoverable: bool = False
    ) -> "StreamEvent":
        return cls(
            type=EventType.ERROR,
            session_id=session_id,
            data={
                "code": code,
                "message": message,
                "recoverable": recoverable
            }
        )


class AgentMessage(BaseModel):
    """Extended message format for agent conversations"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: Literal["user", "assistant", "tool"]
    content: Optional[str] = None
    conversation_id: str
    session_id: Optional[str] = None
    timestamp: int = Field(default_factory=lambda: int(time.time() * 1000))

    # Agent-specific fields
    thinking: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None  # For role="tool"


class AgentChatRequest(BaseModel):
    """Agent chat request"""
    content: str
    conversation_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    @property
    def max_steps(self) -> int:
        return self.config.get("max_steps", 10) if self.config else 10

    @property
    def enabled_tools(self) -> Optional[List[str]]:
        return self.config.get("tools") if self.config else None


class AgentChatResponse(BaseModel):
    """Agent chat response (for sync mode)"""
    success: bool
    session_id: str
    conversation_id: str
    message: Optional[AgentMessage] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    error: Optional[str] = None
