"""
Screenshot Service for capturing and managing screenshots
"""
import asyncio
import uuid
import base64
import hashlib
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
from io import BytesIO

import mss
import imagehash
from PIL import Image

from config.settings import settings
from storage.database import Database
# Lazy import to avoid circular dependency
# from memory import MemoryOrchestrator  # Imported in capture_now()


class ScreenshotService:
    """Service for screenshot capture and management"""

    _instance: Optional["ScreenshotService"] = None

    def __init__(self):
        self._capture_task: Optional[asyncio.Task] = None
        self._is_capturing = False
        self._interval_ms = settings.capture_interval_ms
        self._last_phash: Optional[str] = None
        self._similarity_threshold = settings.similarity_threshold
        self._screenshots_path = settings.screenshots_path
        self._selected_monitor: int = 1  # Default to primary monitor (1-indexed)

    @classmethod
    def get_instance(cls) -> "ScreenshotService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_capturing(self) -> bool:
        """Check if capture is active"""
        return self._is_capturing

    def get_available_monitors(self) -> List[Dict[str, Any]]:
        """Get list of available monitors"""
        monitors = []
        with mss.mss() as sct:
            for i, mon in enumerate(sct.monitors):
                if i == 0:
                    # Index 0 is "all monitors combined"
                    monitors.append({
                        "id": 0,
                        "name": "All Screens",
                        "width": mon["width"],
                        "height": mon["height"],
                        "left": mon["left"],
                        "top": mon["top"]
                    })
                else:
                    monitors.append({
                        "id": i,
                        "name": f"Screen {i}" if i > 1 else "Primary Screen",
                        "width": mon["width"],
                        "height": mon["height"],
                        "left": mon["left"],
                        "top": mon["top"]
                    })
        return monitors

    def set_selected_monitor(self, monitor_id: int) -> bool:
        """Set which monitor to capture"""
        monitors = self.get_available_monitors()
        valid_ids = [m["id"] for m in monitors]
        if monitor_id in valid_ids:
            self._selected_monitor = monitor_id
            return True
        return False

    def get_selected_monitor(self) -> int:
        """Get currently selected monitor ID"""
        return self._selected_monitor

    def capture_monitor_preview(self, monitor_id: int) -> Optional[bytes]:
        """Capture a small preview image of a specific monitor"""
        try:
            with mss.mss() as sct:
                if monitor_id >= len(sct.monitors):
                    return None
                monitor = sct.monitors[monitor_id]
                screenshot = sct.grab(monitor)

                img = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.bgra,
                    "raw",
                    "BGRX"
                )

                # Create a small thumbnail for preview
                img.thumbnail((320, 180), Image.Resampling.LANCZOS)

                # Convert to bytes
                buffer = BytesIO()
                img.save(buffer, "PNG", optimize=True)
                return buffer.getvalue()
        except Exception as e:
            print(f"Preview capture failed: {e}")
            return None

    async def start_capture(
        self,
        interval_ms: Optional[int] = None
    ) -> bool:
        """Start periodic screenshot capture"""
        if self._is_capturing:
            return False

        if interval_ms:
            self._interval_ms = interval_ms

        self._is_capturing = True
        self._capture_task = asyncio.create_task(self._capture_loop())

        return True

    async def stop_capture(self) -> bool:
        """Stop screenshot capture"""
        if not self._is_capturing:
            return False

        self._is_capturing = False

        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None

        self._last_phash = None
        return True

    async def _capture_loop(self) -> None:
        """Background capture loop"""
        while self._is_capturing:
            try:
                await self.capture_now()
            except Exception as e:
                print(f"Capture error: {e}")

            await asyncio.sleep(self._interval_ms / 1000)

    async def capture_now(self) -> Optional[Dict[str, Any]]:
        """Capture a screenshot immediately"""
        try:
            with mss.mss() as sct:
                # Capture the selected monitor
                monitor = sct.monitors[self._selected_monitor]
                screenshot = sct.grab(monitor)

                # Convert to PIL Image
                img = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.bgra,
                    "raw",
                    "BGRX"
                )

                # Calculate perceptual hash for deduplication
                phash = str(imagehash.phash(img))

                # Check for duplicate
                if self._last_phash and self._is_similar(phash, self._last_phash):
                    print("Skipping duplicate screenshot")
                    return None

                # Generate unique ID and timestamp
                screenshot_id = str(uuid.uuid4())
                timestamp = int(datetime.now().timestamp() * 1000)

                # Save image to file
                file_name = f"{screenshot_id}.png"
                file_path = self._screenshots_path / file_name

                # Resize for storage (optional - reduce size)
                max_size = (1920, 1080)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                img.save(file_path, "PNG", optimize=True)

                # Save to database
                db = Database.get_instance()
                screenshot_data = {
                    "id": screenshot_id,
                    "timestamp": timestamp,
                    "file_path": str(file_path),
                    "phash": phash,
                    "processed": False
                }

                await db.save_screenshot(screenshot_data)
                self._last_phash = phash

                # Notify memory manager for batch processing
                try:
                    from memory import MemoryOrchestrator
                    memory_manager = MemoryOrchestrator.get_instance()
                    await memory_manager.on_screenshot_captured(screenshot_data)
                except Exception as e:
                    print(f"Failed to notify memory manager: {e}")

                return screenshot_data

        except Exception as e:
            print(f"Screenshot capture failed: {e}")
            return None

    def _is_similar(self, hash1: str, hash2: str, threshold: int = 5) -> bool:
        """Check if two perceptual hashes are similar"""
        try:
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            distance = h1 - h2  # Hamming distance
            return distance <= threshold
        except Exception:
            return False

    async def get_screenshots(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get screenshots from database"""
        db = Database.get_instance()
        return await db.get_screenshots(limit, offset)

    async def get_screenshots_by_date(
        self,
        date_str: str,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Get screenshots for a specific date"""
        db = Database.get_instance()
        return await db.get_screenshots_by_date(date_str, limit)

    async def get_screenshot_dates(self) -> List[str]:
        """Get list of dates that have screenshots"""
        db = Database.get_instance()
        return await db.get_screenshot_dates()

    async def get_screenshot_by_id(self, screenshot_id: str) -> Optional[Dict[str, Any]]:
        """Get a screenshot by ID"""
        db = Database.get_instance()
        return await db.get_screenshot_by_id(screenshot_id)

    async def get_screenshot_image(self, screenshot_id: str) -> Optional[bytes]:
        """Get screenshot image data"""
        screenshot = await self.get_screenshot_by_id(screenshot_id)
        if not screenshot:
            return None

        file_path = Path(screenshot["file_path"])
        if not file_path.exists():
            return None

        return file_path.read_bytes()

    async def get_screenshot_base64(self, screenshot_id: str) -> Optional[str]:
        """Get screenshot as base64 string"""
        image_data = await self.get_screenshot_image(screenshot_id)
        if not image_data:
            return None

        return base64.b64encode(image_data).decode("utf-8")

    async def delete_screenshot(self, screenshot_id: str) -> bool:
        """Delete a screenshot"""
        try:
            screenshot = await self.get_screenshot_by_id(screenshot_id)
            if screenshot:
                # Delete file
                file_path = Path(screenshot["file_path"])
                if file_path.exists():
                    file_path.unlink()

                # Delete from database
                db = Database.get_instance()
                await db.delete_screenshot(screenshot_id)

            return True
        except Exception as e:
            print(f"Delete screenshot error: {e}")
            return False

    async def cleanup_old_screenshots(self, max_age_days: int = 30) -> int:
        """Clean up old screenshots"""
        db = Database.get_instance()
        screenshots = await db.get_screenshots(limit=10000)

        deleted_count = 0
        cutoff_time = datetime.now().timestamp() * 1000 - (max_age_days * 24 * 60 * 60 * 1000)

        for screenshot in screenshots:
            if screenshot["timestamp"] < cutoff_time:
                await self.delete_screenshot(screenshot["id"])
                deleted_count += 1

        return deleted_count

    def get_status(self) -> Dict[str, Any]:
        """Get capture status"""
        return {
            "is_capturing": self._is_capturing,
            "interval_ms": self._interval_ms,
            "screenshots_path": str(self._screenshots_path),
            "selected_monitor": self._selected_monitor,
            "monitors": self.get_available_monitors()
        }

    async def get_screenshots_since(
        self,
        since_timestamp: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get screenshots created after a timestamp for incremental loading"""
        db = Database.get_instance()
        return await db.get_screenshots_since(since_timestamp, limit)

    async def get_screenshots_paginated(
        self,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """Get paginated screenshots with total count"""
        db = Database.get_instance()
        return await db.get_screenshots_paginated(page, page_size)
