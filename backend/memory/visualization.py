"""
Visualization Generator - Generates visualization data from memories

This is a fixed workflow that transforms memory data into visualization-ready formats.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict

from storage.database import Database
from storage.vector_store import VectorStore


class VisualizationGenerator:
    """Generator for creating visualization data from memories"""

    _instance: Optional["VisualizationGenerator"] = None

    def __init__(self):
        self.db = Database.get_instance()
        self.vector_store = VectorStore.get_instance()

    @classmethod
    def get_instance(cls) -> "VisualizationGenerator":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_timeline_data(
        self,
        days: int = 30,
        granularity: str = "day"
    ) -> Dict[str, Any]:
        """
        Generate timeline data for episodic memories.

        Args:
            days: Number of days to look back
            granularity: "hour", "day", or "week"

        Returns:
            Timeline data with events grouped by time period
        """
        # Get episodic memories from the specified time range
        memories = await self.db.get_episodic_memories(limit=500)

        cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        memories = [m for m in memories if m.get('start_time', 0) >= cutoff_time]

        # Group by time period
        timeline = defaultdict(list)

        for memory in memories:
            start_time = memory.get('start_time', 0)
            dt = datetime.fromtimestamp(start_time / 1000)

            if granularity == "hour":
                key = dt.strftime("%Y-%m-%d %H:00")
            elif granularity == "week":
                # Get the Monday of the week
                monday = dt - timedelta(days=dt.weekday())
                key = monday.strftime("%Y-%m-%d")
            else:  # day
                key = dt.strftime("%Y-%m-%d")

            timeline[key].append({
                'id': memory['id'],
                'title': memory.get('title', ''),
                'content': memory.get('content', '')[:200],
                'start_time': start_time,
                'end_time': memory.get('end_time', start_time),
                'urls': memory.get('urls', []),
                'screenshot_count': len(memory.get('screenshot_ids', [])) if memory.get('screenshot_ids') else 0
            })

        # Sort events within each time period
        for key in timeline:
            timeline[key].sort(key=lambda x: x['start_time'])

        # Convert to sorted list
        sorted_timeline = sorted(timeline.items(), key=lambda x: x[0], reverse=True)

        return {
            'timeline': [
                {'date': date, 'events': events}
                for date, events in sorted_timeline
            ],
            'total_events': len(memories),
            'date_range': {
                'start': (datetime.now() - timedelta(days=days)).isoformat(),
                'end': datetime.now().isoformat()
            }
        }

    async def get_activity_heatmap(
        self,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Generate activity heatmap data (GitHub-style contribution graph).

        Returns daily activity counts for the specified time range.
        """
        memories = await self.db.get_episodic_memories(limit=1000)

        cutoff_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        # Count activities per day
        daily_counts = defaultdict(int)

        for memory in memories:
            start_time = memory.get('start_time', 0)
            if start_time >= cutoff_time:
                date_key = datetime.fromtimestamp(start_time / 1000).strftime("%Y-%m-%d")
                daily_counts[date_key] += 1

        # Fill in missing days with 0
        heatmap = []
        current = datetime.now() - timedelta(days=days)
        while current <= datetime.now():
            date_key = current.strftime("%Y-%m-%d")
            heatmap.append({
                'date': date_key,
                'count': daily_counts.get(date_key, 0),
                'weekday': current.weekday()
            })
            current += timedelta(days=1)

        # Calculate statistics
        counts = [h['count'] for h in heatmap]
        max_count = max(counts) if counts else 0
        total_count = sum(counts)
        active_days = sum(1 for c in counts if c > 0)

        return {
            'heatmap': heatmap,
            'stats': {
                'total_memories': total_count,
                'active_days': active_days,
                'max_daily': max_count,
                'average_daily': round(total_count / len(heatmap), 2) if heatmap else 0
            }
        }

    async def get_knowledge_graph(
        self,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Generate knowledge graph data from semantic memories.

        Returns nodes (memories) and edges (relationships based on similarity).
        """
        semantic_memories = await self.db.get_semantic_memories(limit=limit)

        if not semantic_memories:
            return {'nodes': [], 'edges': [], 'clusters': []}

        # Create nodes
        nodes = []
        node_map = {}

        for i, memory in enumerate(semantic_memories):
            node = {
                'id': memory['id'],
                'label': memory['content'][:50] + ('...' if len(memory['content']) > 50 else ''),
                'content': memory['content'],
                'type': memory.get('type', 'knowledge'),
                'confidence': memory.get('confidence', 0.8),
                'created_at': memory.get('created_at', 0),
                'size': 10 + int(memory.get('confidence', 0.8) * 20)
            }
            nodes.append(node)
            node_map[memory['id']] = i

        # Create edges based on related_memory_ids
        edges = []
        edge_set = set()

        for memory in semantic_memories:
            source_id = memory['id']
            related_ids = memory.get('related_memory_ids', [])

            if isinstance(related_ids, str):
                try:
                    import json
                    related_ids = json.loads(related_ids)
                except:
                    related_ids = []

            for target_id in related_ids:
                if target_id in node_map and source_id != target_id:
                    # Avoid duplicate edges
                    edge_key = tuple(sorted([source_id, target_id]))
                    if edge_key not in edge_set:
                        edge_set.add(edge_key)
                        edges.append({
                            'source': source_id,
                            'target': target_id,
                            'strength': 0.5
                        })

        # Group nodes by type for clusters
        clusters = defaultdict(list)
        for node in nodes:
            clusters[node['type']].append(node['id'])

        return {
            'nodes': nodes,
            'edges': edges,
            'clusters': [
                {'type': t, 'node_ids': ids}
                for t, ids in clusters.items()
            ]
        }

    async def get_topic_distribution(self) -> Dict[str, Any]:
        """
        Analyze topic distribution across semantic memories.
        Uses the 8 life categories: career, finance, health, family, social, growth, leisure, spirit
        """
        semantic_memories = await self.db.get_semantic_memories(limit=500)

        # 8 life categories
        life_categories = ['career', 'finance', 'health', 'family', 'social', 'growth', 'leisure', 'spirit']

        # Count by category (type field)
        category_counts = {cat: 0 for cat in life_categories}
        for memory in semantic_memories:
            mem_type = memory.get('type', 'unknown')
            if mem_type in category_counts:
                category_counts[mem_type] += 1
            # Handle legacy types by mapping to closest category
            elif mem_type == 'knowledge':
                category_counts['growth'] += 1
            elif mem_type == 'preference':
                category_counts['leisure'] += 1

        # Extract simple topic keywords from content
        word_freq = defaultdict(int)
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                     'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                     'through', 'during', 'before', 'after', 'above', 'below',
                     'between', 'under', 'again', 'further', 'then', 'once',
                     'and', 'but', 'or', 'nor', 'so', 'yet', 'both', 'either',
                     'neither', 'not', 'only', 'own', 'same', 'than', 'too',
                     'very', 'just', 'user', 'prefers', 'likes', 'enjoys', 'that',
                     '的', '是', '在', '了', '和', '有', '我', '他', '她', '它',
                     '这', '那', '们', '会', '能', '也', '就', '都', '很', '不'}

        for memory in semantic_memories:
            content = memory.get('content', '').lower()
            words = content.split()
            for word in words:
                # Clean word
                word = ''.join(c for c in word if c.isalnum())
                if len(word) > 2 and word not in stopwords:
                    word_freq[word] += 1

        # Get top keywords
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:20]

        return {
            'category_distribution': category_counts,
            'type_distribution': category_counts,  # Keep for backward compatibility
            'top_keywords': [
                {'word': word, 'count': count}
                for word, count in top_keywords
            ],
            'total_memories': len(semantic_memories)
        }

    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive memory statistics.
        Uses the 8 life categories for semantic memory breakdown.
        """
        episodic = await self.db.get_episodic_memories(limit=1000)
        semantic = await self.db.get_semantic_memories(limit=1000)

        # Time-based stats for episodic
        now = datetime.now().timestamp() * 1000
        day_ago = now - (24 * 60 * 60 * 1000)
        week_ago = now - (7 * 24 * 60 * 60 * 1000)
        month_ago = now - (30 * 24 * 60 * 60 * 1000)

        episodic_today = sum(1 for m in episodic if m.get('start_time', 0) >= day_ago)
        episodic_week = sum(1 for m in episodic if m.get('start_time', 0) >= week_ago)
        episodic_month = sum(1 for m in episodic if m.get('start_time', 0) >= month_ago)

        semantic_today = sum(1 for m in semantic if m.get('created_at', 0) >= day_ago)
        semantic_week = sum(1 for m in semantic if m.get('created_at', 0) >= week_ago)

        # Category breakdown for semantic (8 life categories)
        life_categories = ['career', 'finance', 'health', 'family', 'social', 'growth', 'leisure', 'spirit']
        category_counts = {cat: 0 for cat in life_categories}
        for m in semantic:
            mem_type = m.get('type', 'unknown')
            if mem_type in category_counts:
                category_counts[mem_type] += 1
            # Handle legacy types
            elif mem_type == 'knowledge':
                category_counts['growth'] += 1
            elif mem_type == 'preference':
                category_counts['leisure'] += 1

        # Average confidence
        confidences = [m.get('confidence', 0.8) for m in semantic]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            'episodic': {
                'total': len(episodic),
                'today': episodic_today,
                'this_week': episodic_week,
                'this_month': episodic_month
            },
            'semantic': {
                'total': len(semantic),
                'today': semantic_today,
                'this_week': semantic_week,
                'categories': category_counts,
                # Keep legacy fields for backward compatibility
                'knowledge': category_counts.get('growth', 0),
                'preference': category_counts.get('leisure', 0),
                'avg_confidence': round(avg_confidence, 2)
            },
            'growth': {
                'weekly_episodic': episodic_week,
                'weekly_semantic': semantic_week
            }
        }


# Backward compatibility alias
VisualizationAgent = VisualizationGenerator
