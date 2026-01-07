"""
Image utilities for Nemori Backend
Handles image compression for LLM multimodal requests
"""

import base64
import io
from typing import List, Optional
from PIL import Image


def compress_image_for_llm(
    image_data: str,
    quality: int = 70,
    max_width: int = 1280,
    max_height: int = 720
) -> str:
    """
    Compress an image for sending to LLM APIs.
    Converts PNG to JPEG and resizes if needed.

    Args:
        image_data: Base64 encoded image or data URL
        quality: JPEG quality (0-100), default 70
        max_width: Maximum width, default 1280
        max_height: Maximum height, default 720

    Returns:
        Base64 encoded JPEG data URL
    """
    try:
        # Extract base64 data from data URL if needed
        if image_data.startswith('data:'):
            # Parse data URL: data:image/png;base64,xxxx
            header, base64_data = image_data.split(',', 1)
        else:
            base64_data = image_data

        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)

        # Open image with PIL
        img = Image.open(io.BytesIO(image_bytes))

        # Convert RGBA to RGB (JPEG doesn't support alpha)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Calculate new dimensions while preserving aspect ratio
        width, height = img.size
        if width > max_width or height > max_height:
            width_ratio = max_width / width
            height_ratio = max_height / height
            ratio = min(width_ratio, height_ratio)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save as JPEG to buffer
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        compressed_bytes = buffer.getvalue()

        # Convert back to base64 data URL
        compressed_base64 = base64.b64encode(compressed_bytes).decode('utf-8')
        compressed_data_url = f"data:image/jpeg;base64,{compressed_base64}"

        # Log compression stats
        original_size = len(base64_data)
        compressed_size = len(compressed_base64)
        saved_percent = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
        print(f"Image compressed: {original_size/1024:.0f}KB -> {compressed_size/1024:.0f}KB (saved {saved_percent:.1f}%)")

        return compressed_data_url

    except Exception as e:
        print(f"Image compression failed, using original: {e}")
        # Return original if compression fails
        if not image_data.startswith('data:'):
            return f"data:image/png;base64,{image_data}"
        return image_data


def compress_images_for_llm(
    image_data_list: List[str],
    quality: int = 70,
    max_width: int = 1280,
    max_height: int = 720
) -> List[str]:
    """
    Compress multiple images for sending to LLM APIs.

    Args:
        image_data_list: List of base64 encoded images or data URLs
        quality: JPEG quality (0-100), default 70
        max_width: Maximum width, default 1280
        max_height: Maximum height, default 720

    Returns:
        List of base64 encoded JPEG data URLs
    """
    if not image_data_list:
        return []

    print(f"Compressing {len(image_data_list)} images for LLM...")

    compressed = []
    for img_data in image_data_list:
        compressed.append(compress_image_for_llm(img_data, quality, max_width, max_height))

    return compressed


def ensure_image_data_url(image_data: str) -> str:
    """
    Ensure image data is in data URL format.

    Args:
        image_data: Raw base64 or data URL

    Returns:
        Properly formatted data URL
    """
    if not image_data:
        return image_data

    if image_data.startswith('data:image/'):
        return image_data

    if image_data.startswith('data:'):
        return image_data

    # Try to detect image type from base64 header
    if image_data.startswith('iVBORw0KGgo'):  # PNG
        return f"data:image/png;base64,{image_data}"
    if image_data.startswith('/9j/'):  # JPEG
        return f"data:image/jpeg;base64,{image_data}"
    if image_data.startswith('UklGR'):  # WebP
        return f"data:image/webp;base64,{image_data}"

    # Default to PNG
    return f"data:image/png;base64,{image_data}"


def load_image_as_base64(file_path: str) -> Optional[str]:
    """
    Load an image file and convert to base64 data URL.

    Args:
        file_path: Path to image file

    Returns:
        Base64 data URL or None if failed
    """
    try:
        with open(file_path, 'rb') as f:
            image_bytes = f.read()

        # Detect image type
        img = Image.open(io.BytesIO(image_bytes))
        format_map = {
            'PNG': 'image/png',
            'JPEG': 'image/jpeg',
            'JPG': 'image/jpeg',
            'WEBP': 'image/webp',
            'GIF': 'image/gif'
        }
        mime_type = format_map.get(img.format, 'image/png')

        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"

    except Exception as e:
        print(f"Failed to load image: {e}")
        return None
