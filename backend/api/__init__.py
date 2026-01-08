from fastapi import APIRouter

from .routes import chat, memories, screenshots, settings, conversations, visualization, profile, agent

router = APIRouter()

router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(memories.router, prefix="/memories", tags=["memories"])
router.include_router(screenshots.router, prefix="/screenshots", tags=["screenshots"])
router.include_router(settings.router, prefix="/settings", tags=["settings"])
router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
router.include_router(visualization.router, prefix="/visualization", tags=["visualization"])
router.include_router(profile.router, prefix="/profile", tags=["profile"])
router.include_router(agent.router, prefix="/agent", tags=["agent"])

__all__ = ["router"]
