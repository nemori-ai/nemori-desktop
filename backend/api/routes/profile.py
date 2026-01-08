"""
Profile API Routes
"""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from memory import ProfileManager

router = APIRouter()


class AddItemRequest(BaseModel):
    category: str
    content: str
    importance: float = 0.8


class RemoveItemRequest(BaseModel):
    category: str
    content: str


@router.get("/")
async def get_profile():
    """Get the full user profile"""
    agent = ProfileManager.get_instance()
    profile = await agent.get_full_profile()
    return {"profile": profile}


@router.get("/summary")
async def get_profile_summary(max_chars: int = 800):
    """Get a compact profile summary"""
    agent = ProfileManager.get_instance()
    summary = await agent.get_profile_summary(max_chars=max_chars)
    return {"summary": summary}


@router.get("/context")
async def get_profile_for_context():
    """Get profile formatted for chat context"""
    agent = ProfileManager.get_instance()
    context = await agent.get_profile_for_context()
    return context


@router.post("/update")
async def update_profile_from_memories(recent_count: int = 20):
    """Update profile from recent semantic memories"""
    agent = ProfileManager.get_instance()
    result = await agent.update_from_memories(recent_count=recent_count)
    return {"success": True, **result}


@router.post("/add")
async def add_profile_item(request: AddItemRequest):
    """Manually add a profile item"""
    agent = ProfileManager.get_instance()
    success = await agent.add_manual_item(
        category=request.category,
        content=request.content,
        importance=request.importance
    )
    return {"success": success}


@router.post("/remove")
async def remove_profile_item(request: RemoveItemRequest):
    """Remove a profile item"""
    agent = ProfileManager.get_instance()
    success = await agent.remove_item(
        category=request.category,
        content=request.content
    )
    return {"success": success}


@router.delete("/")
async def clear_profile():
    """Clear all profile data"""
    agent = ProfileManager.get_instance()
    await agent.clear_profile()
    return {"success": True}
