"""
Profile Tools - LangChain 1.0 compatible profile management tools

These tools allow the agent to read, write, and search user profile files.
Profile files are stored as Markdown files with YAML front matter for metadata.
"""

import json
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

from langchain_core.tools import tool

from services.profile_manager import ProfileManager


# ==================== Tool Input Schemas ====================

class ListProfileFilesInput(BaseModel):
    """Input schema for list_profile_files tool"""
    include_topics: bool = Field(
        default=True,
        description="Whether to include topic files from the topics/ directory"
    )
    layer: Optional[int] = Field(
        default=None,
        ge=0,
        le=6,
        description="Filter by layer (0=基础档案, 1=内在特质, 2=能力与发展, 3=生活方式, 4=社会关系, 5=记忆与洞察, 6=专题深入)"
    )


class ReadProfileInput(BaseModel):
    """Input schema for read_profile tool"""
    filename: str = Field(
        description="The filename to read (e.g., '00-basic-info.md' or 'topics/python-learning.md')"
    )


class WriteProfileInput(BaseModel):
    """Input schema for write_profile tool"""
    filename: str = Field(
        description="The filename to write (e.g., '00-basic-info.md' or 'topics/python-learning.md')"
    )
    content: str = Field(
        description="The complete Markdown content to write. Must include YAML front matter with title, summary, keywords, and confidence."
    )
    changelog_entry: str = Field(
        description="A brief description of what was changed (e.g., '更新职业信息：软件工程师')"
    )


class CreateProfileInput(BaseModel):
    """Input schema for create_profile tool"""
    filename: str = Field(
        description="The filename for the new file. For topic files, use 'topics/topic-name.md' format."
    )
    title: str = Field(
        description="The title for the new profile file (e.g., 'Python Learning Journey')"
    )
    description: str = Field(
        description="A brief description of what this file will contain"
    )
    initial_content: Optional[str] = Field(
        default=None,
        description="Optional: Initial Markdown content. If not provided, a template will be generated."
    )


class SearchProfileInput(BaseModel):
    """Input schema for search_profile tool"""
    query: str = Field(
        description="The search query (case-insensitive text search)"
    )
    filenames: Optional[List[str]] = Field(
        default=None,
        description="Optional: List of specific files to search. If not provided, searches all files."
    )


class GetProfileSummaryInput(BaseModel):
    """Input schema for get_profile_summary tool"""
    include_key_facts: bool = Field(
        default=True,
        description="Whether to include key facts from file summaries"
    )


class DeleteProfileInput(BaseModel):
    """Input schema for delete_profile tool"""
    filename: str = Field(
        description="The filename to delete. Only topic files can be deleted (e.g., 'topics/old-topic.md')"
    )


# ==================== Profile Tools ====================

@tool("list_profile_files", args_schema=ListProfileFilesInput)
async def list_profile_files(
    include_topics: bool = True,
    layer: Optional[int] = None
) -> str:
    """List all profile files in the user's profile directory.

    Profile files are organized into layers:
    - Layer 0: 基础档案 (Basic Info, Core Identity)
    - Layer 1: 内在特质 (Personality, Values, Cognitive Style)
    - Layer 2: 能力与发展 (Skills, Knowledge, Goals, Interests)
    - Layer 3: 生活方式 (Daily Patterns, Preferences, Health)
    - Layer 4: 社会关系 (Relationships, Projects, Social Context)
    - Layer 5: 记忆与洞察 (Key Memories, Patterns & Insights)
    - Layer 6: 专题深入 (Topic files in topics/ directory)

    Use this tool to discover available profile files before reading or updating them.
    """
    try:
        manager = ProfileManager.get_instance()
        files = await manager.list_files(include_topics=include_topics)

        # Filter by layer if specified
        if layer is not None:
            files = [f for f in files if f.layer == layer]

        # Group by layer for better organization
        files_by_layer = {}
        for f in files:
            layer_name = manager.LAYER_NAMES.get(f.layer, f"Layer {f.layer}")
            if layer_name not in files_by_layer:
                files_by_layer[layer_name] = []
            files_by_layer[layer_name].append({
                "filename": f.relative_path,
                "title": f.title,
                "summary": f.summary[:100] + "..." if len(f.summary) > 100 else f.summary,
                "confidence": f.confidence,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None
            })

        return json.dumps({
            "success": True,
            "total_files": len(files),
            "files_by_layer": files_by_layer
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "files_by_layer": {}
        })


@tool("read_profile", args_schema=ReadProfileInput)
async def read_profile(filename: str) -> str:
    """Read the content of a profile file.

    Use this tool to read a specific profile file's content. The content includes:
    - YAML front matter with metadata (title, summary, keywords, confidence)
    - Summary section with a brief overview
    - Key Points section with important facts
    - Details section with in-depth information
    - Evidence section tracking observation sources

    Before updating a file, always read it first to understand its current state.
    """
    try:
        manager = ProfileManager.get_instance()
        content = await manager.read_file(filename)

        # Get file metadata
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

        return json.dumps(result, ensure_ascii=False, indent=2)

    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "error": f"File not found: {filename}",
            "content": None
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "content": None
        })


@tool("write_profile", args_schema=WriteProfileInput)
async def write_profile(
    filename: str,
    content: str,
    changelog_entry: str
) -> str:
    """Write or update a profile file.

    Use this tool to update user profile information. The content must be in
    Markdown format with YAML front matter. Always read the file first with
    read_profile before making updates.

    YAML front matter format:
    ---
    title: "Title Here"
    summary: "Brief summary of the file content"
    keywords: [keyword1, keyword2]
    confidence: 0.8
    ---

    Guidelines for updating profile:
    - Preserve existing information unless correcting errors
    - Add new information with evidence sources
    - Update confidence levels based on evidence strength
    - Use changelog_entry to describe what changed
    """
    try:
        manager = ProfileManager.get_instance()
        await manager.write_file(filename, content, changelog_entry)

        return json.dumps({
            "success": True,
            "message": f"Successfully updated {filename}",
            "changelog_entry": changelog_entry
        }, ensure_ascii=False)

    except FileNotFoundError:
        return json.dumps({
            "success": False,
            "error": f"File not found: {filename}. Use create_profile to create a new file."
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@tool("create_profile", args_schema=CreateProfileInput)
async def create_profile(
    filename: str,
    title: str,
    description: str,
    initial_content: Optional[str] = None
) -> str:
    """Create a new profile file.

    Use this tool to create a new topic file when you discover significant
    information about the user that deserves its own dedicated file.

    Topic files should be created in the topics/ directory and named descriptively:
    - topics/python-learning.md
    - topics/fitness-journey.md
    - topics/startup-project.md

    If initial_content is not provided, a template will be generated.
    """
    try:
        manager = ProfileManager.get_instance()
        await manager.create_file(
            filename=filename,
            title=title,
            description=description,
            initial_content=initial_content
        )

        return json.dumps({
            "success": True,
            "message": f"Successfully created {filename}",
            "title": title,
            "description": description
        }, ensure_ascii=False)

    except FileExistsError:
        return json.dumps({
            "success": False,
            "error": f"File already exists: {filename}. Use write_profile to update it."
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@tool("search_profile", args_schema=SearchProfileInput)
async def search_profile(
    query: str,
    filenames: Optional[List[str]] = None
) -> str:
    """Search through profile files for matching content.

    Use this tool to find information across multiple profile files.
    The search is case-insensitive and returns matching lines with context.

    This is useful when you need to:
    - Find where specific information is stored
    - Check if information about a topic already exists
    - Gather related information from multiple files
    """
    try:
        manager = ProfileManager.get_instance()
        results = await manager.search(query, filenames)

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
                    for m in result.matches[:5]  # Limit matches per file
                ]
            })

        return json.dumps({
            "success": True,
            "query": query,
            "total_matches": total_matches,
            "files_matched": len(results),
            "results": formatted_results
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        })


@tool("get_profile_summary", args_schema=GetProfileSummaryInput)
async def get_profile_summary(include_key_facts: bool = True) -> str:
    """Get an overview of the user's profile.

    Use this tool to get a high-level understanding of what we know about the user.
    Returns:
    - Total number of profile files
    - Files per category/layer
    - Recent changes
    - Key facts extracted from file summaries

    This is useful at the start of a conversation or when planning what
    profile information to gather next.
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

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


@tool("delete_profile", args_schema=DeleteProfileInput)
async def delete_profile(filename: str) -> str:
    """Delete a profile file.

    Use this tool with caution. Only topic files (in the topics/ directory)
    can be deleted. Core profile files and system files cannot be deleted.

    This should only be used when:
    - A topic is no longer relevant
    - Information was duplicated and consolidated elsewhere
    - The file was created in error
    """
    try:
        manager = ProfileManager.get_instance()
        success = await manager.delete_file(filename)

        if success:
            return json.dumps({
                "success": True,
                "message": f"Successfully deleted {filename}"
            })
        else:
            return json.dumps({
                "success": False,
                "error": f"File not found: {filename}"
            })

    except PermissionError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })


# ==================== Tool Factory ====================

def get_profile_tools():
    """Get all profile management tools for the agent.

    Returns a list of tool functions decorated with @tool.
    These are compatible with LangChain 1.0's create_agent function.
    """
    return [
        list_profile_files,
        read_profile,
        write_profile,
        create_profile,
        search_profile,
        get_profile_summary,
        delete_profile,
    ]


def get_profile_tool_descriptions() -> dict:
    """Get descriptions of all profile tools."""
    tools = get_profile_tools()
    return {
        tool.name: tool.description
        for tool in tools
    }


# Legacy aliases for consistency
ListProfileFilesTool = list_profile_files
ReadProfileTool = read_profile
WriteProfileTool = write_profile
CreateProfileTool = create_profile
SearchProfileTool = search_profile
GetProfileSummaryTool = get_profile_summary
DeleteProfileTool = delete_profile
