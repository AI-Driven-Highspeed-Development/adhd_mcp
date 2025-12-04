"""
Refresh script for adhd_mcp.

Registers this MCP server in .vscode/mcp.json.
Run via: python adhd_framework.py refresh --module adhd_mcp
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
if str(Path.cwd()) not in sys.path:
    sys.path.append(str(Path.cwd()))

from utils.logger_util.logger import Logger


def main() -> None:
    """Register this MCP in .vscode/mcp.json."""
    logger = Logger(name="adhd_mcpRefresh")
    logger.info("Starting adhd_mcp refresh...")

    try:
        mcp_json_path = Path.cwd() / ".vscode" / "mcp.json"
        
        # Ensure .vscode directory exists
        mcp_json_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing mcp.json or create new structure
        if mcp_json_path.exists():
            with open(mcp_json_path, "r", encoding="utf-8") as f:
                mcp_config = json.load(f)
        else:
            mcp_config = {"servers": {}}
        
        # Ensure servers key exists
        if "servers" not in mcp_config:
            mcp_config["servers"] = {}
        
        # MCP server configuration
        mcp_key = "adhd_mcp"
        module_path = "mcps.adhd_mcp.adhd_mcp"
        
        # Only add if not already present
        if mcp_key not in mcp_config["servers"]:
            mcp_config["servers"][mcp_key] = {
                "type": "stdio",
                "command": ".venv/bin/python",
                "args": ["-m", module_path],
                "cwd": "./"
            }
            
            # Write back with proper formatting
            with open(mcp_json_path, "w", encoding="utf-8") as f:
                json.dump(mcp_config, f, indent=2)
            
            logger.info(f"Added '{mcp_key}' to {mcp_json_path}")
        else:
            logger.info(f"'{mcp_key}' already exists in {mcp_json_path}, skipping")
        
        logger.info("adhd_mcp refresh completed successfully.")
    except Exception as e:
        logger.error(f"adhd_mcp refresh failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
