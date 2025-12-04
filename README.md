# ADHD MCP

## Overview

The `adhd_mcp` is a **minimal, context-efficient** MCP server exposing ADHD framework capabilities. Each tool consumes context window, so we aim for **fewer, smarter tools** that provide *information for AI decision-making*.

### Design Principles

1. **Minimize Tool Count**: Only tools that can't be done with a simple CLI call
2. **Inform, Don't Automate**: Provide data for AI to make decisions
3. **No CLI Wrappers**: Agents can call `python adhd_framework.py refresh/workspace` directly
4. **Procedural Data, AI Judgment**: MCP scans/collects data; AI reasons about it

## Features

| Tool | Primary Use |
|------|-------------|
| `get_project_info` | Project-level metadata from root init.yaml |
| `list_modules` | Project introspection + batch dependency scan |
| `get_module_info` | Single module deep-dive with imports/git status |
| `create_module` | Scaffold new modules with optional GitHub repo |
| `list_context_files` | Find instructions/agents/prompts |
| `git_modules` | Git status/diff/pull/push across modules |

**Total: 6 tools**

## Usage

### Running the MCP Server

```bash
python -m mcps.adhd_mcp.adhd_mcp
```

### Tool Examples

#### Get Project Info
```python
get_project_info()
# Returns: {success, name, version, modules_registered, module_counts}
```

#### List Modules with Dependency Analysis
```python
list_modules(with_imports=True)
# Returns modules with imports categorized as adhd/third_party
# Compare imports.adhd vs init_yaml_requirements for missing deps
```

#### Get Single Module Details
```python
get_module_info("config_manager")
# Returns detailed info: imports, requirements, git status, issues
```

#### Create New Module
```python
create_module(
    name="my_new_manager",
    module_type="manager",
    create_repo=True,
    owner="AI-Driven-Highspeed-Development"
)
```

#### Git Operations
```python
# Check status of all modules
git_modules(action="status")

# Get detailed diffs for commit message crafting
git_modules(action="diff")

# Push a specific module
git_modules(action="push", module_name="kanbn_mcp", commit_message="feat: add batch tasks")

# Pull all modules
git_modules(action="pull")
```

### Dependency Analysis Workflow

1. `list_modules(with_imports=True)` - Scan all imports
2. Compare `imports.adhd` vs `init_yaml_requirements` → find missing ADHD deps
3. Compare `imports.third_party` vs `requirements_txt` → find missing PyPI packages
4. AI decides what to add and edits files directly

## Module Structure

```
mcps/adhd_mcp/
├── __init__.py           # Package exports
├── adhd_mcp.py           # FastMCP server with tool decorators
├── adhd_controller.py    # Business logic implementation
├── helpers.py            # Import scanning and git utilities
├── init.yaml             # Module metadata
├── README.md             # This file
├── refresh.py            # Module refresh script
└── requirements.txt      # MCP-specific dependencies
```

## What This Replaces

| Old Prompt/Tool | New MCP Tool |
|-----------------|--------------|
| `pull_modules.prompt.md` | `git_modules(action="pull")` |
| `push_modules.prompt.md` | `git_modules(action="diff")` → agent crafts message → `git_modules(action="push")` |
| `update_requirements.prompt.md` | `list_modules(with_imports=True)` → agent edits files |
| Manual CLI: `python adhd_framework.py refresh` | *(Still use CLI - not wrapped)* |

## CLI Commands (Not Wrapped)

These remain as CLI commands - agents should call them directly:

```bash
python adhd_framework.py refresh           # Refresh all modules
python adhd_framework.py refresh -m module # Refresh specific module  
python adhd_framework.py workspace         # Generate workspace file
python adhd_framework.py workspace --all   # Include all modules
```