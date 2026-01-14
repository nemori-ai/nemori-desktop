"""
Language utilities for prompt injection

Provides functions to inject language requirements into prompts,
ensuring LLM responses are generated in the user's preferred language.
"""

from typing import Optional

# Supported languages with their display names and instructions
SUPPORTED_LANGUAGES = {
    'en': {
        'name': 'English',
        'instruction': 'You MUST respond in English. All output text must be in English.',
    },
    'zh': {
        'name': '中文',
        'instruction': '你必须用中文回复。所有输出文本必须使用中文。',
    },
}

# Default language
DEFAULT_LANGUAGE = 'en'


def get_language_instruction(language: Optional[str] = None) -> str:
    """
    Get the language instruction for the specified language.

    Args:
        language: Language code ('en', 'zh'). Defaults to 'en'.

    Returns:
        Language instruction string to append to prompts.
    """
    lang = language or DEFAULT_LANGUAGE
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    return SUPPORTED_LANGUAGES[lang]['instruction']


def inject_language(prompt: str, language: Optional[str] = None) -> str:
    """
    Inject language requirement into a prompt.

    This function appends a language instruction to the end of the prompt,
    ensuring the LLM responds in the specified language.

    Args:
        prompt: The original prompt text.
        language: Language code ('en', 'zh'). Defaults to 'en'.

    Returns:
        Prompt with language instruction appended.
    """
    if not language:
        return prompt

    instruction = get_language_instruction(language)

    # Add a clear separator and the language instruction
    return f"{prompt}\n\n---\n**Language Requirement:**\n{instruction}"


def get_supported_languages() -> dict:
    """
    Get all supported languages.

    Returns:
        Dictionary of supported languages with their metadata.
    """
    return SUPPORTED_LANGUAGES.copy()


def is_language_supported(language: str) -> bool:
    """
    Check if a language is supported.

    Args:
        language: Language code to check.

    Returns:
        True if the language is supported.
    """
    return language in SUPPORTED_LANGUAGES
