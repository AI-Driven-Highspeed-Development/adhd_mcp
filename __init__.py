"""
adhd_mcp - MCP Module

Model Context Protocol server module.

Usage as MCP Server:
    python -m mcps.adhd_mcp.adhd_mcp

Refresh to register in .vscode/mcp.json:
    python adhd_framework.py refresh --module adhd_mcp
"""

import os
import sys

# Add path handling to work from the new nested directory structure
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.getcwd()  # Use current working directory as project root
sys.path.insert(0, project_root)

from mcps.adhd_mcp.adhd_mcp_server import mcp

__all__ = [
    'mcp'
]