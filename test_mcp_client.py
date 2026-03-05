"""
Simple MCP Client to test the MCP Server
"""
import asyncio
import json
import httpx

async def test_mcp_server():
    """Test the MCP server by sending a properly formatted MCP request"""
    
    # MCP uses JSON-RPC over HTTP
    # This is the correct format for calling tools on an MCP server
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "fetch_error_logs",
            "arguments": {
                "tenant_id": "test-tenant"
            }
        }
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "http://localhost:8002/",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())
