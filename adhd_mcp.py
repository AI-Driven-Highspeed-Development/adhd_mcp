"""
adhd_mcp - ADHD Framework MCP Server

A minimal, context-efficient MCP exposing ADHD framework capabilities.
Provides information for AI decision-making with fewer, smarter tools.

Run with: python -m mcps.adhd_mcp.adhd_mcp
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .adhd_controller import AdhdController

# Create MCP server instance
mcp = FastMCP(
    name="adhd_mcp",
    instructions=(
        "ADHD Framework MCP server. "
        "Provides project introspection, module management, and git operations "
        "for AI-Driven Highspeed Development framework projects."
    ),
)

# Module-level controller instance
_controller: AdhdController | None = None


def _get_controller() -> AdhdController:
    """Get or create the AdhdController instance."""
    global _controller
    if _controller is None:
        _controller = AdhdController()
    return _controller


# --- Tool 1: get_project_info ---


@mcp.tool()
def get_project_info() -> dict:
    """Get project-level metadata from root init.yaml.

    Returns project name, version, registered module URLs, and counts by type.
    Use this to understand the overall project structure.

    Returns:
        dict with success, name, version, modules_registered, module_counts
    """
    return _get_controller().get_project_info()


# --- Tool 2: list_modules ---


@mcp.tool()
def list_modules(
    layers: list[str] | None = None,
    with_imports: bool = False,
) -> dict:
    """List discovered modules with optional filtering.

    Args:
        layers: Filter by layer (e.g., ["foundation", "runtime", "dev"]), or None for all
        with_imports: Include Python imports scan for dependency analysis

    Returns:
        dict with count and modules list. Each module has name, layer, version, path, repo_url.
        If with_imports=True, also includes imports, init_yaml_requirements, requirements_txt.

    Examples:
        - list_modules() - Quick overview of all modules
        - list_modules(with_imports=True) - Full dependency analysis
        - list_modules(layers=["foundation"]) - Just foundation modules
    """
    return _get_controller().list_modules(
        layers=layers,
        with_imports=with_imports,
    )


# --- Tool 3: get_module_info ---


@mcp.tool()
def get_module_info(module_name: str) -> dict:
    """Get detailed info for a single module.

    Always includes imports, requirements, and git status.
    Use this for deep-dive into a specific module's dependencies.

    Args:
        module_name: Name of the module (e.g., "config_manager", "kanbn_mcp")

    Returns:
        dict with detailed module info including:
        - Basic: name, type, version, path, repo_url, remote_url
        - Git: git_status (clean/dirty/ahead/behind), git_branch, git_changes
        - Imports: stdlib, adhd, third_party, local imports
        - Requirements: init_yaml_requirements, requirements_txt
        - Issues: Any validation issues

    Use imports.adhd vs init_yaml_requirements to find missing ADHD deps.
    Use imports.third_party vs requirements_txt to find missing PyPI packages.
    """
    return _get_controller().get_module_info(module_name=module_name)


# --- Tool 4: create_module ---


@mcp.tool()
def create_module(
    name: str,
    layer: str,
    is_mcp: bool = False,
    create_repo: bool = False,
    owner: str | None = None,
) -> dict:
    """Create a new module with scaffolding.

    Args:
        name: Module name in snake_case (e.g., "my_new_manager")
        layer: One of: "foundation", "runtime", "dev"
        is_mcp: Whether this is an MCP module (creates additional MCP files)
        create_repo: Whether to create a GitHub repository
        owner: GitHub org/user for repo (required if create_repo=True)

    Returns:
        On success: dict with name, layer, path, files_created, repo_url (if created)
        If create_repo=True but owner missing: returns available_owners list

    The scaffolding creates:
        - __init__.py, init.yaml, README.md, .config_template
        - For MCPs: also creates <name>_mcp.py and refresh.py
    """
    return _get_controller().create_module(
        name=name,
        layer=layer,
        is_mcp=is_mcp,
        create_repo=create_repo,
        owner=owner,
    )


# --- Tool 5: list_context_files ---


@mcp.tool()
def list_context_files(
    file_type: str | None = None,
    include_modules: bool = True,
) -> dict:
    """List AI context files (instructions, agents, prompts).

    Args:
        file_type: Filter by type: "instruction", "agent", "prompt", or None for all
        include_modules: Include per-module files, not just core (default: True)

    Returns:
        dict with arrays for each type (omitted if filtering):
        - instructions: [{name, path, source}]
        - agents: [{name, path, source}]
        - prompts: [{name, path, source}]

    Source indicates where the file came from: "core", "synced", or module name.
    """
    return _get_controller().list_context_files(
        file_type=file_type,
        include_modules=include_modules,
    )


# --- Tool 6: git_modules ---


@mcp.tool()
def git_modules(
    action: str = "status",
    module_name: str | None = None,
    layers: list[str] | None = None,
    commit_message: str | None = None,
) -> dict:
    """Git operations across modules.

    Args:
        action: One of:
            - "status": Overview (dirty/clean/ahead/behind + file counts)
            - "diff": Detailed changes per module (for crafting commit messages)
            - "pull": Pull latest (skips dirty modules)
            - "push": Commit and push (requires commit_message)
        module_name: Specific module, or None for all
        layers: Filter by layer (e.g., ["foundation", "runtime"]), or None for all
        commit_message: Required for push action

    Returns:
        For status: modules list with status, branch, change counts
        For diff: modules list with detailed file changes and diff_summary
        For pull/push: pushed/failed/skipped lists with details

    Workflow for pushing changes:
        1. Call git_modules(action="diff") to see changes
        2. Analyze changes and craft commit message
        3. Call git_modules(action="push", module_name="...", commit_message="...")

    Note: For push, call once per module with its specific commit message.
    """
    return _get_controller().git_modules(
        action=action,
        module_name=module_name,
        layers=layers,
        commit_message=commit_message,
    )


# --- Entry Point ---


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
