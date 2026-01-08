"""
Nemori Memory Module - Fixed workflows for memory generation and management

This module contains the memory processing pipelines:
- EpisodicProcessor: Creates narrative episodic memories from events
- SemanticExtractor: Extracts life insights into 8 categories
- ProfileManager: Maintains structured user profiles
- EventSegmenter: Determines memory boundaries from event sequences
- VisualizationGenerator: Generates visualization data from memories
- MemoryOrchestrator: Coordinates batch processing and memory generation
"""

from .episodic import EpisodicProcessor
from .semantic import SemanticExtractor, SEMANTIC_CATEGORIES
from .profile import ProfileManager, ProfileItem, CATEGORY_LIMITS
from .segmentation import EventSegmenter, EventSegmentation
from .visualization import VisualizationGenerator
from .manager import MemoryOrchestrator

__all__ = [
    # Core processors
    'EpisodicProcessor',
    'SemanticExtractor',
    'ProfileManager',
    'EventSegmenter',
    'VisualizationGenerator',
    'MemoryOrchestrator',
    # Data classes
    'ProfileItem',
    'EventSegmentation',
    # Constants
    'SEMANTIC_CATEGORIES',
    'CATEGORY_LIMITS',
]
