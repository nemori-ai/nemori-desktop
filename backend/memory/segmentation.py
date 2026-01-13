"""
Event Segmenter - Determines memory boundaries from event sequences

This is a fixed workflow that analyzes event sequences and determines
optimal segmentation points for creating coherent episodic memories.
"""

import json
from datetime import datetime
from typing import List, Dict, Any

from storage.database import Database
from services.llm_service import LLMService
from utils.image import compress_images_for_llm, load_image_as_base64


class EventSegmentation:
    """Represents an event segmentation decision"""
    def __init__(self, reason: str, cut_position: int, summary: str = ""):
        self.reason = reason
        self.cut_position = cut_position
        self.summary = summary

    def to_dict(self) -> Dict[str, Any]:
        return {
            'reason': self.reason,
            'cut_position': self.cut_position,
            'summary': self.summary
        }


class EventSegmenter:
    """Segmenter for analyzing event sequences and determining segmentation points"""

    def __init__(self):
        self.db = Database.get_instance()
        self.llm = LLMService.get_instance()

    async def analyze_event_sequence(self, message_ids: List[str]) -> List[EventSegmentation]:
        """Analyze a sequence of messages and determine segmentation points"""
        if len(message_ids) <= 1:
            return [EventSegmentation(
                reason="Single event or empty sequence",
                cut_position=len(message_ids)
            )]

        try:
            messages = await self.db.get_messages_by_ids(message_ids)
            if not messages:
                return [EventSegmentation(
                    reason="No valid messages found",
                    cut_position=0
                )]

            # Sort by timestamp
            messages.sort(key=lambda m: m.get('timestamp', 0))

            # Build event context
            event_details = self._build_event_context(messages)

            # Perform segmentation analysis
            segmentations = await self._perform_event_segmentation(event_details, messages)

            return segmentations

        except Exception as e:
            print(f"Error analyzing event sequence: {e}")
            return [EventSegmentation(
                reason="Error in analysis, defaulting to full batch",
                cut_position=len(message_ids)
            )]

    def _build_event_context(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Build a list of event descriptions for LLM analysis"""
        event_details = []

        for i, msg in enumerate(messages):
            ts = datetime.fromtimestamp(msg.get('timestamp', 0)/1000).strftime('%H:%M:%S')

            if msg.get('screenshot_id'):
                title = msg.get('title', 'Untitled')
                url = msg.get('url', 'No URL')
                event_details.append(f"[{i}] {ts} - Screenshot: {title} ({url})")
            elif msg.get('content'):
                role = msg.get('role', 'unknown')
                content = msg['content'][:100] + '...' if len(msg.get('content', '')) > 100 else msg['content']
                event_details.append(f"[{i}] {ts} - {role}: {content}")
            else:
                role = msg.get('role', 'unknown')
                event_details.append(f"[{i}] {ts} - {role} activity")

        return event_details

    async def _perform_event_segmentation(
        self,
        event_details: List[str],
        messages: List[Dict[str, Any]]
    ) -> List[EventSegmentation]:
        """Use LLM to determine optimal segmentation points"""
        if not self.llm.is_configured():
            return [EventSegmentation(
                reason="No LLM configured, using default segmentation",
                cut_position=len(messages)
            )]

        num_events = len(messages)

        prompt = f"""You are an intelligent event segmentation agent. Your task is to analyze a sequence of browsing/activity events and determine how to segment them into coherent episodes.

Here is the sequence of {num_events} events:
{chr(10).join(event_details)}

Instructions:
1. Look for natural breakpoints where one coherent activity/task ends and another begins
2. Consider factors like:
   - Topic/domain changes (e.g., switching from work to entertainment)
   - Time gaps (large breaks between activities)
   - URL domain changes (different websites/applications)
   - Task completion patterns (finishing one workflow and starting another)
   - Context shifts (different types of content or activities)

3. Each segment should represent a coherent episode of related activities
4. Avoid creating too many tiny segments (prefer 3-8 events per segment when possible)
5. Make cuts that preserve the narrative flow of each episode

Return a JSON array of segmentation decisions:

[
  {{
    "reason": "Brief explanation of why this cut makes sense",
    "cutPosition": number (1 to {num_events-1} for actual cuts, or {num_events} for no cut),
    "summary": "Brief summary of the segment (max 100 words)"
  }}
]

If no cuts are needed, return:
[
  {{
    "reason": "Explanation of why no cuts are needed",
    "cutPosition": {num_events},
    "summary": "Brief summary of the entire sequence"
  }}
]

Important:
- cutPosition should be between 1 and {num_events-1} for actual cuts
- cutPosition of {num_events} means no cut (process entire sequence as one episode)
- Always provide exactly one segmentation decision
- Focus on the most significant natural breakpoint if multiple exist"""

        import asyncio
        max_retries = 2  # Fewer retries for segmentation since it has a good fallback
        last_error = None

        for attempt in range(max_retries):
            try:
                # Try multimodal with screenshots first
                image_urls = await self._collect_screenshot_images(messages, max_images=10)

                if image_urls:
                    response = await self.llm.chat_with_images(
                        prompt=prompt,
                        image_urls=image_urls,
                        temperature=0.3,
                        response_format={"type": "json_object"}
                    )
                else:
                    response = await self.llm.chat(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        response_format={"type": "json_object"}
                    )

                result = self.llm.parse_json_response(response)

                if not result or not isinstance(result, list) or len(result) == 0:
                    raise ValueError("Invalid response format")

                segmentations = []
                for seg in result:
                    if not isinstance(seg.get('reason'), str) or not isinstance(seg.get('cutPosition'), (int, float)):
                        raise ValueError("Invalid segmentation object")

                    cut_pos = int(seg['cutPosition'])
                    cut_pos = max(1, min(num_events, cut_pos))

                    segmentations.append(EventSegmentation(
                        reason=seg['reason'],
                        cut_position=cut_pos,
                        summary=seg.get('summary', '')
                    ))

                return segmentations

            except Exception as e:
                last_error = e
                print(f"Error in event segmentation (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Short delay before retry

        # All retries failed - use fallback
        print(f"Segmentation failed after {max_retries} attempts, using full batch fallback")
        return [EventSegmentation(
            reason="Segmentation analysis failed, processing full batch",
            cut_position=len(messages)
        )]

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

        # Compress images for LLM
        if image_urls:
            print(f"Collected {len(image_urls)} screenshots for analysis")
            image_urls = compress_images_for_llm(image_urls)

        return image_urls

    async def should_segment_here(
        self,
        current_message: Dict[str, Any],
        previous_messages: List[Dict[str, Any]]
    ) -> bool:
        """Quick check if a new message should start a new segment"""
        if not previous_messages:
            return False

        last_msg = previous_messages[-1]

        # Check time gap (more than 15 minutes)
        time_gap = current_message.get('timestamp', 0) - last_msg.get('timestamp', 0)
        if time_gap > 15 * 60 * 1000:  # 15 minutes in milliseconds
            return True

        # Check URL domain change
        current_url = current_message.get('url', '')
        last_url = last_msg.get('url', '')
        if current_url and last_url:
            try:
                from urllib.parse import urlparse
                current_domain = urlparse(current_url).netloc
                last_domain = urlparse(last_url).netloc
                if current_domain and last_domain and current_domain != last_domain:
                    return True
            except:
                pass

        return False


# Backward compatibility alias
MainAgent = EventSegmenter
