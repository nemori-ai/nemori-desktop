"""
Profile Agent - Maintains a structured user profile with anti-truncation design

Key Design Principles:
1. Hierarchical structure with category limits
2. Importance scoring for automatic pruning
3. Rolling window updates (keep recent + important)
4. Compact storage format
5. Incremental updates instead of full rewrites
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from storage.database import Database
from services.llm_service import LLMService


# Profile category limits (prevents unbounded growth)
CATEGORY_LIMITS = {
    'interests': 10,        # Top 10 interests
    'skills': 10,           # Top 10 skills
    'preferences': 15,      # Top 15 preferences
    'habits': 8,            # Top 8 habits
    'facts': 20,            # Top 20 personal facts
    'goals': 5,             # Top 5 current goals
}

# Maximum total profile items
MAX_PROFILE_ITEMS = 60


class ProfileItem:
    """A single profile item with metadata"""

    def __init__(
        self,
        category: str,
        content: str,
        importance: float = 0.5,
        created_at: Optional[int] = None,
        last_seen: Optional[int] = None,
        occurrence_count: int = 1
    ):
        self.category = category
        self.content = content
        self.importance = importance
        self.created_at = created_at or int(datetime.now().timestamp() * 1000)
        self.last_seen = last_seen or self.created_at
        self.occurrence_count = occurrence_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            'category': self.category,
            'content': self.content,
            'importance': self.importance,
            'created_at': self.created_at,
            'last_seen': self.last_seen,
            'occurrence_count': self.occurrence_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileItem":
        return cls(
            category=data['category'],
            content=data['content'],
            importance=data.get('importance', 0.5),
            created_at=data.get('created_at'),
            last_seen=data.get('last_seen'),
            occurrence_count=data.get('occurrence_count', 1)
        )

    def calculate_score(self) -> float:
        """Calculate item score for pruning decisions"""
        now = datetime.now().timestamp() * 1000
        # Recency factor (decays over 30 days)
        age_days = (now - self.last_seen) / (1000 * 60 * 60 * 24)
        recency_score = max(0, 1 - (age_days / 30))

        # Frequency factor
        freq_score = min(1, self.occurrence_count / 5)

        # Combined score: importance * 0.5 + recency * 0.3 + frequency * 0.2
        return (self.importance * 0.5) + (recency_score * 0.3) + (freq_score * 0.2)


class ProfileAgent:
    """Agent for maintaining structured user profiles"""

    _instance: Optional["ProfileAgent"] = None

    def __init__(self):
        self.db = Database.get_instance()
        self.llm = LLMService.get_instance()
        self._profile_cache: Optional[Dict[str, List[ProfileItem]]] = None

    @classmethod
    def get_instance(cls) -> "ProfileAgent":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_profile(self) -> Dict[str, List[ProfileItem]]:
        """Get the current user profile"""
        if self._profile_cache is not None:
            return self._profile_cache

        # Load from database
        profile_json = await self.db.get_setting('user_profile')
        if profile_json:
            try:
                data = json.loads(profile_json)
                self._profile_cache = {
                    category: [ProfileItem.from_dict(item) for item in items]
                    for category, items in data.items()
                }
            except Exception as e:
                print(f"Failed to load profile: {e}")
                self._profile_cache = self._create_empty_profile()
        else:
            self._profile_cache = self._create_empty_profile()

        return self._profile_cache

    async def save_profile(self) -> None:
        """Save profile to database"""
        if self._profile_cache is None:
            return

        data = {
            category: [item.to_dict() for item in items]
            for category, items in self._profile_cache.items()
        }

        await self.db.set_setting('user_profile', json.dumps(data, ensure_ascii=False))

    def _create_empty_profile(self) -> Dict[str, List[ProfileItem]]:
        """Create an empty profile structure"""
        return {category: [] for category in CATEGORY_LIMITS.keys()}

    async def update_from_memories(self, recent_count: int = 20) -> Dict[str, Any]:
        """
        Update profile from recent semantic memories.

        This uses an incremental update approach:
        1. Get recent semantic memories
        2. Extract potential profile items
        3. Merge with existing profile (update or add)
        4. Prune to maintain limits
        """
        profile = await self.get_profile()

        # Get recent semantic memories
        semantic_memories = await self.db.get_semantic_memories(limit=recent_count)
        if not semantic_memories:
            return {'updated': 0, 'pruned': 0}

        # Extract profile items from memories
        new_items = await self._extract_profile_items(semantic_memories)
        if not new_items:
            return {'updated': 0, 'pruned': 0}

        # Merge with existing profile
        updated_count = 0
        for item in new_items:
            merged = self._merge_item(profile, item)
            if merged:
                updated_count += 1

        # Prune to maintain limits
        pruned_count = self._prune_profile(profile)

        # Save updated profile
        self._profile_cache = profile
        await self.save_profile()

        return {'updated': updated_count, 'pruned': pruned_count}

    async def _extract_profile_items(
        self,
        memories: List[Dict[str, Any]]
    ) -> List[ProfileItem]:
        """Extract profile items from semantic memories using LLM"""
        if not self.llm.is_configured():
            return self._heuristic_extract(memories)

        # Build compact memory summary
        memory_texts = []
        for mem in memories[:15]:  # Limit to avoid huge prompts
            mem_type = mem.get('type', 'unknown')
            content = mem.get('content', '')[:150]
            memory_texts.append(f"[{mem_type}] {content}")

        memories_block = "\n".join(memory_texts)

        prompt = f"""Analyze these user memories and extract profile items.

Memories:
{memories_block}

Extract items into these categories:
- interests: Things the user is interested in
- skills: Things the user knows or can do
- preferences: User preferences and tastes
- habits: Regular behaviors or patterns
- facts: Personal facts about the user
- goals: User's goals or aspirations

For each item, assign importance (0.0-1.0) based on how defining it is for the user.

Return JSON:
{{
  "items": [
    {{"category": "interests", "content": "...", "importance": 0.8}},
    ...
  ]
}}

Rules:
- Maximum 5 items total
- Each item content should be 10-30 words
- Focus on durable traits, not transient details
- Higher importance for unique/defining characteristics

Return only valid JSON."""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            result = self.llm.parse_json_response(response)

            if not result or 'items' not in result:
                return []

            items = []
            for item_data in result['items']:
                if not isinstance(item_data, dict):
                    continue
                category = item_data.get('category', '')
                if category not in CATEGORY_LIMITS:
                    continue
                items.append(ProfileItem(
                    category=category,
                    content=item_data.get('content', ''),
                    importance=float(item_data.get('importance', 0.5))
                ))

            return items

        except Exception as e:
            print(f"Error extracting profile items: {e}")
            return self._heuristic_extract(memories)

    def _heuristic_extract(self, memories: List[Dict[str, Any]]) -> List[ProfileItem]:
        """Fallback heuristic extraction without LLM"""
        items = []

        for mem in memories[:10]:
            mem_type = mem.get('type', '')
            content = mem.get('content', '')

            if mem_type == 'preference':
                items.append(ProfileItem(
                    category='preferences',
                    content=content[:100],
                    importance=mem.get('confidence', 0.5)
                ))
            elif mem_type == 'knowledge':
                # Categorize based on keywords
                lower = content.lower()
                if any(kw in lower for kw in ['like', 'enjoy', 'love', 'interest']):
                    items.append(ProfileItem(
                        category='interests',
                        content=content[:100],
                        importance=0.6
                    ))
                elif any(kw in lower for kw in ['know', 'can', 'skill', 'expert']):
                    items.append(ProfileItem(
                        category='skills',
                        content=content[:100],
                        importance=0.6
                    ))
                else:
                    items.append(ProfileItem(
                        category='facts',
                        content=content[:100],
                        importance=0.5
                    ))

        return items[:5]

    def _merge_item(
        self,
        profile: Dict[str, List[ProfileItem]],
        new_item: ProfileItem
    ) -> bool:
        """
        Merge a new item into the profile.
        Returns True if the profile was modified.
        """
        category_items = profile.get(new_item.category, [])

        # Check for similar existing item (simple substring match)
        new_lower = new_item.content.lower()
        for existing in category_items:
            existing_lower = existing.content.lower()

            # Check similarity
            if self._is_similar(new_lower, existing_lower):
                # Update existing item
                existing.last_seen = new_item.last_seen
                existing.occurrence_count += 1
                # Boost importance if seen multiple times
                existing.importance = min(1.0, existing.importance + 0.1)
                return True

        # Add new item
        category_items.append(new_item)
        profile[new_item.category] = category_items
        return True

    def _is_similar(self, text1: str, text2: str, threshold: float = 0.6) -> bool:
        """Check if two texts are similar using simple word overlap"""
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return False

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return (intersection / union) >= threshold

    def _prune_profile(self, profile: Dict[str, List[ProfileItem]]) -> int:
        """
        Prune profile to maintain limits.
        Returns number of items pruned.
        """
        pruned = 0

        for category, items in profile.items():
            limit = CATEGORY_LIMITS.get(category, 10)

            if len(items) > limit:
                # Sort by score (highest first)
                items.sort(key=lambda x: x.calculate_score(), reverse=True)
                # Keep top items
                pruned += len(items) - limit
                profile[category] = items[:limit]

        # Check total limit
        total_items = sum(len(items) for items in profile.values())
        if total_items > MAX_PROFILE_ITEMS:
            # Need to prune more - remove lowest scoring across all categories
            all_items = [
                (cat, i, item, item.calculate_score())
                for cat, items in profile.items()
                for i, item in enumerate(items)
            ]
            all_items.sort(key=lambda x: x[3])  # Sort by score

            items_to_remove = total_items - MAX_PROFILE_ITEMS
            for cat, idx, item, _ in all_items[:items_to_remove]:
                profile[cat].remove(item)
                pruned += 1

        return pruned

    async def get_profile_summary(self, max_chars: int = 800) -> str:
        """
        Get a compact profile summary suitable for LLM context.

        This generates a bounded string that won't cause truncation.
        """
        profile = await self.get_profile()

        # Build compact summary
        lines = []
        char_count = 0

        # Priority order for categories
        priority_order = ['interests', 'preferences', 'skills', 'habits', 'facts', 'goals']

        for category in priority_order:
            items = profile.get(category, [])
            if not items:
                continue

            # Sort by score and take top items
            sorted_items = sorted(items, key=lambda x: x.calculate_score(), reverse=True)

            # Build category line
            category_label = category.title()
            item_texts = [item.content for item in sorted_items[:5]]  # Max 5 per category in summary

            line = f"{category_label}: {'; '.join(item_texts)}"

            # Check if adding this would exceed limit
            if char_count + len(line) + 1 > max_chars:
                # Truncate line to fit
                remaining = max_chars - char_count - 1
                if remaining > 50:  # Only add if there's reasonable space
                    line = line[:remaining-3] + "..."
                    lines.append(line)
                break

            lines.append(line)
            char_count += len(line) + 1  # +1 for newline

        return "\n".join(lines) if lines else "No profile data yet."

    async def get_profile_for_context(self) -> Dict[str, Any]:
        """Get profile data formatted for chat context injection"""
        profile = await self.get_profile()

        summary = await self.get_profile_summary(max_chars=600)

        # Count stats
        total_items = sum(len(items) for items in profile.values())
        category_counts = {cat: len(items) for cat, items in profile.items() if items}

        return {
            'summary': summary,
            'total_items': total_items,
            'categories': category_counts,
            'last_updated': datetime.now().isoformat()
        }

    async def add_manual_item(
        self,
        category: str,
        content: str,
        importance: float = 0.8
    ) -> bool:
        """Manually add a profile item"""
        if category not in CATEGORY_LIMITS:
            return False

        profile = await self.get_profile()

        item = ProfileItem(
            category=category,
            content=content,
            importance=importance
        )

        self._merge_item(profile, item)
        self._prune_profile(profile)

        self._profile_cache = profile
        await self.save_profile()

        return True

    async def remove_item(self, category: str, content: str) -> bool:
        """Remove a profile item by content match"""
        profile = await self.get_profile()

        if category not in profile:
            return False

        items = profile[category]
        content_lower = content.lower()

        for item in items:
            if item.content.lower() == content_lower:
                items.remove(item)
                self._profile_cache = profile
                await self.save_profile()
                return True

        return False

    async def clear_profile(self) -> None:
        """Clear all profile data"""
        self._profile_cache = self._create_empty_profile()
        await self.save_profile()

    async def get_full_profile(self) -> Dict[str, Any]:
        """Get the full profile data (for UI display)"""
        profile = await self.get_profile()

        return {
            category: [
                {
                    **item.to_dict(),
                    'score': round(item.calculate_score(), 2)
                }
                for item in sorted(items, key=lambda x: x.calculate_score(), reverse=True)
            ]
            for category, items in profile.items()
        }
