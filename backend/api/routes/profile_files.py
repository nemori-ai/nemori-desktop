"""
Profile Files API Routes

API endpoints for managing user profile files (Markdown-based profile system).
This is the new file-based profile system used by the Proactive Agent.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.profile_manager import ProfileManager

router = APIRouter()


# ==================== Request/Response Models ====================

class ProfileFileInfo(BaseModel):
    """Profile file information"""
    name: str
    relative_path: str
    title: str
    summary: str
    keywords: List[str]
    confidence: float
    layer: int
    layer_name: str
    updated_at: Optional[str] = None
    size: int


class ProfileFileContent(BaseModel):
    """Profile file with content"""
    filename: str
    content: str
    metadata: Optional[dict] = None


class WriteFileRequest(BaseModel):
    """Request to write a profile file"""
    content: str = Field(..., description="The Markdown content with YAML front matter")
    changelog_entry: str = Field(..., description="Description of the change")


class CreateFileRequest(BaseModel):
    """Request to create a new profile file"""
    title: str = Field(..., description="Title of the new file")
    description: str = Field(..., description="Brief description")
    initial_content: Optional[str] = Field(None, description="Optional initial content")


class SearchRequest(BaseModel):
    """Request to search profile files"""
    query: str = Field(..., description="Search query")
    filenames: Optional[List[str]] = Field(None, description="Optional: files to search")


class SearchMatch(BaseModel):
    """A single search match"""
    line: int
    content: str
    context: str


class SearchFileResult(BaseModel):
    """Search results for a single file"""
    filename: str
    matches_count: int
    matches: List[SearchMatch]


class SearchResponse(BaseModel):
    """Search response"""
    query: str
    total_matches: int
    files_matched: int
    results: List[SearchFileResult]


class ProfileSummaryResponse(BaseModel):
    """Profile summary response"""
    total_files: int
    last_updated: Optional[str]
    categories: dict
    recent_changes: List[dict]
    key_facts: Optional[List[str]] = None


# ==================== API Endpoints ====================

@router.get("/files")
async def list_files(
    include_topics: bool = True,
    layer: Optional[int] = None
) -> dict:
    """List all profile files.

    Profile files are organized into layers:
    - 0: 基础档案 (Basic Info, Core Identity)
    - 1: 内在特质 (Personality, Values, Cognitive Style)
    - 2: 能力与发展 (Skills, Knowledge, Goals, Interests)
    - 3: 生活方式 (Daily Patterns, Preferences, Health)
    - 4: 社会关系 (Relationships, Projects, Social Context)
    - 5: 记忆与洞察 (Key Memories, Patterns & Insights)
    - 6: 专题深入 (Topic files in topics/ directory)
    """
    try:
        manager = ProfileManager.get_instance()
        files = await manager.list_files(include_topics=include_topics)

        # Filter by layer if specified
        if layer is not None:
            files = [f for f in files if f.layer == layer]

        # Group by layer
        files_by_layer = {}
        for f in files:
            layer_name = manager.LAYER_NAMES.get(f.layer, f"Layer {f.layer}")
            if layer_name not in files_by_layer:
                files_by_layer[layer_name] = []
            files_by_layer[layer_name].append({
                "name": f.name,
                "relative_path": f.relative_path,
                "title": f.title,
                "summary": f.summary,
                "keywords": f.keywords,
                "confidence": f.confidence,
                "layer": f.layer,
                "layer_name": layer_name,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
                "size": f.size
            })

        return {
            "success": True,
            "total_files": len(files),
            "files_by_layer": files_by_layer
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{filename:path}")
async def read_file(filename: str) -> dict:
    """Read a profile file's content.

    Args:
        filename: The file path (e.g., '00-basic-info.md' or 'topics/python.md')
    """
    try:
        manager = ProfileManager.get_instance()
        content = await manager.read_file(filename)

        # Get metadata
        files = await manager.list_files()
        file_info = next((f for f in files if f.relative_path == filename), None)

        result = {
            "success": True,
            "filename": filename,
            "content": content
        }

        if file_info:
            result["metadata"] = {
                "title": file_info.title,
                "summary": file_info.summary,
                "keywords": file_info.keywords,
                "confidence": file_info.confidence,
                "layer": file_info.layer,
                "updated_at": file_info.updated_at.isoformat() if file_info.updated_at else None
            }

        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/files/{filename:path}")
async def write_file(filename: str, request: WriteFileRequest) -> dict:
    """Update a profile file's content.

    Args:
        filename: The file path
        request: The new content and changelog entry
    """
    try:
        manager = ProfileManager.get_instance()
        await manager.write_file(
            filename=filename,
            content=request.content,
            changelog_entry=request.changelog_entry
        )
        return {
            "success": True,
            "message": f"Successfully updated {filename}",
            "changelog_entry": request.changelog_entry
        }
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {filename}. Use POST to create a new file."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{filename:path}")
async def create_file(filename: str, request: CreateFileRequest) -> dict:
    """Create a new profile file.

    Topic files should be created in the topics/ directory:
    - topics/python-learning.md
    - topics/fitness-journey.md
    """
    try:
        manager = ProfileManager.get_instance()
        await manager.create_file(
            filename=filename,
            title=request.title,
            description=request.description,
            initial_content=request.initial_content
        )
        return {
            "success": True,
            "message": f"Successfully created {filename}",
            "title": request.title
        }
    except FileExistsError:
        raise HTTPException(
            status_code=409,
            detail=f"File already exists: {filename}. Use PUT to update it."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{filename:path}")
async def delete_file(filename: str) -> dict:
    """Delete a profile file.

    Only topic files can be deleted. Core files and system files are protected.
    """
    try:
        manager = ProfileManager.get_instance()
        success = await manager.delete_file(filename)
        if success:
            return {"success": True, "message": f"Successfully deleted {filename}"}
        else:
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_files(request: SearchRequest) -> dict:
    """Search through profile files for matching content."""
    try:
        manager = ProfileManager.get_instance()
        results = await manager.search(request.query, request.filenames)

        formatted_results = []
        total_matches = 0

        for result in results:
            total_matches += result.total_matches
            formatted_results.append({
                "filename": result.filename,
                "matches_count": result.total_matches,
                "matches": [
                    {
                        "line": m.line_number,
                        "content": m.line_content.strip(),
                        "context": m.context.strip()
                    }
                    for m in result.matches[:10]  # Limit matches per file
                ]
            })

        return {
            "success": True,
            "query": request.query,
            "total_matches": total_matches,
            "files_matched": len(results),
            "results": formatted_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_summary(include_key_facts: bool = True) -> dict:
    """Get a summary of the user's profile.

    Returns overview information including:
    - Total files count
    - Files per category
    - Recent changes
    - Key facts (optional)
    """
    try:
        manager = ProfileManager.get_instance()
        summary = await manager.get_summary()

        result = {
            "success": True,
            "total_files": summary.total_files,
            "last_updated": summary.last_updated.isoformat() if summary.last_updated else None,
            "categories": summary.categories,
            "recent_changes": summary.recent_changes
        }

        if include_key_facts:
            result["key_facts"] = summary.key_facts

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/layers")
async def get_layers() -> dict:
    """Get information about profile layers."""
    manager = ProfileManager.get_instance()
    return {
        "success": True,
        "layers": [
            {"id": layer_id, "name": layer_name}
            for layer_id, layer_name in manager.LAYER_NAMES.items()
        ]
    }


@router.get("/changelog")
async def get_changelog(limit: int = 20) -> dict:
    """Get recent changes to profile files."""
    try:
        manager = ProfileManager.get_instance()
        content = await manager.read_file("_changelog.md")

        # Parse changelog entries
        changes = []
        lines = content.split('\n')
        count = 0

        for line in lines:
            if line.startswith('|') and not line.startswith('| 日期') and '---' not in line:
                parts = [p.strip() for p in line.split('|')[1:-1]]
                if len(parts) >= 3:
                    changes.append({
                        'date': parts[0],
                        'filename': parts[1],
                        'description': parts[2]
                    })
                    count += 1
                    if count >= limit:
                        break

        # Return in reverse order (newest first)
        return {
            "success": True,
            "changes": changes[::-1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def initialize_profile() -> dict:
    """Initialize the profile directory with default files.

    This creates all core profile files if they don't exist.
    """
    try:
        manager = ProfileManager.get_instance()
        await manager.initialize()
        return {
            "success": True,
            "message": "Profile initialized successfully",
            "profile_dir": str(manager.profile_dir)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
