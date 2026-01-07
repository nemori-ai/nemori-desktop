"""
Episodic Agent - Creates narrative memories from message batches
"""

import uuid
import json
import math
from datetime import datetime
from typing import Optional, List, Dict, Any

from storage.database import Database
from storage.vector_store import VectorStore
from services.llm_service import LLMService
from utils.image import compress_images_for_llm, load_image_as_base64


class EpisodicAgent:
    """Agent for creating episodic memories from message batches"""

    def __init__(self):
        self.db = Database.get_instance()
        self.vector_store = VectorStore.get_instance()
        self.llm = LLMService.get_instance()

    async def create_from_messages(self, message_ids: List[str], summary: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create an episodic memory from a batch of messages"""
        try:
            # Load messages
            messages = await self.db.get_messages_by_ids(message_ids)
            if not messages:
                return None

            # Sort by timestamp
            messages.sort(key=lambda m: m.get('timestamp', 0))

            # Compute time range
            start_time = messages[0].get('timestamp')
            end_time = messages[-1].get('timestamp')

            # Collect metadata
            participants = set()
            urls = set()
            screenshot_ids = set()

            # Build event details for LLM
            event_details = []
            for msg in messages:
                role = msg.get('role', 'unknown')
                if role in ('user', 'assistant'):
                    participants.add(role)

                if msg.get('url'):
                    urls.add(msg['url'])

                if msg.get('screenshot_id'):
                    screenshot_ids.add(msg['screenshot_id'])
                    screenshot = await self.db.get_screenshot(msg['screenshot_id'])
                    if screenshot:
                        ts = datetime.fromtimestamp(msg['timestamp']/1000).strftime('%H:%M:%S')
                        event_details.append(
                            f"[{ts}] Screenshot: {screenshot.get('title', 'Untitled')} ({screenshot.get('url', 'No URL')})"
                        )

                if msg.get('content'):
                    ts = datetime.fromtimestamp(msg['timestamp']/1000).strftime('%H:%M:%S')
                    content = msg['content'][:200] + '...' if len(msg.get('content', '')) > 200 else msg['content']
                    event_details.append(f"[{ts}] {role}: {content}")

            # Collect and compress screenshot images
            screenshot_images = await self._collect_screenshot_images(messages, max_images=10)

            # Generate episodic content using LLM (with images if available)
            episodic_content = await self._generate_episodic_content(event_details, summary, screenshot_images)

            if not episodic_content or not episodic_content.get('title') or not episodic_content.get('content'):
                print("Failed to generate valid episodic content")
                return None

            # Generate embedding
            embedding = await self.llm.embed_single(episodic_content['content'])

            # Check for similar memories to potentially merge
            similar_memories = await self._search_similar_memories(embedding, 5)

            if similar_memories:
                # Decide whether to merge or create new
                decision = await self._decide_on_merge(episodic_content, start_time, end_time, similar_memories)

                if decision.get('decision') == 'merge' and decision.get('merge_target_id'):
                    try:
                        print(f"Decision to merge with {decision['merge_target_id']}. Reason: {decision.get('reason')}")
                        merged_memory = await self._merge_memories(
                            decision['merge_target_id'],
                            message_ids,
                            episodic_content
                        )

                        # Delete old memory and save new one
                        await self.db.delete_episodic_memory(decision['merge_target_id'])
                        self.vector_store.delete([decision['merge_target_id']])

                        # Save merged memory
                        await self._save_memory(merged_memory)
                        print(f"Successfully merged memory. New ID: {merged_memory['id']}")
                        return merged_memory
                    except Exception as e:
                        print(f"Merge failed, saving as new: {e}")
                else:
                    print(f"Decision to create new memory. Reason: {decision.get('reason')}")

            # Create new memory
            memory_id = str(uuid.uuid4())
            memory = {
                'id': memory_id,
                'created_at': int(datetime.now().timestamp() * 1000),
                'start_time': start_time,
                'end_time': end_time,
                'title': episodic_content['title'],
                'content': episodic_content['content'],
                'event_ids': message_ids,
                'participants': list(participants),
                'urls': list(urls),
                'screenshot_ids': list(screenshot_ids),
                'embedding_id': memory_id,
                'source_app': ['nemori']
            }

            await self._save_memory(memory, embedding)
            print(f"Created new episodic memory: {memory['title']}")
            return memory

        except Exception as e:
            print(f"Error creating episodic memory: {e}")
            return None

    async def _save_memory(self, memory: Dict[str, Any], embedding: Optional[List[float]] = None) -> None:
        """Save memory to database and vector store"""
        if embedding is None:
            embedding = await self.llm.embed_single(memory['content'])

        # Save to vector store
        self.vector_store.add_embedding(
            id=memory['id'],
            embedding=embedding,
            metadata={
                'type': 'episodic',
                'title': memory['title'],
                'created_at': memory['created_at']
            },
            document=memory['content']
        )

        # Save to database
        await self.db.save_episodic_memory(memory)

    async def _generate_episodic_content(
        self,
        event_details: List[str],
        summary: Optional[str] = None,
        screenshot_images: Optional[List[str]] = None
    ) -> Optional[Dict[str, str]]:
        """Generate episodic content using LLM (with optional images)"""
        if not self.llm.is_configured():
            return None

        events_text = "\n".join(event_details)

        prompt = f"""You are an assistant that creates a personal journal entry from a user's digital activity.

Here is a log of the user's recent activity:
{events_text}

{f'Summary hint: {summary}' if summary else ''}

{'I have also attached screenshots from this session for visual context.' if screenshot_images else ''}

Please write your response based on the following instructions:
- **Perspective**: Write the 'content' from a first-person or close third-person perspective, as if narrating the user's own experience.
- **Narration Style**: Create a narrative that captures the flow and purpose of the session. Do not include raw IDs or technical details.
- **Focus**: Describe what the user did, thought, or intended to do.
- **Visual Context**: If screenshots are provided, use them to enrich your understanding of the user's activities.

Please write:
- **title**: A concise line capturing what this episode is about (max 100 characters).
- **content**: A detailed narrative of what happened, at least 200 words long.

Return your response in JSON format:
{{
  "title": "...",
  "content": "..."
}}"""

        try:
            if screenshot_images:
                # Use multimodal chat with images
                response = await self.llm.chat_with_images(
                    prompt=prompt,
                    image_urls=screenshot_images,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
            else:
                # Text-only chat
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
            result = self.llm.parse_json_response(response)
            return result
        except Exception as e:
            print(f"Error generating episodic content: {e}")
            return None

    async def _collect_screenshot_images(
        self,
        messages: List[Dict[str, Any]],
        max_images: int = 10
    ) -> List[str]:
        """Collect and compress screenshot images for LLM analysis"""
        image_urls = []

        for msg in messages:
            if len(image_urls) >= max_images:
                break

            screenshot_id = msg.get('screenshot_id')
            if not screenshot_id:
                continue

            try:
                screenshot = await self.db.get_screenshot(screenshot_id)
                if not screenshot:
                    continue

                # Load image from file path
                file_path = screenshot.get('file_path')
                if file_path:
                    img_data = load_image_as_base64(file_path)
                    if img_data:
                        image_urls.append(img_data)

            except Exception as e:
                print(f"Failed to load screenshot {screenshot_id}: {e}")

        # Compress images for LLM (PNG -> JPEG, resize)
        if image_urls:
            print(f"EpisodicAgent: Collected {len(image_urls)} screenshots, compressing for LLM...")
            image_urls = compress_images_for_llm(image_urls)

        return image_urls

    async def _search_similar_memories(
        self,
        embedding: List[float],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Search for similar episodic memories"""
        try:
            results = self.vector_store.query(
                query_embedding=embedding,
                n_results=top_k,
                where={'type': 'episodic'}
            )

            memories = []
            if results['ids'] and results['ids'][0]:
                for i, mem_id in enumerate(results['ids'][0]):
                    memory = await self.db.get_episodic_memory(mem_id)
                    if memory:
                        distance = results['distances'][0][i] if results.get('distances') else 0
                        memories.append({
                            **memory,
                            'similarity': 1 - distance  # Convert distance to similarity
                        })

            return memories
        except Exception as e:
            print(f"Error searching similar memories: {e}")
            return []

    async def _decide_on_merge(
        self,
        new_content: Dict[str, str],
        start_time: int,
        end_time: int,
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Decide whether to merge with an existing memory"""
        if not self.llm.is_configured():
            return {'decision': 'new', 'reason': 'LLM not configured'}

        candidates_summary = "\n".join([
            f"""- Candidate ID: {c['id']}
  - Time Range: {datetime.fromtimestamp(c['start_time']/1000)} to {datetime.fromtimestamp(c['end_time']/1000)}
  - Title: {c['title']}
  - Content: {c['content'][:200]}..."""
            for c in candidates
        ])

        prompt = f"""You are a memory management assistant. Your task is to decide whether a newly generated episodic memory should be merged with an existing similar memory or kept as a new one.

**Decision Criteria:**
1. **Temporal Proximity:** Are the events close in time? A small gap (e.g., under 15 minutes) suggests they might be part of the same activity.
2. **Contextual Cohesion:** Do the memories describe the same continuous event or task?

**Newly Generated Memory:**
- Time Range: {datetime.fromtimestamp(start_time/1000)} to {datetime.fromtimestamp(end_time/1000)}
- Title: {new_content['title']}
- Content: {new_content['content']}

**Top Similar Existing Memories:**
{candidates_summary}

**Your Task:**
Based on the criteria, decide whether to merge the new memory with ONE of the candidates or to create a new memory.

- If you decide to merge, set "decision" to "merge" and provide the "merge_target_id".
- If you decide not to merge, set "decision" to "new".

**JSON Response Format:**
{{
  "decision": "merge" | "new",
  "merge_target_id": "...",
  "reason": "..."
}}"""

        try:
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            result = self.llm.parse_json_response(response)
            if result and result.get('decision') in ('merge', 'new'):
                return result
            return {'decision': 'new', 'reason': 'Invalid response format'}
        except Exception as e:
            print(f"Error in merge decision: {e}")
            return {'decision': 'new', 'reason': 'Decision failed'}

    async def _merge_memories(
        self,
        target_id: str,
        new_message_ids: List[str],
        new_content: Dict[str, str]
    ) -> Dict[str, Any]:
        """Merge new messages with an existing memory"""
        target_memory = await self.db.get_episodic_memory(target_id)
        if not target_memory:
            raise ValueError(f"Target memory not found: {target_id}")

        # Combine message IDs
        all_message_ids = list(set(target_memory.get('event_ids', []) + new_message_ids))

        # Get all messages and rebuild context
        all_messages = await self.db.get_messages_by_ids(all_message_ids)
        all_messages.sort(key=lambda m: m.get('timestamp', 0))

        start_time = all_messages[0].get('timestamp') if all_messages else target_memory['start_time']
        end_time = all_messages[-1].get('timestamp') if all_messages else target_memory['end_time']

        # Collect metadata
        participants = set(target_memory.get('participants', []))
        urls = set(target_memory.get('urls', []))
        screenshot_ids = set(target_memory.get('screenshot_ids', []))

        for msg in all_messages:
            if msg.get('role') in ('user', 'assistant'):
                participants.add(msg['role'])
            if msg.get('url'):
                urls.add(msg['url'])
            if msg.get('screenshot_id'):
                screenshot_ids.add(msg['screenshot_id'])

        # Collect screenshots from all messages for visual context
        all_screenshot_images = await self._collect_screenshot_images(all_messages, max_images=10)

        # Generate merged content
        merged_content = await self._generate_merged_content(
            target_memory,
            new_content,
            all_messages,
            all_screenshot_images
        )

        # Generate new embedding
        new_embedding = await self.llm.embed_single(merged_content['content'])

        # Create merged memory
        memory_id = str(uuid.uuid4())
        merged_memory = {
            'id': memory_id,
            'created_at': int(datetime.now().timestamp() * 1000),
            'start_time': start_time,
            'end_time': end_time,
            'title': merged_content['title'],
            'content': merged_content['content'],
            'event_ids': all_message_ids,
            'participants': list(participants),
            'urls': list(urls),
            'screenshot_ids': list(screenshot_ids),
            'embedding_id': memory_id,
            'source_app': list(set(target_memory.get('source_app', ['nemori']) + ['nemori']))
        }

        # Save merged memory with embedding
        await self._save_memory(merged_memory, new_embedding)

        return merged_memory

    async def _generate_merged_content(
        self,
        old_memory: Dict[str, Any],
        new_content: Dict[str, str],
        all_messages: List[Dict[str, Any]],
        screenshot_images: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Generate merged content from old and new memories (with optional images)"""
        if not self.llm.is_configured():
            return new_content

        # Build event summary
        event_details = []
        for msg in all_messages:
            ts = datetime.fromtimestamp(msg['timestamp']/1000).strftime('%H:%M:%S')
            if msg.get('content'):
                event_details.append(f"[{ts}] {msg.get('role', 'unknown')}: {msg['content'][:100]}")
            elif msg.get('screenshot_id'):
                event_details.append(f"[{ts}] Screenshot: {msg.get('title', 'Untitled')}")

        prompt = f"""You are a memory consolidation assistant. You need to merge two related memories into one coherent narrative.

**Old Memory:**
Title: {old_memory['title']}
Content: {old_memory['content']}

**New Memory:**
Title: {new_content['title']}
Content: {new_content['content']}

**Combined Event Timeline:**
{chr(10).join(event_details)}

{'I have also attached screenshots from this session for visual context.' if screenshot_images else ''}

Your task is to create a single, unified memory that combines both narratives into a coherent story. The new narrative should:
- Seamlessly connect the events from both memories
- Focus on creating a logical story from the user's perspective
- Use visual context from screenshots if provided to enrich the narrative
- Not mention screenshots or technical details directly

Please write:
- title: A new, concise title for the combined episode (max 100 characters).
- content: A detailed narrative that merges both memories into one story. At least 300 words.

Return your response in JSON format:
{{
  "title": "...",
  "content": "..."
}}"""

        try:
            if screenshot_images:
                response = await self.llm.chat_with_images(
                    prompt=prompt,
                    image_urls=screenshot_images,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
            else:
                response = await self.llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
            result = self.llm.parse_json_response(response)
            return result if result else new_content
        except Exception as e:
            print(f"Error generating merged content: {e}")
            return new_content

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return await self.llm.embed_single(text)

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if len(vec_a) != len(vec_b):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)
