"""
Settings API Routes
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from storage.database import Database
from services.llm_service import LLMService
from config.settings import settings as app_settings

router = APIRouter()


class SettingUpdate(BaseModel):
    value: str


class LLMConfig(BaseModel):
    # Chat model config
    chat_api_key: Optional[str] = None
    chat_base_url: Optional[str] = None
    chat_model: Optional[str] = None
    # Embedding model config
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_model: Optional[str] = None


class AppSettingsUpdate(BaseModel):
    capture_interval_ms: Optional[int] = None
    batch_size: Optional[int] = None
    similarity_threshold: Optional[float] = None
    max_local_storage_mb: Optional[int] = None


@router.get("/")
async def get_all_settings():
    """Get all settings"""
    db = Database.get_instance()
    settings = await db.get_all_settings()

    # Don't expose full API keys
    for key_field in ["chat_api_key", "embedding_api_key", "openai_api_key"]:
        if key_field in settings and settings[key_field]:
            key = settings[key_field]
            settings[key_field] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"

    return {"settings": settings}


@router.get("/app")
async def get_app_settings():
    """Get application settings (non-sensitive)"""
    db = Database.get_instance()

    # Load overrides from database if they exist
    capture_interval = await db.get_setting("capture_interval_ms")
    batch_size = await db.get_setting("batch_size")
    similarity_threshold = await db.get_setting("similarity_threshold")
    max_storage = await db.get_setting("max_local_storage_mb")
    default_model = await db.get_setting("default_model")
    embedding_model = await db.get_setting("embedding_model")

    return {
        "capture_interval_ms": int(capture_interval) if capture_interval else app_settings.capture_interval_ms,
        "similarity_threshold": float(similarity_threshold) if similarity_threshold else app_settings.similarity_threshold,
        "batch_size": int(batch_size) if batch_size else app_settings.batch_size,
        "max_local_storage_mb": int(max_storage) if max_storage else app_settings.max_local_storage_mb,
        "default_model": default_model or app_settings.default_model,
        "embedding_model": embedding_model or app_settings.embedding_model,
        "data_dir": str(app_settings.data_dir)
    }


@router.put("/app")
async def update_app_settings(update: AppSettingsUpdate):
    """Update application settings"""
    db = Database.get_instance()

    if update.capture_interval_ms is not None:
        await db.set_setting("capture_interval_ms", str(update.capture_interval_ms))

    if update.batch_size is not None:
        await db.set_setting("batch_size", str(update.batch_size))

    if update.similarity_threshold is not None:
        await db.set_setting("similarity_threshold", str(update.similarity_threshold))

    if update.max_local_storage_mb is not None:
        await db.set_setting("max_local_storage_mb", str(update.max_local_storage_mb))

    return {"success": True}


# ==================== Language Settings ====================
# NOTE: These routes MUST be defined BEFORE the generic /{key} routes
# to avoid being caught by the wildcard pattern

class LanguageUpdate(BaseModel):
    language: str  # 'en' or 'zh'


@router.get("/language")
async def get_language():
    """Get current language setting"""
    db = Database.get_instance()
    language = await db.get_setting("language")
    llm = LLMService.get_instance()
    return {
        "language": language or llm.language or "en",
        "supported": ["en", "zh"]
    }


@router.put("/language")
async def set_language(update: LanguageUpdate):
    """Set language for UI and prompt injection"""
    from prompts.language import is_language_supported

    if not is_language_supported(update.language):
        return {"success": False, "error": f"Unsupported language: {update.language}"}

    db = Database.get_instance()
    await db.set_setting("language", update.language)

    # Update LLM service
    llm = LLMService.get_instance()
    llm.set_language(update.language)

    return {"success": True, "language": update.language}


# ==================== Generic Setting Routes ====================

@router.get("/{key}")
async def get_setting(key: str):
    """Get a specific setting"""
    db = Database.get_instance()
    value = await db.get_setting(key)

    # Don't expose the full API key
    if key == "openai_api_key" and value:
        value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"

    return {"key": key, "value": value}


@router.put("/{key}")
async def update_setting(key: str, update: SettingUpdate):
    """Update a setting"""
    db = Database.get_instance()
    await db.set_setting(key, update.value)

    # If updating LLM settings, update the service
    if key == "openai_api_key":
        llm = LLMService.get_instance()
        llm.set_api_key(update.value)
    elif key == "openai_base_url":
        llm = LLMService.get_instance()
        llm.set_base_url(update.value)
    elif key == "default_model":
        llm = LLMService.get_instance()
        llm.set_default_model(update.value)
    elif key == "embedding_model":
        llm = LLMService.get_instance()
        llm.set_embedding_model(update.value)

    return {"success": True}


@router.post("/llm")
async def configure_llm(config: LLMConfig):
    """Configure LLM settings"""
    db = Database.get_instance()
    llm = LLMService.get_instance()

    # Chat model configuration
    if config.chat_api_key is not None:
        api_key = config.chat_api_key.strip()
        if api_key:
            await db.set_setting("chat_api_key", api_key)
            llm.set_chat_api_key(api_key)
        else:
            # Empty string means delete
            await db.delete_setting("chat_api_key")
            llm.set_chat_api_key("")

    if config.chat_base_url:
        await db.set_setting("chat_base_url", config.chat_base_url)
        llm.set_chat_base_url(config.chat_base_url)

    if config.chat_model:
        await db.set_setting("chat_model", config.chat_model)
        llm.set_chat_model(config.chat_model)

    # Embedding model configuration
    if config.embedding_api_key is not None:
        api_key = config.embedding_api_key.strip()
        if api_key:
            await db.set_setting("embedding_api_key", api_key)
            llm.set_embedding_api_key(api_key)
        else:
            # Empty string means delete
            await db.delete_setting("embedding_api_key")
            llm.set_embedding_api_key("")

    if config.embedding_base_url:
        await db.set_setting("embedding_base_url", config.embedding_base_url)
        llm.set_embedding_base_url(config.embedding_base_url)

    if config.embedding_model:
        await db.set_setting("embedding_model", config.embedding_model)
        llm.set_embedding_model(config.embedding_model)

    return {"success": True, "configured": llm.is_configured()}


@router.get("/llm/status")
async def get_llm_status():
    """Get LLM service status"""
    llm = LLMService.get_instance()
    return {
        "configured": llm.is_configured()
    }


@router.post("/llm/test")
async def test_llm_connection():
    """Test LLM connection"""
    llm = LLMService.get_instance()
    try:
        success = await llm.test_connection()
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}
