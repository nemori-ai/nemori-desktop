"""
Visualization API Routes
"""
from typing import Optional

from fastapi import APIRouter

from agents.visualization_agent import VisualizationAgent

router = APIRouter()


@router.get("/timeline")
async def get_timeline(
    days: int = 30,
    granularity: str = "day"
):
    """Get timeline data for episodic memories"""
    agent = VisualizationAgent.get_instance()
    data = await agent.get_timeline_data(days=days, granularity=granularity)
    return data


@router.get("/heatmap")
async def get_heatmap(days: int = 90):
    """Get activity heatmap data"""
    agent = VisualizationAgent.get_instance()
    data = await agent.get_activity_heatmap(days=days)
    return data


@router.get("/knowledge-graph")
async def get_knowledge_graph(limit: int = 100):
    """Get knowledge graph data from semantic memories"""
    agent = VisualizationAgent.get_instance()
    data = await agent.get_knowledge_graph(limit=limit)
    return data


@router.get("/topics")
async def get_topics():
    """Get topic distribution data"""
    agent = VisualizationAgent.get_instance()
    data = await agent.get_topic_distribution()
    return data


@router.get("/stats")
async def get_stats():
    """Get comprehensive memory statistics"""
    agent = VisualizationAgent.get_instance()
    data = await agent.get_memory_stats()
    return data
