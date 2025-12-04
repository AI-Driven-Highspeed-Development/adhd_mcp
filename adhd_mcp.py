"""
adhd_mcp - MCP Server

This module provides the MCP server entry point using FastMCP.
Run with: python -m mcps.adhd_mcp.adhd_mcp
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

# Create MCP server instance
mcp = FastMCP(
    name="adhd_mcp",
    instructions="TODO: Add description of this MCP server.",
)


# --- Tools ---


@mcp.tool()
def example_tool(message: str) -> dict:
    """Example tool - replace with your actual tools.
    
    Args:
        message: A sample message parameter
    
    Returns:
        dict with success status and message
    """
    return {"success": True, "message": message}


# --- Entry Point ---


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
