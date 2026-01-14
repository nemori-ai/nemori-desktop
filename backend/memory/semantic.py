"""
Semantic Extractor - Extracts life insights from message batches into 8 categories

This is a fixed workflow that transforms event data into categorized semantic memories.
"""

import uuid
import json
import math
from datetime import datetime
from typing import Optional, List, Dict, Any

from storage.database import Database
from storage.vector_store import VectorStore
from services.llm_service import LLMService
from prompts import SEMANTIC_CATEGORIES, inject_language
from prompts.semantic_prompts import (
    get_consolidation_decision_prompt,
    get_reconstruction_prompt,
    get_calibration_prompt,
)


class SemanticExtractor:
    """Extractor for semantic memories across 8 life categories"""

    def __init__(self):
        self.db = Database.get_instance()
        self.vector_store = VectorStore.get_instance()
        self.llm = LLMService.get_instance()

    async def create_from_segment(
        self,
        message_ids: List[str],
        summary: Optional[str] = None,
        top_n: int = 5,
        source_app: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Create semantic memories from a message segment"""
        try:
            # Load messages
            messages = await self.db.get_messages_by_ids(message_ids)
            if not messages:
                return []

            # Build session summary
            session_summary = summary if summary and summary.strip() else self._build_fallback_summary(messages)

            # Step 1: Find similar semantic memories by summary embedding
            summary_embedding = await self.llm.embed_single(session_summary)
            similar = await self._find_similar_semantic_memories(summary_embedding, top_n)

            # Step 2: Reconstruct detailed scene
            reconstruction = await self._reconstruct_details(session_summary, similar, messages)

            # Step 3: Calibrate with original messages to extract knowledge/preferences
            calibration = await self._calibrate_with_original(
                reconstruction.get('reconstructed_details', session_summary),
                messages
            )

            # If LLM returns nothing, use heuristics
            has_items = any(calibration.get(cat, []) for cat in SEMANTIC_CATEGORIES.keys())
            if not has_items:
                fallback = self._extract_heuristic_items(messages, session_summary)
                has_fallback = any(fallback.get(cat, []) for cat in SEMANTIC_CATEGORIES.keys())
                if has_fallback:
                    print('SemanticExtractor: using heuristic fallback')
                    calibration = fallback
                    calibration['__fallback'] = True
                else:
                    print('SemanticExtractor: no semantic items extracted')
                    return []

            # Generate and save individual semantic memories
            all_memories = []
            is_fallback = calibration.get('__fallback', False)
            confidence = 0.6 if is_fallback else 0.8

            # Save items for each category
            for category in SEMANTIC_CATEGORIES.keys():
                for item in calibration.get(category, []):
                    try:
                        memory = await self._consolidate_semantic_item({
                            'type': category,
                            'content': item,
                            'context': reconstruction.get('reconstructed_details', ''),
                            'source_summary': session_summary,
                            'source_message_ids': message_ids,
                            'confidence': confidence,
                            'source_app': source_app or ['nemori']
                        })
                        if memory:
                            all_memories.append(memory)
                    except Exception as e:
                        print(f"Failed to create {category} memory: {e}")

            print(f"Created {len(all_memories)} semantic memories")
            return all_memories

        except Exception as e:
            print(f"Error creating semantic memory: {e}")
            return []

    async def _consolidate_semantic_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Consolidate a semantic item with existing similar items"""
        # Generate embedding for the item
        item_embedding = await self.llm.embed_single(item['content'])

        # Search for related concepts
        candidates = await self._find_similar_semantic_memories(item_embedding, 5)

        # Decide on consolidation strategy
        decision = await self._decide_on_consolidation(item, candidates)

        content_to_save = decision.get('new_content', item['content']) if decision.get('decision') == 'MERGE' else item['content']
        final_embedding = item_embedding if content_to_save == item['content'] else await self.llm.embed_single(content_to_save)

        # Collect source apps from related memories
        all_source_apps = set(item.get('source_app', ['nemori']))
        if decision.get('decision') in ('MERGE', 'CONFLICT_DELETE') and decision.get('target_ids'):
            for candidate in candidates:
                if candidate['id'] in decision['target_ids']:
                    all_source_apps.update(candidate.get('source_app', []))

        # Execute decision
        if decision.get('decision') in ('MERGE', 'CONFLICT_DELETE') and decision.get('target_ids'):
            print(f"Executing {decision['decision']}: Deleting old memories {decision['target_ids']}")
            for old_id in decision['target_ids']:
                await self.db.delete_semantic_memory(old_id)
                self.vector_store.delete([old_id])

        # Create new memory
        memory_id = str(uuid.uuid4())
        memory = {
            'id': memory_id,
            'created_at': int(datetime.now().timestamp() * 1000),
            'type': item['type'],
            'content': content_to_save,
            'context': item.get('context', ''),
            'source_summary': item.get('source_summary', ''),
            'source_message_ids': item.get('source_message_ids', []),
            'related_memory_ids': [c['id'] for c in candidates],
            'confidence': item.get('confidence', 0.8),
            'embedding_id': memory_id,
            'source_app': list(all_source_apps)
        }

        # Save to vector store
        self.vector_store.add_embedding(
            id=memory_id,
            embedding=final_embedding,
            metadata={
                'type': 'semantic',
                'memory_type': item['type'],
                'confidence': item.get('confidence', 0.8),
                'created_at': memory['created_at']
            },
            document=content_to_save
        )

        # Save to database
        await self.db.save_semantic_memory(memory)
        print(f"Semantic memory saved (Decision: {decision.get('decision', 'NEW')}): {content_to_save[:50]}...")

        return memory

    async def _decide_on_consolidation(
        self,
        new_item: Dict[str, Any],
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Decide how to consolidate a new item with existing ones"""
        if not self.llm.is_configured():
            return {'decision': 'NEW', 'reason': 'LLM not configured'}

        if not candidates:
            return {'decision': 'NEW', 'reason': 'No similar memories found'}

        candidates_summary = "\n".join([
            f"""---
Candidate #{i+1} (ID: {c['id']})
Type: {c['type']}
Content: "{c['content']}"
---"""
            for i, c in enumerate(candidates)
        ])

        # Get language from LLM service settings
        language = getattr(self.llm, 'language', None)
        prompt = get_consolidation_decision_prompt(
            new_item_type=new_item['type'],
            new_item_content=new_item['content'],
            candidates_summary=candidates_summary
        )
        prompt = inject_language(prompt, language)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            decision = self.llm.parse_json_response(response)
            if decision and decision.get('decision') in ('NEW', 'MERGE', 'CONFLICT_DELETE'):
                return decision
            return {'decision': 'NEW', 'reason': 'Invalid decision format'}
        except Exception as e:
            print(f"Error in consolidation decision: {e}")
            return {'decision': 'NEW', 'reason': 'Decision failed'}

    async def _find_similar_semantic_memories(
        self,
        embedding: List[float],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """Find similar semantic memories using vector search"""
        try:
            results = self.vector_store.query(
                query_embedding=embedding,
                n_results=top_n,
                where={'type': 'semantic'}
            )

            memories = []
            if results['ids'] and results['ids'][0]:
                for i, mem_id in enumerate(results['ids'][0]):
                    memory = await self.db.get_semantic_memory(mem_id)
                    if memory:
                        memories.append(memory)

            return memories
        except Exception as e:
            print(f"Error searching semantic memories: {e}")
            return []

    async def _reconstruct_details(
        self,
        summary: str,
        similar: List[Dict[str, Any]],
        messages: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Reconstruct detailed scene from summary and similar memories"""
        if not self.llm.is_configured():
            return {'reconstructed_details': summary}

        similar_context = "\n".join([
            f"#{i+1} {m['type']}: {m['content']}"
            for i, m in enumerate(similar)
        ]) or 'None'

        # Get language from LLM service settings
        language = getattr(self.llm, 'language', None)
        prompt = get_reconstruction_prompt(summary=summary, similar_context=similar_context)
        prompt = inject_language(prompt, language)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            result = self.llm.parse_json_response(response)
            if result and isinstance(result.get('reconstructed_details'), str):
                return result
            return {'reconstructed_details': summary}
        except Exception as e:
            print(f"Error in reconstruction: {e}")
            return {'reconstructed_details': summary}

    async def _calibrate_with_original(
        self,
        reconstructed: str,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Extract insights into 8 life categories from the session"""
        if not self.llm.is_configured():
            return {cat: [] for cat in SEMANTIC_CATEGORIES.keys()}

        # Build compact message summary
        compact = []
        for msg in messages[:30]:
            ts = datetime.fromtimestamp(msg['timestamp']/1000).strftime('%H:%M:%S')
            text = msg.get('content', '')
            if text:
                text = text[:140].replace('\n', ' ')
                compact.append(f"- [{ts}] {msg.get('role', 'unknown')}: {text}")
            elif msg.get('screenshot_id'):
                compact.append(f"- [{ts}] [screenshot] {msg.get('title', '')}")

        categories_desc = "\n".join([f"- **{k}**: {v}" for k, v in SEMANTIC_CATEGORIES.items()])

        # Get language from LLM service settings
        language = getattr(self.llm, 'language', None)
        prompt = get_calibration_prompt(
            categories_desc=categories_desc,
            reconstructed=reconstructed,
            compact_events=chr(10).join(compact)
        )
        prompt = inject_language(prompt, language)

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            result = self.llm.parse_json_response(response)
            if result:
                return {
                    cat: [item for item in result.get(cat, []) if isinstance(item, str)]
                    for cat in SEMANTIC_CATEGORIES.keys()
                }
            return {cat: [] for cat in SEMANTIC_CATEGORIES.keys()}
        except Exception as e:
            print(f"Error in calibration: {e}")
            return {cat: [] for cat in SEMANTIC_CATEGORIES.keys()}

    def _build_fallback_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Build a fallback summary from messages"""
        parts = []
        for msg in messages[:5]:
            if msg.get('content'):
                parts.append(f"{msg.get('role', 'unknown')}: {msg['content'][:80]}")
            elif msg.get('screenshot_id'):
                parts.append(f"screenshot: {msg.get('title', '')}")
        return ' | '.join(parts)

    def _extract_heuristic_items(
        self,
        messages: List[Dict[str, Any]],
        summary: str
    ) -> Dict[str, List[str]]:
        """Extract semantic items using heuristics when LLM fails"""
        result = {cat: [] for cat in SEMANTIC_CATEGORIES.keys()}
        s = (summary or '').lower()

        # Count URL hosts
        host_count = {}
        for msg in messages:
            url = msg.get('url')
            if url:
                try:
                    from urllib.parse import urlparse
                    host = urlparse(url).netloc.replace('www.', '')
                    if host:
                        host_count[host] = host_count.get(host, 0) + 1
                except:
                    pass

        # Categorize based on site content
        if host_count:
            top_host = max(host_count.items(), key=lambda x: x[1])[0]

            # Work/career related sites
            if any(x in top_host for x in ['github', 'gitlab', 'stackoverflow', 'linkedin']):
                result['career'].append(f"User works with {top_host}")
            # Learning sites
            elif any(x in top_host for x in ['coursera', 'udemy', 'edx', 'medium', 'dev.to']):
                result['growth'].append(f"User learns from {top_host}")
            # Entertainment/leisure
            elif any(x in top_host for x in ['youtube', 'netflix', 'spotify', 'twitch']):
                result['leisure'].append(f"User enjoys content on {top_host}")
            # Social
            elif any(x in top_host for x in ['twitter', 'facebook', 'instagram', 'reddit']):
                result['social'].append(f"User is active on {top_host}")
            # Finance
            elif any(x in top_host for x in ['bank', 'invest', 'trading', 'finance']):
                result['finance'].append(f"User uses {top_host} for finances")

        # Check for video content
        if 'youtube' in s or 'video' in s:
            result['leisure'].append("User enjoys watching video content")

        # Check for coding/development
        if any(x in s for x in ['code', 'programming', 'develop', 'python', 'javascript']):
            result['career'].append("User is involved in software development")

        return result


# Backward compatibility alias
SemanticAgent = SemanticExtractor
