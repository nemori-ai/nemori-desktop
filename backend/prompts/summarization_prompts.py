"""
Summarization Prompts

Prompts used by the summarization middleware for:
- Summarizing conversation context to manage token limits
"""


def get_summarization_prompt(
    previous_summary: str,
    conversation_text: str
) -> str:
    """
    Generate prompt for summarizing conversation context.

    Args:
        previous_summary: Previous summary if any
        conversation_text: Text of conversation to summarize

    Returns:
        Formatted prompt string
    """
    return SUMMARIZATION_PROMPT.format(
        previous_summary=previous_summary or 'None',
        conversation_text=conversation_text
    )


SUMMARIZATION_PROMPT = """Please summarize the following conversation, preserving:
1. Key facts and information discussed
2. User preferences and decisions made
3. Important context that may be needed later
4. Any tool calls and their results

Keep the summary concise but comprehensive. Focus on information that would be useful for continuing the conversation.

Previous summary (if any): {previous_summary}

Conversation to summarize:
{conversation_text}

Provide a summary in 2-4 paragraphs:"""
