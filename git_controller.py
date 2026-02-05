"""
Git Controller - Git operations for ADHD MCP.

Handles git status, diff, pull, and push operations across modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from logger_util import Logger
from modules_controller_core import ModulesController, ModuleInfo

from .helpers import (
    get_git_status,
    get_git_remote_url,
    get_git_diff_stat,
    git_pull,
    git_commit_and_push,
)


class GitController:
    """Controller for git operations across ADHD modules."""

    def __init__(
        self,
        root_path: Path,
        modules_controller: ModulesController,
    ):
        self.root_path = root_path
        self.modules_controller = modules_controller
        self.logger = Logger(name=self.__class__.__name__)

    def git_modules(
        self,
        action: str = "status",
        module_name: str | None = None,
        layers: list[str] | None = None,
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        """Git operations across modules.

        Args:
            action: One of "status", "diff", "pull", "push"
            module_name: Specific module, or None for all
            layers: Filter by layer (e.g., ["foundation", "runtime"]), or None for all
            commit_message: Required for push action

        Returns:
            Dict with git operation results
        """
        valid_actions = ["status", "diff", "pull", "push"]
        if action not in valid_actions:
            return {
                "success": False,
                "error": "invalid_action",
                "message": f"action must be one of: {valid_actions}",
            }

        if action == "push" and not commit_message:
            return {
                "success": False,
                "error": "commit_message_required",
                "message": "commit_message is required for push action",
            }

        try:
            # Get modules to operate on
            if module_name:
                module = self.modules_controller.get_module_by_name(module_name)
                if not module:
                    return {
                        "success": False,
                        "error": "module_not_found",
                        "message": f"Module '{module_name}' not found",
                    }
                modules = [module]
            else:
                report = self.modules_controller.scan_all_modules()
                modules = [
                    m for m in report.modules
                    if not layers or m.layer.value in layers
                ]

            if action == "status":
                return self._git_status_action(modules)
            elif action == "diff":
                return self._git_diff_action(modules)
            elif action == "pull":
                return self._git_pull_action(modules)
            elif action == "push":
                return self._git_push_action(modules, commit_message)  # type: ignore
            else:
                return {
                    "success": False,
                    "error": "unknown_action",
                    "message": f"Unknown action: {action}",
                }
        except Exception as e:
            return {
                "success": False,
                "error": "git_error",
                "message": str(e),
            }

    def _git_status_action(self, modules: list[ModuleInfo]) -> dict[str, Any]:
        """Get git status for modules."""
        modules_data = []
        for module in modules:
            status = get_git_status(module.path)
            remote_url = get_git_remote_url(module.path)
            
            data: dict[str, Any] = {
                "name": module.name,
                "repo_url": module.repo_url,
                "remote_url": remote_url,
                "status": status.get("status", "unknown"),
                "branch": status.get("branch", "unknown"),
            }

            # Add extra fields based on status
            if status.get("status") == "dirty":
                data["changed"] = status.get("changed", 0)
                data["added"] = status.get("added", 0)
                data["deleted"] = status.get("deleted", 0)
            elif status.get("status") in ("ahead", "behind", "diverged"):
                if "commits" in status:
                    data["commits"] = status["commits"]
                if "ahead" in status:
                    data["ahead"] = status["ahead"]
                if "behind" in status:
                    data["behind"] = status["behind"]

            modules_data.append(data)

        return {
            "success": True,
            "modules": modules_data,
        }

    def _git_diff_action(self, modules: list[ModuleInfo]) -> dict[str, Any]:
        """Get detailed diff info for modules."""
        modules_data = []
        for module in modules:
            status = get_git_status(module.path)
            remote_url = get_git_remote_url(module.path)
            
            if status.get("status") != "dirty":
                continue

            changes = get_git_diff_stat(module.path)
            
            # Calculate summary
            total_ins = sum(c.get("insertions", 0) for c in changes)
            total_del = sum(c.get("deletions", 0) for c in changes)
            
            modules_data.append({
                "name": module.name,
                "repo_url": module.repo_url,
                "remote_url": remote_url,
                "status": "dirty",
                "branch": status.get("branch", "unknown"),
                "changes": changes,
                "diff_summary": f"+{total_ins} -{total_del} in {len(changes)} files",
            })

        return {
            "success": True,
            "modules": modules_data,
        }

    def _git_pull_action(self, modules: list[ModuleInfo]) -> dict[str, Any]:
        """Pull latest for modules."""
        pulled = []
        failed = []
        skipped = []

        for module in modules:
            status = get_git_status(module.path)
            
            # Skip if dirty
            if status.get("status") == "dirty":
                skipped.append({
                    "name": module.name,
                    "reason": "Has uncommitted changes",
                })
                continue

            # Skip if not a git repo
            if status.get("status") == "not_a_repo":
                skipped.append({
                    "name": module.name,
                    "reason": "Not a git repository",
                })
                continue

            result = git_pull(module.path)
            if result.get("success"):
                pulled.append({
                    "name": module.name,
                    "message": result.get("message", ""),
                })
            else:
                failed.append({
                    "name": module.name,
                    "error": result.get("error", "Unknown error"),
                })

        return {
            "success": len(failed) == 0,
            "pulled": pulled,
            "failed": failed,
            "skipped": skipped,
        }

    def _git_push_action(
        self,
        modules: list[ModuleInfo],
        commit_message: str,
    ) -> dict[str, Any]:
        """Commit and push for modules."""
        pushed = []
        failed = []
        skipped = []

        for module in modules:
            status = get_git_status(module.path)
            
            # Skip if not dirty
            if status.get("status") != "dirty":
                skipped.append({
                    "name": module.name,
                    "reason": "No changes to commit",
                })
                continue

            branch = status.get("branch", "main")
            result = git_commit_and_push(module.path, commit_message, branch)
            
            if result.get("success"):
                pushed.append({
                    "name": module.name,
                    "commit": result.get("commit", "unknown"),
                    "message": commit_message,
                })
            else:
                error = result.get("error", "Unknown error")
                if error == "nothing_to_commit":
                    skipped.append({
                        "name": module.name,
                        "reason": "No changes to commit",
                    })
                else:
                    failed.append({
                        "name": module.name,
                        "error": error,
                    })

        return {
            "success": len(failed) == 0,
            "pushed": pushed,
            "failed": failed,
            "skipped": skipped,
        }
