"""
Screenshots API Routes
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from services.screenshot_service import ScreenshotService

router = APIRouter()


class CaptureOptions(BaseModel):
    interval_ms: Optional[int] = None


class SelectMonitorRequest(BaseModel):
    monitor_id: int


class UploadScreenshotRequest(BaseModel):
    """Request model for uploading screenshot from Electron frontend"""
    image_data: str  # Base64 encoded PNG image
    monitor_id: Optional[str] = None


@router.get("/")
async def get_screenshots(limit: int = 100, offset: int = 0):
    """Get screenshots list"""
    service = ScreenshotService.get_instance()
    screenshots = await service.get_screenshots(limit, offset)
    return {"screenshots": screenshots}


@router.get("/dates")
async def get_screenshot_dates():
    """Get list of dates that have screenshots"""
    service = ScreenshotService.get_instance()
    dates = await service.get_screenshot_dates()
    return {"dates": dates}


@router.get("/by-date/{date_str}")
async def get_screenshots_by_date(date_str: str, limit: int = 500, offset: int = 0):
    """Get screenshots for a specific date (YYYY-MM-DD format) with pagination"""
    service = ScreenshotService.get_instance()
    screenshots = await service.get_screenshots_by_date(date_str, limit, offset)
    total = await service.get_screenshot_count_by_date(date_str)
    return {"screenshots": screenshots, "date": date_str, "total": total}


@router.get("/since/{since_timestamp}")
async def get_screenshots_since(since_timestamp: int, limit: int = 100):
    """Get screenshots created after a timestamp for incremental loading"""
    service = ScreenshotService.get_instance()
    screenshots = await service.get_screenshots_since(since_timestamp, limit)
    return {"screenshots": screenshots, "since": since_timestamp}


@router.get("/paginated")
async def get_screenshots_paginated(page: int = 1, page_size: int = 50):
    """Get paginated screenshots with total count"""
    service = ScreenshotService.get_instance()
    result = await service.get_screenshots_paginated(page, page_size)
    return result


@router.get("/status")
async def get_capture_status():
    """Get screenshot capture status"""
    service = ScreenshotService.get_instance()
    return service.get_status()


@router.get("/monitors")
async def get_monitors():
    """Get available monitors for capture"""
    service = ScreenshotService.get_instance()
    return {
        "monitors": service.get_available_monitors(),
        "selected": service.get_selected_monitor()
    }


@router.post("/monitors/select")
async def select_monitor(request: SelectMonitorRequest):
    """Select which monitor to capture"""
    service = ScreenshotService.get_instance()
    success = service.set_selected_monitor(request.monitor_id)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid monitor ID")
    return {
        "success": True,
        "selected": request.monitor_id,
        "monitors": service.get_available_monitors()
    }


@router.get("/monitors/{monitor_id}/preview")
async def get_monitor_preview(monitor_id: int):
    """Get a preview image of a specific monitor"""
    service = ScreenshotService.get_instance()
    preview = service.capture_monitor_preview(monitor_id)
    if not preview:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return Response(content=preview, media_type="image/png")


@router.post("/start")
async def start_capture(options: CaptureOptions = None):
    """Start screenshot capture"""
    service = ScreenshotService.get_instance()
    success = await service.start_capture(
        interval_ms=options.interval_ms if options else None
    )
    return {"success": success, "status": service.get_status()}


@router.post("/stop")
async def stop_capture():
    """Stop screenshot capture"""
    service = ScreenshotService.get_instance()
    success = await service.stop_capture()
    return {"success": success, "status": service.get_status()}


@router.post("/capture-now")
async def capture_now():
    """Capture a screenshot immediately (deprecated - use /upload instead)"""
    service = ScreenshotService.get_instance()
    screenshot = await service.capture_now()
    if screenshot:
        return {"success": True, "screenshot": screenshot}
    return {"success": False, "message": "Capture failed or duplicate"}


@router.post("/upload")
async def upload_screenshot(request: UploadScreenshotRequest):
    """
    Upload a screenshot captured by Electron frontend.
    This endpoint receives base64-encoded image data and saves it.
    """
    service = ScreenshotService.get_instance()
    screenshot = await service.save_uploaded_screenshot(
        image_data=request.image_data,
        monitor_id=request.monitor_id
    )
    if screenshot:
        return {"success": True, "screenshot": screenshot}
    return {"success": False, "message": "Failed to save screenshot or duplicate"}


@router.get("/{screenshot_id}")
async def get_screenshot(screenshot_id: str):
    """Get screenshot metadata"""
    service = ScreenshotService.get_instance()
    screenshot = await service.get_screenshot_by_id(screenshot_id)
    if not screenshot:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return screenshot


@router.get("/{screenshot_id}/image")
async def get_screenshot_image(screenshot_id: str):
    """Get screenshot image data"""
    service = ScreenshotService.get_instance()
    image_data = await service.get_screenshot_image(screenshot_id)
    if not image_data:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return Response(
        content=image_data,
        media_type="image/png"
    )


@router.get("/{screenshot_id}/base64")
async def get_screenshot_base64(screenshot_id: str):
    """Get screenshot as base64 string"""
    service = ScreenshotService.get_instance()
    base64_data = await service.get_screenshot_base64(screenshot_id)
    if not base64_data:
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return {"image": base64_data}


@router.delete("/{screenshot_id}")
async def delete_screenshot(screenshot_id: str):
    """Delete a screenshot"""
    service = ScreenshotService.get_instance()
    success = await service.delete_screenshot(screenshot_id)
    return {"success": success}


@router.post("/cleanup")
async def cleanup_old_screenshots(max_age_days: int = 30):
    """Clean up old screenshots"""
    service = ScreenshotService.get_instance()
    deleted_count = await service.cleanup_old_screenshots(max_age_days)
    return {
        "success": True,
        "deleted_count": deleted_count
    }
