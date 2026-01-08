"""
Agent Executor - LangChain 1.0 native agent with SSE streaming

This module implements the main agent execution using LangChain 1.0's create_agent
function with custom middleware for streaming events via SSE.

Architecture:
1. Uses LangChain 1.0's create_agent for the core ReAct loop
2. Custom middleware for event streaming and session tracking
3. SSE-compatible event generation for frontend consumption
"""

import json
import time
import uuid
import asyncio
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator, Callable
from datetime import datetime

from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from models.agent_schemas import (
    AgentSession,
    AgentStatus,
    ToolCall,
    ToolCallStatus,
    StreamEvent,
    EventType,
)
from services.llm_service import LLMService
from storage.database import Database
from .tools import get_all_tools
from .middleware.summarization import SummarizationMiddleware


# Default tool call timeout in seconds
TOOL_CALL_TIMEOUT = 30

# System prompt for the agent
AGENT_SYSTEM_PROMPT = """You are Nemori, an intelligent personal assistant with access to the user's memory system.

Current date and time: {current_datetime}

You have access to the following tools to search and retrieve information from the user's memories:

{tools_description}

TOOL USAGE GUIDELINES:

1. **Parallel Tool Calls**: You can call multiple tools simultaneously when they are independent.
   - Good: Call search_episodic_memory and search_semantic_memory at the same time for broader coverage
   - Good: Call keyword_search and time_filter together when searching for specific terms in a time range
   - All parallel tool calls will complete before you see the results

2. **Think Tool**: Use the `think` tool to pause and reason through complex situations.
   - Use it AFTER receiving tool results to analyze and synthesize information
   - Use it when planning a multi-step approach
   - Use it when the situation is ambiguous and needs careful consideration
   - The think tool helps you organize your thoughts before responding

3. **Sequential Calls**: Call tools sequentially when results from one tool inform the next.
   - Example: First get_user_profile, then search based on discovered preferences

When answering questions about the user or their past experiences:
1. First, use the appropriate memory search tools to find relevant information
2. Combine information from multiple sources for comprehensive answers
3. Use the think tool to analyze results when dealing with complex questions
4. Provide well-reasoned answers based on the retrieved memories
5. If no relevant memories are found, let the user know

Tool Selection Guidelines:
- Use semantic search (search_episodic_memory, search_semantic_memory) when looking for meaning or context
- Use keyword_search when looking for specific terms or exact matches
- Use time_filter when the question involves specific time periods
- Use get_user_profile to understand the user's overall preferences and characteristics
- Use get_recent_activity to see what the user has been doing lately
- Use search_chat_history to find previous conversations
- Use think to reason through complex problems or analyze multiple tool results
- When referring to dates, use the current date above as reference. "Yesterday" means one day before the current date.

Always be helpful, accurate, and respect the user's privacy. Base your responses on the actual memories retrieved.
"""


class AgentExecutor:
    """Executes agent conversations using LangChain 1.0's native agent pattern."""

    def __init__(
        self,
        max_steps: int = 10,
        tools: Optional[List] = None,
        on_event: Optional[Callable[[StreamEvent], None]] = None
    ):
        """Initialize the agent executor.

        Args:
            max_steps: Maximum number of reasoning steps
            tools: List of tools available to the agent. Defaults to all memory tools.
            on_event: Optional callback for stream events
        """
        self.max_steps = max_steps
        self.tools = tools or get_all_tools()
        self.on_event = on_event

        self.llm_service = LLMService.get_instance()
        self.db = Database.get_instance()
        self.middleware = SummarizationMiddleware()

        # Build tool lookup for name resolution
        self.tool_map: Dict[str, Any] = {tool.name: tool for tool in self.tools}

    def _build_system_prompt(self) -> str:
        """Build the system prompt with tool descriptions."""
        tools_desc = "\n".join([
            f"- **{tool.name}**: {tool.description}"
            for tool in self.tools
        ])
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        return AGENT_SYSTEM_PROMPT.format(
            tools_description=tools_desc,
            current_datetime=current_datetime
        )

    def _create_langchain_agent(self):
        """Create a LangGraph ReAct agent with our tools.

        Uses langgraph.prebuilt.create_react_agent which is the stable API
        for creating tool-calling agents in the LangChain ecosystem.
        """
        # Get the model from LLM service
        model_name = self.llm_service.model
        api_key = self.llm_service.api_key
        base_url = self.llm_service.base_url

        # Create ChatOpenAI instance with tool calling support
        # Enable parallel tool calls - LangGraph will wait for all to complete
        chat_model = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
        )  # parallel_tool_calls enabled by default

        # Create agent using LangGraph's create_react_agent
        # This creates a graph that alternates between the model and tools
        # Using 'prompt' parameter which accepts str and converts to SystemMessage
        agent = create_react_agent(
            model=chat_model,
            tools=self.tools,
            prompt=self._build_system_prompt(),
        )

        return agent

    async def run(
        self,
        user_input: str,
        conversation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        existing_messages: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run the agent with the given user input.

        Args:
            user_input: The user's message
            conversation_id: Optional conversation ID for context
            session_id: Optional session ID (will be generated if not provided)
            existing_messages: Optional existing conversation messages

        Yields:
            StreamEvent objects for each step of the agent execution
        """
        # Create session
        session = AgentSession.create(
            conversation_id=conversation_id or str(uuid.uuid4()),
            max_steps=self.max_steps
        )
        if session_id:
            session.id = session_id

        session.start()

        # Emit session start
        start_event = StreamEvent.session_start(
            session_id=session.id,
            conversation_id=session.conversation_id,
            max_steps=session.max_steps,
            tools=[tool.name for tool in self.tools]
        )
        yield start_event
        if self.on_event:
            self.on_event(start_event)

        try:
            # Build message history
            messages = existing_messages or []
            user_message = {"role": "user", "content": user_input}

            # Process through summarization middleware
            context_messages = await self.middleware.process_context(
                conversation_id=session.conversation_id,
                new_message=user_message,
                existing_messages=messages
            )

            # Convert to LangChain message format
            langchain_messages = self._convert_to_langchain_messages(context_messages)

            # Create agent
            agent = self._create_langchain_agent()

            # Stream agent execution
            final_response = ""
            step = 0

            async for event in self._stream_agent_execution(
                agent, langchain_messages, session
            ):
                yield event

                # Track final response
                if event.type == EventType.RESPONSE_END:
                    final_response = event.data.get("content", "")
                    step = event.step or 0

            # Complete session
            session.current_step = step
            session.complete()

            # Emit session end
            end_event = StreamEvent.session_end(
                session_id=session.id,
                total_steps=session.current_step,
                tool_calls_count=session.tool_calls_count,
                total_duration_ms=session.duration_ms or 0
            )
            yield end_event
            if self.on_event:
                self.on_event(end_event)

            # Save session to database
            await self._save_session(session)

        except Exception as e:
            # Handle unexpected errors
            session.fail()
            error_event = StreamEvent.error(
                session_id=session.id,
                code="execution_error",
                message=str(e),
                recoverable=False
            )
            yield error_event
            if self.on_event:
                self.on_event(error_event)

    def _convert_to_langchain_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> List[Any]:
        """Convert dict messages to LangChain message objects."""
        langchain_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            elif role == "tool":
                langchain_messages.append(ToolMessage(
                    content=content,
                    tool_call_id=msg.get("tool_call_id", "")
                ))
            else:  # user
                langchain_messages.append(HumanMessage(content=content))

        return langchain_messages

    async def _stream_agent_execution(
        self,
        agent,
        messages: List,
        session: AgentSession
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream agent execution events.

        This method wraps LangChain's agent streaming to emit our custom events.
        """
        step = 0
        thinking_start_time = None

        try:
            # Use LangChain's native streaming
            async for event in agent.astream(
                {"messages": messages},
                stream_mode="values"
            ):
                # Process each streamed event
                latest_messages = event.get("messages", [])
                if not latest_messages:
                    continue

                latest_message = latest_messages[-1]

                # Check for tool calls
                if hasattr(latest_message, 'tool_calls') and latest_message.tool_calls:
                    # Log parallel tool calls for debugging
                    if len(latest_message.tool_calls) > 1:
                        tool_names = [tc.get('name', 'unknown') for tc in latest_message.tool_calls]
                        logger.info(
                            f"Parallel tool calls detected: {tool_names}. "
                            "LangGraph will execute all and wait for completion."
                        )

                    for tool_call in latest_message.tool_calls:
                        step += 1
                        session.current_step = step

                        # Emit thinking start
                        if thinking_start_time is None:
                            thinking_start_time = time.time()
                            thinking_start = StreamEvent.thinking_start(session.id, step)
                            yield thinking_start
                            if self.on_event:
                                self.on_event(thinking_start)

                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('args', {})
                        tool_call_id = tool_call.get('id', str(uuid.uuid4()))

                        # Create tool call record
                        tc = ToolCall(
                            session_id=session.id,
                            step=step,
                            tool_name=tool_name,
                            tool_args=tool_args
                        )
                        tc.id = tool_call_id
                        session.add_tool_call(tc)

                        # Emit thinking end
                        if thinking_start_time:
                            thinking_duration = int((time.time() - thinking_start_time) * 1000)
                            thinking_end = StreamEvent.thinking_end(session.id, step, thinking_duration)
                            yield thinking_end
                            if self.on_event:
                                self.on_event(thinking_end)
                            thinking_start_time = None

                        # Emit tool call start
                        tool_start_event = StreamEvent.tool_call_start(
                            session_id=session.id,
                            step=step,
                            tool_call_id=tool_call_id,
                            tool_name=tool_name
                        )
                        yield tool_start_event
                        if self.on_event:
                            self.on_event(tool_start_event)

                        # Emit tool call args
                        tool_args_event = StreamEvent.tool_call_args(
                            session_id=session.id,
                            step=step,
                            tool_call_id=tool_call_id,
                            args=tool_args
                        )
                        yield tool_args_event
                        if self.on_event:
                            self.on_event(tool_args_event)

                        tc.start()
                        thinking_start_time = time.time()

                # Check for tool results
                elif isinstance(latest_message, ToolMessage):
                    tool_call_id = latest_message.tool_call_id
                    tool_result = latest_message.content

                    # Find matching tool call
                    tc = next(
                        (t for t in session.tool_calls if t.id == tool_call_id),
                        None
                    )

                    if tc:
                        if "error" in str(tool_result).lower() and "success" not in str(tool_result):
                            tc.fail(str(tool_result))
                            tool_error_event = StreamEvent.tool_call_error(
                                session_id=session.id,
                                step=tc.step,
                                tool_call_id=tool_call_id,
                                error=str(tool_result)
                            )
                            yield tool_error_event
                            if self.on_event:
                                self.on_event(tool_error_event)
                        else:
                            tc.complete(tool_result)
                            tool_result_event = StreamEvent.tool_call_result(
                                session_id=session.id,
                                step=tc.step,
                                tool_call_id=tool_call_id,
                                result=tool_result,
                                duration_ms=tc.duration_ms or 0
                            )
                            yield tool_result_event
                            if self.on_event:
                                self.on_event(tool_result_event)

                # Check for final response (AIMessage without tool calls)
                elif isinstance(latest_message, AIMessage):
                    if not hasattr(latest_message, 'tool_calls') or not latest_message.tool_calls:
                        content = latest_message.content
                        if content:
                            step += 1

                            # Emit thinking end if still thinking
                            if thinking_start_time:
                                thinking_duration = int((time.time() - thinking_start_time) * 1000)
                                thinking_end = StreamEvent.thinking_end(session.id, step, thinking_duration)
                                yield thinking_end
                                if self.on_event:
                                    self.on_event(thinking_end)
                                thinking_start_time = None

                            # Emit response start
                            response_start = StreamEvent.response_start(session.id, step)
                            yield response_start
                            if self.on_event:
                                self.on_event(response_start)

                            # Emit response as chunks
                            chunk_size = 50
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i + chunk_size]
                                chunk_event = StreamEvent.response_chunk(session.id, step, chunk)
                                yield chunk_event
                                if self.on_event:
                                    self.on_event(chunk_event)

                            # Emit response end
                            response_end = StreamEvent.response_end(session.id, step, content)
                            yield response_end
                            if self.on_event:
                                self.on_event(response_end)

        except Exception as e:
            # Handle streaming errors
            error_event = StreamEvent.error(
                session_id=session.id,
                code="stream_error",
                message=str(e),
                recoverable=False
            )
            yield error_event
            if self.on_event:
                self.on_event(error_event)

    async def _save_session(self, session: AgentSession) -> None:
        """Save session and tool calls to database.

        Args:
            session: The completed agent session
        """
        try:
            conn = self.db._connection

            # Save session
            await conn.execute(
                """
                INSERT OR REPLACE INTO agent_sessions
                (id, conversation_id, status, current_step, max_steps, config,
                 created_at, updated_at, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.conversation_id,
                    session.status.value,
                    session.current_step,
                    session.max_steps,
                    None,  # config
                    session.created_at,
                    session.updated_at,
                    session.started_at,
                    session.completed_at,
                ),
            )

            # Save tool calls
            for tc in session.tool_calls:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO tool_calls
                    (id, session_id, step, tool_name, tool_args, status,
                     result, error, started_at, completed_at, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tc.id,
                        tc.session_id,
                        tc.step,
                        tc.tool_name,
                        json.dumps(tc.tool_args),
                        tc.status.value,
                        json.dumps(tc.result) if tc.result else None,
                        tc.error,
                        tc.started_at,
                        tc.completed_at,
                        tc.duration_ms,
                    ),
                )

            await conn.commit()

        except Exception as e:
            print(f"Failed to save agent session: {e}")


async def run_agent(
    user_input: str,
    conversation_id: Optional[str] = None,
    max_steps: int = 10,
    tools: Optional[List] = None
) -> AsyncGenerator[StreamEvent, None]:
    """Convenience function to run the agent.

    Args:
        user_input: The user's message
        conversation_id: Optional conversation ID
        max_steps: Maximum reasoning steps
        tools: Optional list of tools

    Yields:
        StreamEvent objects
    """
    executor = AgentExecutor(max_steps=max_steps, tools=tools)
    async for event in executor.run(user_input, conversation_id):
        yield event
