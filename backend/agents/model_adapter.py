"""
Model Adapter - Adapts LLMService to LangChain ChatModel interface

This module provides compatibility between the existing LLMService
and LangChain's chat model interface.
"""

from typing import Optional, List, Dict, Any, Iterator, AsyncIterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun

from services.llm_service import LLMService


class NemoriChatModel(BaseChatModel):
    """LangChain-compatible chat model adapter for Nemori's LLMService."""

    model_name: str = "nemori-chat"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    streaming: bool = False

    @property
    def _llm_type(self) -> str:
        return "nemori-chat"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to OpenAI format."""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
            else:
                # Default to user message
                converted.append({"role": "user", "content": str(msg.content)})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat completion synchronously."""
        import asyncio

        # Run async method in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._agenerate(messages, stop, None, **kwargs)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._agenerate(messages, stop, None, **kwargs)
                )
        except RuntimeError:
            return asyncio.run(self._agenerate(messages, stop, None, **kwargs))

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate chat completion asynchronously."""
        llm = LLMService.get_instance()

        if not llm.is_chat_configured():
            raise ValueError("Chat model not configured in LLMService")

        # Convert messages
        openai_messages = self._convert_messages(messages)

        # Get temperature and max_tokens from kwargs or instance
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        # Call LLMService
        response = await llm.chat(
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Create ChatResult
        message = AIMessage(content=response)
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream chat completion asynchronously."""
        llm = LLMService.get_instance()

        if not llm.is_chat_configured():
            raise ValueError("Chat model not configured in LLMService")

        # Convert messages
        openai_messages = self._convert_messages(messages)

        # Get temperature and max_tokens from kwargs or instance
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)

        # Stream from LLMService
        async for chunk in llm.chat_stream(
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield chunk


def create_chat_model(
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    streaming: bool = False
) -> BaseChatModel:
    """Create a LangChain-compatible chat model instance.

    Args:
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens in response
        streaming: Whether to enable streaming mode

    Returns:
        A LangChain BaseChatModel instance
    """
    return NemoriChatModel(
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming
    )
