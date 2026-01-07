"""
Pydantic schemas for API data validation
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ==================== Chat Models ====================

class ChatRequest(BaseModel):
    content: str
    conversation_id: Optional[str] = None
    model: Optional[str] = None
    use_memory: bool = True


class ChatResponse(BaseModel):
    success: bool
    message: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    error: Optional[str] = None


class MessageModel(BaseModel):
    id: str
    role: str
    content: str
    timestamp: int
    conversation_id: str
    metadata: Optional[Dict[str, Any]] = None


# ==================== Conversation Models ====================

class ConversationModel(BaseModel):
    id: str
    title: str
    created_at: int
    updated_at: int


class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


class UpdateConversationRequest(BaseModel):
    title: str


# ==================== Memory Models ====================

class EpisodicMemoryModel(BaseModel):
    id: str
    title: str
    content: str
    start_time: int
    end_time: int
    participants: Optional[List[str]] = None
    urls: Optional[List[str]] = None
    screenshot_ids: Optional[List[str]] = None
    embedding_id: Optional[str] = None
    created_at: int


class SemanticMemoryModel(BaseModel):
    id: str
    type: str  # 'career', 'finance', 'health', 'family', 'social', 'growth', 'leisure', 'spirit'
    content: str
    confidence: float = 0.5
    source: Optional[str] = None
    embedding_id: Optional[str] = None
    created_at: int


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10
    memory_type: Optional[str] = None


class MemorySearchResult(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None


# ==================== Screenshot Models ====================

class ScreenshotModel(BaseModel):
    id: str
    timestamp: int
    file_path: str
    window_title: Optional[str] = None
    app_name: Optional[str] = None
    url: Optional[str] = None
    phash: Optional[str] = None
    processed: bool = False
    created_at: int


class CaptureStatusModel(BaseModel):
    is_capturing: bool
    interval_ms: int
    screenshots_path: str


class CaptureOptionsModel(BaseModel):
    interval_ms: Optional[int] = None


# ==================== Settings Models ====================

class SettingUpdateRequest(BaseModel):
    value: str


class LLMConfigRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    embedding_model: Optional[str] = None


class AppSettingsModel(BaseModel):
    capture_interval_ms: int
    similarity_threshold: float
    batch_size: int
    max_local_storage_mb: int
    default_model: str
    embedding_model: str
    data_dir: str


# ==================== Stats Models ====================

class MemoryStatsModel(BaseModel):
    screenshots_count: int
    messages_count: int
    episodic_memories_count: int
    semantic_memories_count: int
    conversations_count: int
    vector_embeddings: int
    pending_batch: int
