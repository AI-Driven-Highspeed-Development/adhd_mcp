"""
adhd_mcp - MCP Module

Model Context Protocol server module.

Usage as MCP Server:
    python -m mcps.adhd_mcp.adhd_mcp

Refresh to register in .vscode/mcp.json:
    python adhd_framework.py refresh --module adhd_mcp
"""

from .adhd_mcp import mcp

__all__ = [
    'mcp'
]