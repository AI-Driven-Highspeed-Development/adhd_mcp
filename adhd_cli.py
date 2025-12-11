"""CLI commands and registration for adhd_mcp.

Exposes ADHD MCP tools as CLI commands for command-line usage.
"""

from __future__ import annotations

import argparse
import json

from mcps.adhd_mcp.adhd_controller import AdhdController
from managers.cli_manager import CLIManager, ModuleRegistration, Command, CommandArg


# ─────────────────────────────────────────────────────────────────────────────
# Controller Access
# ─────────────────────────────────────────────────────────────────────────────

_controller: AdhdController | None = None


def _get_controller() -> AdhdController:
    """Get or create the controller instance."""
    global _controller
    if _controller is None:
        _controller = AdhdController()
    return _controller


def _print_result(result: dict) -> int:
    """Print result as JSON and return exit code."""
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("success", True) else 1


# ─────────────────────────────────────────────────────────────────────────────
# Handler Functions
# ─────────────────────────────────────────────────────────────────────────────

def project_info_cmd(args: argparse.Namespace) -> int:
    """Get project-level metadata."""
    result = _get_controller().get_project_info()
    return _print_result(result)


def list_modules_cmd(args: argparse.Namespace) -> int:
    """List discovered modules."""
    types = args.types.split(",") if args.types else None
    result = _get_controller().list_modules(
        include_cores=args.include_cores,
        types=types,
        with_imports=args.with_imports,
    )
    return _print_result(result)


def get_module_cmd(args: argparse.Namespace) -> int:
    """Get detailed info for a single module."""
    result = _get_controller().get_module_info(module_name=args.name)
    return _print_result(result)


def create_module_cmd(args: argparse.Namespace) -> int:
    """Create a new module."""
    result = _get_controller().create_module(
        name=args.name,
        module_type=args.type,
        create_repo=args.create_repo,
        owner=args.owner,
        template_url=args.template,
    )
    return _print_result(result)


def list_context_cmd(args: argparse.Namespace) -> int:
    """List AI context files."""
    result = _get_controller().list_context_files(
        file_type=args.file_type,
        include_modules=not args.core_only,
    )
    return _print_result(result)


def git_status_cmd(args: argparse.Namespace) -> int:
    """Get git status for modules."""
    result = _get_controller().git_modules(
        action="status",
        module_name=args.module,
        include_cores=args.include_cores,
    )
    return _print_result(result)


def git_diff_cmd(args: argparse.Namespace) -> int:
    """Get detailed git changes for modules."""
    result = _get_controller().git_modules(
        action="diff",
        module_name=args.module,
        include_cores=args.include_cores,
    )
    return _print_result(result)


def git_pull_cmd(args: argparse.Namespace) -> int:
    """Pull latest changes for modules."""
    result = _get_controller().git_modules(
        action="pull",
        module_name=args.module,
        include_cores=args.include_cores,
    )
    return _print_result(result)


def git_push_cmd(args: argparse.Namespace) -> int:
    """Commit and push changes for a module."""
    result = _get_controller().git_modules(
        action="push",
        module_name=args.module,
        commit_message=args.message,
    )
    return _print_result(result)


# ─────────────────────────────────────────────────────────────────────────────
# CLI Registration
# ─────────────────────────────────────────────────────────────────────────────

def register_cli() -> None:
    """Register adhd_mcp commands with CLIManager."""
    cli = CLIManager()
    cli.register_module(ModuleRegistration(
        module_name="adhd_mcp",
        short_name="adhd",
        description="ADHD framework project management CLI",
        commands=[
            Command(
                name="info",
                help="Get project-level metadata from root init.yaml",
                handler="mcps.adhd_mcp.adhd_cli:project_info_cmd",
            ),
            Command(
                name="modules",
                help="List discovered modules",
                handler="mcps.adhd_mcp.adhd_cli:list_modules_cmd",
                args=[
                    CommandArg(
                        name="--types",
                        short="-t",
                        help="Comma-separated module types: manager,util,mcp,plugin",
                    ),
                    CommandArg(
                        name="--include-cores",
                        short="-c",
                        action="store_true",
                        help="Include core modules",
                    ),
                    CommandArg(
                        name="--with-imports",
                        short="-i",
                        action="store_true",
                        help="Include import analysis",
                    ),
                ],
            ),
            Command(
                name="module",
                help="Get detailed info for a single module",
                handler="mcps.adhd_mcp.adhd_cli:get_module_cmd",
                args=[
                    CommandArg(name="name", help="Module name"),
                ],
            ),
            Command(
                name="create",
                help="Create a new module with scaffolding",
                handler="mcps.adhd_mcp.adhd_cli:create_module_cmd",
                args=[
                    CommandArg(name="name", help="Module name in snake_case"),
                    CommandArg(name="type", help="Module type: manager, util, plugin, mcp"),
                    CommandArg(
                        name="--create-repo",
                        short="-r",
                        action="store_true",
                        help="Create GitHub repository",
                    ),
                    CommandArg(name="--owner", short="-o", help="GitHub org/user for repo"),
                    CommandArg(name="--template", help="Template URL to use"),
                ],
            ),
            Command(
                name="context",
                help="List AI context files (instructions, agents, prompts)",
                handler="mcps.adhd_mcp.adhd_cli:list_context_cmd",
                args=[
                    CommandArg(
                        name="--file-type",
                        short="-t",
                        help="Filter by type: instruction, agent, prompt",
                        choices=["instruction", "agent", "prompt"],
                    ),
                    CommandArg(
                        name="--core-only",
                        action="store_true",
                        help="Only show core files, exclude per-module files",
                    ),
                ],
            ),
            Command(
                name="git-status",
                help="Get git status for modules",
                handler="mcps.adhd_mcp.adhd_cli:git_status_cmd",
                args=[
                    CommandArg(name="--module", short="-m", help="Specific module name"),
                    CommandArg(
                        name="--include-cores",
                        short="-c",
                        action="store_true",
                        help="Include core modules",
                    ),
                ],
            ),
            Command(
                name="git-diff",
                help="Get detailed git changes for modules",
                handler="mcps.adhd_mcp.adhd_cli:git_diff_cmd",
                args=[
                    CommandArg(name="--module", short="-m", help="Specific module name"),
                    CommandArg(
                        name="--include-cores",
                        short="-c",
                        action="store_true",
                        help="Include core modules",
                    ),
                ],
            ),
            Command(
                name="git-pull",
                help="Pull latest changes for modules",
                handler="mcps.adhd_mcp.adhd_cli:git_pull_cmd",
                args=[
                    CommandArg(name="--module", short="-m", help="Specific module name"),
                    CommandArg(
                        name="--include-cores",
                        short="-c",
                        action="store_true",
                        help="Include core modules",
                    ),
                ],
            ),
            Command(
                name="git-push",
                help="Commit and push changes for a module",
                handler="mcps.adhd_mcp.adhd_cli:git_push_cmd",
                args=[
                    CommandArg(name="module", help="Module name"),
                    CommandArg(name="message", help="Commit message"),
                ],
            ),
        ],
    ))
