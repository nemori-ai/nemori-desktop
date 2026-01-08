"""
Visualization API Routes
"""
from typing import Optional

from fastapi import APIRouter

from memory import VisualizationGenerator

router = APIRouter()


@router.get("/timeline")
async def get_timeline(
    days: int = 30,
    granularity: str = "day"
):
    """Get timeline data for episodic memories"""
    generator = VisualizationGenerator.get_instance()
    data = await generator.get_timeline_data(days=days, granularity=granularity)
    return data


@router.get("/heatmap")
async def get_heatmap(days: int = 90):
    """Get activity heatmap data"""
    generator = VisualizationGenerator.get_instance()
    data = await generator.get_activity_heatmap(days=days)
    return data


@router.get("/knowledge-graph")
async def get_knowledge_graph(limit: int = 100):
    """Get knowledge graph data from semantic memories"""
    generator = VisualizationGenerator.get_instance()
    data = await generator.get_knowledge_graph(limit=limit)
    return data


@router.get("/topics")
async def get_topics():
    """Get topic distribution data"""
    generator = VisualizationGenerator.get_instance()
    data = await generator.get_topic_distribution()
    return data


@router.get("/stats")
async def get_stats():
    """Get comprehensive memory statistics"""
    generator = VisualizationGenerator.get_instance()
    data = await generator.get_memory_stats()
    return data
