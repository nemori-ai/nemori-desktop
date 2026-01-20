"""
LLM Service for chat and embedding generation
"""
import asyncio
import json
import re
import sys
import os
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI

from config.settings import settings
from storage.database import Database

# Ensure UTF-8 encoding for all I/O operations
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # Python < 3.7

if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Set environment variable for httpx/openai client
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')


# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 30.0  # seconds


class LLMService:
    """Service for LLM interactions (chat, embeddings)"""

    _instance: Optional["LLMService"] = None

    def __init__(self):
        # Chat model configuration
        self._chat_client: Optional[AsyncOpenAI] = None
        self._chat_api_key: str = ""
        self._chat_base_url: str = "https://openrouter.ai/api/v1"
        self._chat_model: str = "google/gemini-3-flash-preview"

        # Embedding model configuration
        self._embedding_client: Optional[AsyncOpenAI] = None
        self._embedding_api_key: str = ""
        self._embedding_base_url: str = "https://openrouter.ai/api/v1"
        self._embedding_model: str = "google/gemini-embedding-001"
        self._embedding_dimension: int = settings.embedding_dimension

        # Language configuration for prompt injection
        self._language: str = "en"  # Default to English

    @classmethod
    def get_instance(cls) -> "LLMService":
        if cls._instance is None:
            cls._instance = cls()
            # Note: async loading will be done via load_from_database()
            cls._instance._load_config_sync()
        return cls._instance

    def _load_config_sync(self) -> None:
        """Load configuration from environment settings (sync, used at init)"""
        # Try to load from environment first (legacy support)
        if settings.openai_api_key:
            self._chat_api_key = settings.openai_api_key
            self._embedding_api_key = settings.openai_api_key

        self._init_clients()

    async def load_from_database(self) -> None:
        """Load configuration from database (async, call after DB init)"""
        db = Database.get_instance()

        # Load chat model settings
        chat_api_key = await db.get_setting("chat_api_key")
        if chat_api_key:
            self._chat_api_key = chat_api_key
        else:
            # Fallback to legacy key
            legacy_key = await db.get_setting("openai_api_key")
            if legacy_key:
                self._chat_api_key = legacy_key

        chat_base_url = await db.get_setting("chat_base_url")
        if chat_base_url:
            self._chat_base_url = chat_base_url
        else:
            # Fallback to legacy url
            legacy_url = await db.get_setting("openai_base_url")
            if legacy_url:
                self._chat_base_url = legacy_url

        chat_model = await db.get_setting("chat_model")
        if chat_model:
            self._chat_model = chat_model
        else:
            # Fallback to legacy model
            legacy_model = await db.get_setting("default_model")
            if legacy_model:
                self._chat_model = legacy_model

        # Load embedding model settings
        embedding_api_key = await db.get_setting("embedding_api_key")
        if embedding_api_key:
            self._embedding_api_key = embedding_api_key
        else:
            # Fallback to chat api key if not set
            self._embedding_api_key = self._chat_api_key

        embedding_base_url = await db.get_setting("embedding_base_url")
        if embedding_base_url:
            self._embedding_base_url = embedding_base_url

        embedding_model = await db.get_setting("embedding_model")
        if embedding_model:
            self._embedding_model = embedding_model

        # Load language setting
        language = await db.get_setting("language")
        if language:
            self._language = language

        # Reinitialize clients with loaded settings
        self._init_clients()

        print(f"LLM service loaded from database. Chat configured: {self.is_chat_configured()}, Embedding configured: {self.is_embedding_configured()}, Language: {self._language}")

    def _init_clients(self) -> None:
        """Initialize OpenAI clients for chat and embedding"""
        # Initialize chat client
        if self._chat_api_key:
            self._chat_client = AsyncOpenAI(
                api_key=self._chat_api_key,
                base_url=self._chat_base_url
            )
        else:
            self._chat_client = None

        # Initialize embedding client
        if self._embedding_api_key:
            self._embedding_client = AsyncOpenAI(
                api_key=self._embedding_api_key,
                base_url=self._embedding_base_url
            )
        else:
            self._embedding_client = None

    def is_chat_configured(self) -> bool:
        """Check if chat model is configured"""
        return self._chat_client is not None and bool(self._chat_api_key)

    def is_embedding_configured(self) -> bool:
        """Check if embedding model is configured"""
        return self._embedding_client is not None and bool(self._embedding_api_key)

    def is_configured(self) -> bool:
        """Check if LLM service is configured (at least chat model)"""
        return self.is_chat_configured()

    # Public properties for accessing chat model config
    @property
    def model(self) -> str:
        """Get the current chat model name"""
        return self._chat_model

    @property
    def api_key(self) -> str:
        """Get the current chat API key"""
        return self._chat_api_key

    @property
    def base_url(self) -> str:
        """Get the current chat base URL"""
        return self._chat_base_url

    @property
    def language(self) -> str:
        """Get the current language setting"""
        return self._language

    def set_language(self, language: str) -> None:
        """Set language for prompt injection"""
        self._language = language

    # Chat model setters
    def set_chat_api_key(self, api_key: str) -> None:
        """Set chat API key and reinitialize client"""
        self._chat_api_key = api_key
        self._init_clients()

    def set_chat_base_url(self, base_url: str) -> None:
        """Set chat base URL and reinitialize client"""
        self._chat_base_url = base_url
        self._init_clients()

    def set_chat_model(self, model: str) -> None:
        """Set chat model"""
        self._chat_model = model

    # Embedding model setters
    def set_embedding_api_key(self, api_key: str) -> None:
        """Set embedding API key and reinitialize client"""
        self._embedding_api_key = api_key
        self._init_clients()

    def set_embedding_base_url(self, base_url: str) -> None:
        """Set embedding base URL and reinitialize client"""
        self._embedding_base_url = base_url
        self._init_clients()

    def set_embedding_model(self, model: str) -> None:
        """Set embedding model"""
        self._embedding_model = model

    # Legacy setters (for backward compatibility)
    def set_api_key(self, api_key: str) -> None:
        """Set API key (legacy - sets both chat and embedding)"""
        self._chat_api_key = api_key
        self._embedding_api_key = api_key
        self._init_clients()

    def set_base_url(self, base_url: str) -> None:
        """Set base URL (legacy - sets chat only)"""
        self._chat_base_url = base_url
        self._init_clients()

    def set_default_model(self, model: str) -> None:
        """Set default chat model (legacy)"""
        self._chat_model = model

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
        retries: int = MAX_RETRIES
    ) -> str:
        """Send chat completion request with retry logic"""
        if not self._chat_client:
            raise ValueError("Chat model not configured. Please set your Chat API key.")

        kwargs = {
            "model": model or self._chat_model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        if response_format:
            kwargs["response_format"] = response_format

        last_error = None
        delay = INITIAL_RETRY_DELAY

        for attempt in range(retries):
            try:
                response = await self._chat_client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""

                # If response_format is json_object, validate it's actual JSON
                if response_format and response_format.get("type") == "json_object":
                    if not content.strip():
                        raise ValueError("Empty JSON response")
                    # Try to parse to validate
                    json.loads(content)

                return content

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Don't retry on authentication errors
                if "401" in error_msg or "unauthorized" in error_msg or "invalid api key" in error_msg:
                    raise

                # Retry on rate limits, timeouts, and empty responses
                if attempt < retries - 1:
                    print(f"LLM request failed (attempt {attempt + 1}/{retries}): {e}")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY)  # Exponential backoff
                else:
                    print(f"LLM request failed after {retries} attempts: {e}")

        raise last_error or ValueError("LLM request failed")

    def parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON from LLM response with fallback extraction"""
        if not response or not response.strip():
            return None

        # Try direct parsing first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in the response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> str:
        """Simple text generation wrapper around chat.

        Args:
            prompt: The user prompt to generate a response for
            system_prompt: Optional system message for context
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        return await self.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

    async def chat_with_images(
        self,
        prompt: str,
        image_urls: List[str],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """Send multimodal chat request with images"""
        if not self._chat_client:
            raise ValueError("Chat model not configured. Please set your Chat API key.")

        # Build content parts
        content_parts = [{"type": "text", "text": prompt}]
        for url in image_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url}
            })

        messages = [{"role": "user", "content": content_parts}]

        return await self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion response"""
        if not self._chat_client:
            raise ValueError("Chat model not configured. Please set your Chat API key.")

        stream = await self._chat_client.chat.completions.create(
            model=model or self._chat_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        retries: int = MAX_RETRIES
    ) -> List[List[float]]:
        """Generate embeddings for texts with retry logic"""
        if not self._embedding_client:
            raise ValueError("Embedding model not configured. Please set your Embedding API key.")

        last_error = None
        delay = INITIAL_RETRY_DELAY

        for attempt in range(retries):
            try:
                response = await self._embedding_client.embeddings.create(
                    model=model or self._embedding_model,
                    input=texts
                )

                embeddings = [data.embedding for data in response.data]

                # Only truncate if dimension is explicitly configured (non-zero)
                # Setting embedding_dimension to 0 means auto-adapt to model's native dimension
                if self._embedding_dimension > 0 and len(embeddings[0]) > self._embedding_dimension:
                    embeddings = [emb[:self._embedding_dimension] for emb in embeddings]

                return embeddings

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Don't retry on authentication errors
                if "401" in error_msg or "unauthorized" in error_msg or "invalid api key" in error_msg:
                    raise

                # Retry on rate limits, timeouts, and network errors
                if attempt < retries - 1:
                    print(f"Embedding request failed (attempt {attempt + 1}/{retries}): {e}")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, MAX_RETRY_DELAY)
                else:
                    print(f"Embedding request failed after {retries} attempts: {e}")

        raise last_error or ValueError("Embedding request failed")

    async def embed_single(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate embedding for a single text"""
        embeddings = await self.embed([text], model)
        return embeddings[0]

    async def test_connection(self) -> bool:
        """Test connection to LLM service (tests chat model)"""
        if not self._chat_client:
            raise ValueError("Chat model not configured")

        try:
            response = await self._chat_client.chat.completions.create(
                model=self._chat_model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return bool(response.choices[0].message.content)
        except Exception as e:
            raise ValueError(f"Connection test failed: {str(e)}")

    # ==================== Memory Analysis Methods ====================

    async def analyze_for_episodic_memory(
        self,
        content: str
    ) -> Optional[Dict[str, Any]]:
        """Analyze content to extract episodic memory elements"""
        if not self._chat_client:
            return None

        prompt = f"""Analyze the following content and extract key episodic memory elements:

Content: {content}

Return a JSON object with:
- title: A brief title for this memory (max 50 chars)
- summary: A concise summary of what happened (max 200 chars)
- entities: Array of key entities mentioned (people, places, things)
- timeframe: Any time references mentioned (optional)

Return only valid JSON, no markdown."""

        try:
            response = await self.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            import json
            return json.loads(response)
        except Exception as e:
            print(f"Episodic analysis failed: {e}")
            return None

    async def analyze_for_semantic_memory(
        self,
        content: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Analyze content to extract semantic memories"""
        if not self._chat_client:
            return None

        prompt = f"""Analyze the following content and extract semantic memories (facts, knowledge, or user preferences):

Content: {content}

Return a JSON array of objects, each with:
- type: "knowledge" or "preference"
- content: The extracted fact or preference (max 100 chars)
- confidence: A number 0-1 indicating confidence

Return only valid JSON array, no markdown. Return empty array if nothing to extract."""

        try:
            response = await self.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            import json
            return json.loads(response)
        except Exception as e:
            print(f"Semantic analysis failed: {e}")
            return None

    async def generate_conversation_title(self, messages: List[Dict[str, str]]) -> str:
        """Generate a title for a conversation based on its messages"""
        if not self._chat_client or not messages:
            return "New Conversation"

        # Take first few messages for context
        context = "\n".join([
            f"{m['role']}: {m['content'][:300]}"
            for m in messages[:3]
        ])

        prompt = f"""Generate a short, descriptive title for this conversation (max 40 characters).

Rules:
- Focus on the main topic or question
- Be specific and descriptive
- Do NOT start with "Conversation about" or similar phrases
- Use title case
- No quotes or punctuation at the end

Conversation:
{context}

Title:"""

        try:
            title = await self.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=30
            )
            # Clean up the title
            title = title.strip().strip('"').strip("'").strip()
            # Remove common prefixes
            for prefix in ["Title:", "Conversation:", "Topic:"]:
                if title.lower().startswith(prefix.lower()):
                    title = title[len(prefix):].strip()
            return title[:50] if title else "New Conversation"
        except Exception:
            return "New Conversation"
