"""
Debugger Agent
==============
Fetches error logs via the MCP tool and diagnoses the root cause.

IMPORTANT: The agent never calls the Dummy API directly.
It always goes through the MCP server's fetch_error_logs tool.

Flow:
    User reports error
        → Debugger Agent invoked
        → calls fetch_error_logs MCP tool
        → MCP server calls Dummy API (localhost:8001)
        → logs returned to agent
        → Groq LLM reads logs, returns diagnosis
"""

import json
import logging
import os
import sys
from pathlib import Path

import httpx
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

logger = logging.getLogger(__name__)

# MCP server URL — the agent calls this, not the Dummy API directly
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8002")

SYSTEM_PROMPT = """You are a debugging specialist for the Maveric platform.

When a user reports an error, failure, or unexpected behaviour:
1. ALWAYS call fetch_error_logs first — this retrieves chat history sessions
2. Read the chat sessions carefully:
   - Sessions show conversation IDs and message counts
   - Use the session ID to get detailed message history if needed
   - Messages contain user queries and assistant responses
3. Analyze the chat to understand what the user was trying to do
4. Provide a diagnosis based on their conversation history
5. Give specific steps to help resolve the issue

NOTE: Error logs have been replaced with chat history. 
Check the chat sessions to understand user interactions."""


def create_debugger_agent():
    """Build the Debugger Agent with fetch_error_logs MCP tool."""

    @tool
    async def fetch_error_logs(
        tenant_id: str = "00000000-0000-0000-3029-000000000001"
    ) -> str:
        """
        Fetch chat history sessions for a tenant (replaces error logs).

        This now returns chat sessions instead of error logs.
        Each session contains user messages and assistant responses
        that show what the user was trying to do.

        Always call this first when the user reports any error or failure.
        The chat history shows the conversation context needed to understand
        what went wrong.

        Args:
            tenant_id: The tenant UUID (use default if not specified).

        Returns:
            JSON string with chat sessions and metadata.
        """
        # Call the MCP server's HTTP endpoint
        # The MCP server then calls the Dummy API internally
        url = f"{MCP_SERVER_URL}/call_tool"
        payload = {
            "name": "fetch_error_logs",
            "arguments": {"tenant_id": tenant_id}
        }
        logger.info(f"Calling MCP tool via: {url}")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                # MCP returns result in content[0].text
                if isinstance(data, dict) and "content" in data:
                    return data["content"][0].get("text", json.dumps(data))
                return json.dumps(data)
        except httpx.HTTPError as e:
            logger.error(f"MCP call failed: {e}")
            return json.dumps({"error": f"MCP server error: {str(e)}"})

    llm = ChatGroq(
        model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        temperature=0.0,
    )

    return create_react_agent(
        model=llm,
        tools=[fetch_error_logs],
        prompt=SYSTEM_PROMPT,
    )


async def run_debugger_agent(query: str) -> str:
    """Run the Debugger Agent and return the final response string."""
    agent = create_debugger_agent()
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": query}]
    })
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and msg.content:
            if not getattr(msg, "tool_calls", None):
                return msg.content
    return "No response generated."