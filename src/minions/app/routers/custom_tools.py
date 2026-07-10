# -*- coding: utf-8 -*-
"""API routes for custom (user-defined) tools management.

Custom tools are ``.py`` files in ``~/.minions/custom_tools/`` that use
``@tool_descriptor``.  This router provides CRUD + reload so users can
create, edit, delete and hot-reload tools from the console UI without
touching core code.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path
from pydantic import BaseModel, Field

from ...agents.tools.custom_loader import (
    CUSTOM_TOOLS_DIR,
    delete_custom_tool_file,
    list_custom_tool_files,
    read_custom_tool_file,
    reload_custom_tool,
    save_custom_tool_file,
)

router = APIRouter(prefix="/custom-tools", tags=["custom-tools"])

# Default template shown when creating a new custom tool.
TOOL_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Custom tool: {name}."""

from agentscope.message import TextBlock, ToolResultState
from agentscope.tool import ToolChunk

from minions.runtime.tool_registry import tool_descriptor


@tool_descriptor()
async def {name}(query: str) -> ToolChunk:
    """TODO: describe what this tool does.

    Args:
        query (str): The input query.
    """
    # Your tool logic here
    result = f"Echo: {{query}}"
    return ToolChunk(
        is_last=True,
        state=ToolResultState.SUCCESS,
        content=[TextBlock(type="text", text=result)],
    )
'''


class CustomToolFile(BaseModel):
    """Metadata for a custom tool file on disk."""

    name: str = Field(..., description="Tool file stem (without .py)")
    filename: str = Field(..., description="File name including .py")
    size: int = Field(..., description="File size in bytes")
    modified_time: float = Field(..., description="Last modified epoch")


class CustomToolContent(BaseModel):
    """Full content of a custom tool file."""

    name: str
    content: str
    size: int
    modified_time: float


class CreateCustomToolRequest(BaseModel):
    """Request body for creating a custom tool."""

    name: str = Field(..., description="Tool file name (without .py)")
    content: str = Field(default="", description="Python source code")


class UpdateCustomToolRequest(BaseModel):
    """Request body for updating a custom tool."""

    content: str = Field(..., description="New Python source code")


@router.get(
    "",
    response_model=list[CustomToolFile],
    summary="List custom tools",
)
async def list_custom_tools() -> list[CustomToolFile]:
    """List all custom tool files on disk."""
    files = list_custom_tool_files()
    return [CustomToolFile(**f) for f in files]


@router.post(
    "",
    response_model=CustomToolContent,
    summary="Create a custom tool",
)
async def create_custom_tool(
    body: CreateCustomToolRequest = Body(...),
) -> CustomToolContent:
    """Create a new custom tool file.

    If *content* is empty a template is generated from the tool name.
    The tool is saved but not yet loaded into the running agent - call
    the reload endpoint (or restart) to activate it.
    """
    content = body.content.strip()
    if not content:
        content = TOOL_TEMPLATE.format(name=body.name)
    try:
        path = save_custom_tool_file(body.name, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    stat = path.stat()
    return CustomToolContent(
        name=body.name,
        content=content,
        size=stat.st_size,
        modified_time=stat.st_mtime,
    )


@router.get(
    "/{name}",
    response_model=CustomToolContent,
    summary="Read a custom tool",
)
async def get_custom_tool(
    name: str = Path(..., description="Tool file stem (without .py)"),
) -> CustomToolContent:
    """Read the source code of a custom tool file."""
    try:
        content = read_custom_tool_file(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    path = CUSTOM_TOOLS_DIR / f"{name}.py"
    stat = path.stat()
    return CustomToolContent(
        name=name,
        content=content,
        size=stat.st_size,
        modified_time=stat.st_mtime,
    )


@router.put(
    "/{name}",
    response_model=CustomToolContent,
    summary="Update a custom tool",
)
async def update_custom_tool(
    name: str = Path(..., description="Tool file stem (without .py)"),
    body: UpdateCustomToolRequest = Body(...),
) -> CustomToolContent:
    """Update the source code of a custom tool file."""
    try:
        path = save_custom_tool_file(name, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    stat = path.stat()
    return CustomToolContent(
        name=name,
        content=body.content,
        size=stat.st_size,
        modified_time=stat.st_mtime,
    )


@router.delete(
    "/{name}",
    response_model=dict,
    summary="Delete a custom tool",
)
async def delete_custom_tool(
    name: str = Path(..., description="Tool file stem (without .py)"),
) -> dict:
    """Delete a custom tool file and unload it."""
    try:
        delete_custom_tool_file(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"deleted": True, "name": name}


@router.post(
    "/{name}/reload",
    response_model=dict,
    summary="Reload a custom tool",
)
async def reload_custom_tool_endpoint(
    name: str = Path(..., description="Tool file stem (without .py)"),
) -> dict[str, Any]:
    """Hot-reload a custom tool file into the running process.

    This re-imports the ``.py`` file so that ``@tool_descriptor`` picks
    up the latest version.  A full agent reload is needed for the new
    tool to take effect in active sessions.
    """
    try:
        success = reload_custom_tool(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "reloaded": success,
        "name": name,
        "time": time.time(),
    }
