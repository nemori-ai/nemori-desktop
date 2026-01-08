"""
Summarization Middleware - Context management for agent conversations

Implements automatic context summarization to prevent token overflow
while maintaining conversation continuity.
"""

import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from services.llm_service import LLMService


@dataclass
class SummarizationConfig:
    """Configuration for summarization middleware."""
    max_context_tokens: int = 8000  # Maximum tokens before summarization
    summary_target_tokens: int = 1000  # Target size for summaries
    min_messages_to_summarize: int = 4  # Minimum messages before summarization
    preserve_recent_messages: int = 2  # Number of recent messages to always keep


@dataclass
class ConversationContext:
    """Represents the current conversation context."""
    messages: List[Dict[str, str]] = field(default_factory=list)
    summary: Optional[str] = None
    total_tokens_estimate: int = 0


class SummarizationMiddleware:
    """Middleware that manages conversation context through summarization.

    This middleware automatically summarizes older messages when the context
    grows too large, maintaining important context while staying within
    token limits.
    """

    def __init__(self, config: Optional[SummarizationConfig] = None):
        """Initialize the summarization middleware.

        Args:
            config: Configuration options. Uses defaults if not provided.
        """
        self.config = config or SummarizationConfig()
        self.llm = LLMService.get_instance()
        self._context_cache: Dict[str, ConversationContext] = {}

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation).

        Uses a simple character-based estimation: ~4 characters per token for English,
        ~2 characters per token for Chinese/Japanese.
        """
        # Simple heuristic: count characters and estimate
        # Chinese/Japanese characters are typically 1-2 tokens each
        # English words are typically 1-2 tokens
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
        other_count = len(text) - cjk_count

        return (cjk_count * 2) + (other_count // 4)

    def _estimate_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate total tokens for a list of messages."""
        total = 0
        for msg in messages:
            # Add overhead for role and structure
            total += 4
            total += self._estimate_tokens(msg.get('content', ''))
        return total

    async def process_context(
        self,
        conversation_id: str,
        new_message: Dict[str, str],
        existing_messages: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, str]]:
        """Process a new message and return the optimized context.

        Args:
            conversation_id: Unique identifier for the conversation
            new_message: The new message to add
            existing_messages: Existing messages (if not using cache)

        Returns:
            Optimized list of messages for the LLM call
        """
        # Get or create context
        if conversation_id not in self._context_cache:
            self._context_cache[conversation_id] = ConversationContext()

        context = self._context_cache[conversation_id]

        # Initialize with existing messages if provided
        if existing_messages is not None and not context.messages:
            context.messages = list(existing_messages)

        # Add new message
        context.messages.append(new_message)

        # Estimate current token count
        context.total_tokens_estimate = self._estimate_messages_tokens(context.messages)

        # Check if summarization is needed
        if self._needs_summarization(context):
            await self._summarize_context(context)

        # Build and return optimized context
        return self._build_context(context)

    def _needs_summarization(self, context: ConversationContext) -> bool:
        """Check if the context needs to be summarized."""
        # Need enough messages to summarize
        if len(context.messages) < self.config.min_messages_to_summarize:
            return False

        # Check token estimate
        return context.total_tokens_estimate > self.config.max_context_tokens

    async def _summarize_context(self, context: ConversationContext) -> None:
        """Summarize older messages in the context."""
        if not self.llm.is_configured():
            # If LLM not configured, just truncate
            context.messages = context.messages[-self.config.preserve_recent_messages:]
            return

        # Determine which messages to summarize
        messages_to_keep = context.messages[-self.config.preserve_recent_messages:]
        messages_to_summarize = context.messages[:-self.config.preserve_recent_messages]

        if not messages_to_summarize:
            return

        # Build summary prompt
        conversation_text = self._format_messages_for_summary(messages_to_summarize)

        prompt = f"""Please summarize the following conversation, preserving:
1. Key facts and information discussed
2. User preferences and decisions made
3. Important context that may be needed later
4. Any tool calls and their results

Keep the summary concise but comprehensive. Focus on information that would be useful for continuing the conversation.

Previous summary (if any): {context.summary or 'None'}

Conversation to summarize:
{conversation_text}

Provide a summary in 2-4 paragraphs:"""

        try:
            summary = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=self.config.summary_target_tokens
            )

            # Update context
            context.summary = summary.strip()
            context.messages = messages_to_keep
            context.total_tokens_estimate = self._estimate_messages_tokens(messages_to_keep)
            context.total_tokens_estimate += self._estimate_tokens(summary)

        except Exception as e:
            print(f"Summarization failed: {e}")
            # Fallback: just truncate
            context.messages = messages_to_keep

    def _format_messages_for_summary(self, messages: List[Dict[str, str]]) -> str:
        """Format messages for summarization prompt."""
        lines = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."

            lines.append(f"{role.upper()}: {content}")

        return "\n\n".join(lines)

    def _build_context(self, context: ConversationContext) -> List[Dict[str, str]]:
        """Build the final context for LLM call."""
        result = []

        # Add summary as system message if exists
        if context.summary:
            result.append({
                "role": "system",
                "content": f"Previous conversation summary:\n{context.summary}"
            })

        # Add current messages
        result.extend(context.messages)

        return result

    def add_tool_result(
        self,
        conversation_id: str,
        tool_name: str,
        tool_result: Any
    ) -> None:
        """Add a tool result to the context.

        Args:
            conversation_id: Conversation identifier
            tool_name: Name of the tool that was called
            tool_result: Result from the tool
        """
        if conversation_id not in self._context_cache:
            self._context_cache[conversation_id] = ConversationContext()

        context = self._context_cache[conversation_id]

        # Format tool result as assistant message
        result_str = json.dumps(tool_result, ensure_ascii=False) if not isinstance(tool_result, str) else tool_result

        context.messages.append({
            "role": "assistant",
            "content": f"[Tool: {tool_name}]\n{result_str}"
        })

    def clear_context(self, conversation_id: str) -> None:
        """Clear the context for a conversation.

        Args:
            conversation_id: Conversation identifier to clear
        """
        if conversation_id in self._context_cache:
            del self._context_cache[conversation_id]

    def get_context_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get statistics about a conversation context.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Dictionary with context statistics
        """
        if conversation_id not in self._context_cache:
            return {
                "exists": False,
                "message_count": 0,
                "has_summary": False,
                "estimated_tokens": 0
            }

        context = self._context_cache[conversation_id]
        return {
            "exists": True,
            "message_count": len(context.messages),
            "has_summary": context.summary is not None,
            "estimated_tokens": context.total_tokens_estimate
        }
