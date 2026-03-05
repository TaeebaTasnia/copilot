"""
MCP Server HTTP Bridge
======================
Exposes MCP tools via HTTP endpoints for testing and direct API access.

This is the bridge between the Debugger Agent and the Dummy API.
The agent can call tools either through:
  1. MCP protocol (when used as an MCP server)
  2. HTTP endpoints (for direct testing)

The Dummy API serves as the data backend.

Flow:
    Client (HTTP or MCP)
        → calls fetch_error_logs tool
        → this server sends GET to Dummy API
        → returns logs back to client

Run locally:
    python server.py
"""

import json
import logging
import os
import httpx
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# When running in Docker this will be http://dummy-api:8001
# When running locally this will be http://localhost:8001
DUMMY_API_URL = os.environ.get("DUMMY_API_URL", "http://localhost:8001")

# Create FastAPI app
app = FastAPI(title="NetAI Copilot MCP Server")


# Request models
class ToolCallRequest(BaseModel):
    name: str
    arguments: dict = {}


class ToolResponse(BaseModel):
    success: bool
    data: dict = None
    error: str = None


# Tool implementations - updated for chat history API
async def fetch_error_logs(tenant_id: str = "00000000-0000-0000-3029-000000000001") -> dict:
    """
    Fetch chat history for a tenant (replaced error logs with chat history).

    Args:
        tenant_id: The tenant UUID to fetch chat sessions for.

    Returns:
        List of chat sessions with message counts and metadata.
    """
    url = f"{DUMMY_API_URL}/chat/sessions/{tenant_id}"
    logger.info(f"Fetching chat sessions from API: {url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Got {data.get('session_count', 0)} chat sessions from API")
            
            # Return in a format that works with the existing agent
            return {
                "status": "success",
                "message": "Chat history has replaced error logs. See sessions below.",
                "sessions": data.get("sessions", []),
                "session_count": data.get("session_count", 0),
                "note": "Use /chat/messages/{session_id} to get messages in a specific session"
            }
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch chat sessions: {e}")
        raise HTTPException(status_code=502, detail=f"Dummy API error: {str(e)}")


async def fetch_chat_history(session_id: str) -> dict:
    """
    Fetch detailed chat history for a specific session.

    Args:
        session_id: The session UUID to fetch messages for.

    Returns:
        List of chat messages in chronological order.
    """
    url = f"{DUMMY_API_URL}/chat/messages/{session_id}"
    logger.info(f"Fetching chat history from API: {url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Got {data.get('message_count', 0)} messages from session: {session_id}")
            return data
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch chat history: {e}")
        raise HTTPException(status_code=502, detail=f"Dummy API error: {str(e)}")


# HTTP Routes
@app.post("/call_tool")
async def call_tool(request: ToolCallRequest) -> ToolResponse:
    """
    Call an MCP tool via HTTP.
    
    Example requests:
    {
        "name": "fetch_error_logs",
        "arguments": {"tenant_id": "test-tenant"}
    }
    
    OR:
    {
        "name": "fetch_chat_history",
        "arguments": {"session_id": "session-uuid"}
    }
    """
    try:
        tool_name = request.name
        arguments = request.arguments
        
        logger.info(f"HTTP call to tool: {tool_name} with args: {arguments}")
        
        if tool_name == "fetch_error_logs":
            # deprecated but kept for backward compatibility
            tenant_id = arguments.get("tenant_id", "00000000-0000-0000-3029-000000000001")
            data = await fetch_error_logs(tenant_id)
            return ToolResponse(success=True, data=data)
        
        elif tool_name == "fetch_chat_history":
            session_id = arguments.get("session_id", "")
            if not session_id:
                raise HTTPException(status_code=400, detail="session_id is required")
            data = await fetch_chat_history(session_id)
            return ToolResponse(success=True, data=data)
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "service": "mcp-server"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "NetAI Copilot MCP Server",
        "version": "1.0",
        "note": "Error logs have been replaced with chat history",
        "endpoints": {
            "health": "GET /health",
            "call_tool": "POST /call_tool",
            "docs": "GET /docs",
            "openapi": "GET /openapi.json"
        },
        "available_tools": [
            "fetch_error_logs (deprecated - now returns chat sessions)",
            "fetch_chat_history"
        ],
        "migration_info": {
            "old": "/v1/tenants/{tenant_id}/baselines/logs/errors (removed)",
            "new": "/chat/sessions/{tenant_id} and /chat/messages/{session_id}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8002))
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Starting MCP Server on {host}:{port}")
    logger.info(f"Dummy API backend: {DUMMY_API_URL}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


