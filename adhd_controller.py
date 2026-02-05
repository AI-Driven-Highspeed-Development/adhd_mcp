"""
ADHD MCP Controller - Business logic for ADHD framework MCP tools.

This controller provides the implementation for all adhd_mcp tools:
- get_project_info: Get root project metadata
- list_modules: List modules with filtering
- get_module_info: Get detailed module info
- create_module: Scaffold new modules
- list_context_files: List instructions, agents, prompts (delegates to ContextController)
- git_modules: Git operations across modules (delegates to GitController)
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

import yaml

from config_manager import ConfigManager
from logger_util import Logger
from modules_controller_core import ModulesController, ModuleInfo
from module_creator_core import ModuleCreator, ModuleCreationParams
from creator_common_core import RepoCreationOptions
from github_api_core import GithubApi

from .helpers import (
    scan_module_imports,
    parse_requirements_txt,
    get_git_status,
    get_git_remote_url,
)
from .git_controller import GitController
from .context_controller import ContextController


class AdhdController:
    """Controller for ADHD framework MCP operations.
    
    Delegates git operations to GitController and context file operations
    to ContextController for better separation of concerns.
    """

    def __init__(self, root_path: Path | str | None = None):
        self.root_path = Path(root_path).resolve() if root_path else Path.cwd().resolve()
        self.logger = Logger(name=self.__class__.__name__)
        self._modules_controller: ModulesController | None = None
        self._git_controller: GitController | None = None
        self._context_controller: ContextController | None = None

    @property
    def modules_controller(self) -> ModulesController:
        """Lazy-load the modules controller."""
        if self._modules_controller is None:
            self._modules_controller = ModulesController(root_path=self.root_path)
        return self._modules_controller

    @property
    def git_controller(self) -> GitController:
        """Lazy-load the git controller."""
        if self._git_controller is None:
            self._git_controller = GitController(
                root_path=self.root_path,
                modules_controller=self.modules_controller,
            )
        return self._git_controller

    @property
    def context_controller(self) -> ContextController:
        """Lazy-load the context controller."""
        if self._context_controller is None:
            self._context_controller = ContextController(
                root_path=self.root_path,
                modules_controller=self.modules_controller,
            )
        return self._context_controller

    # --- Tool 1: get_project_info ---

    def get_project_info(self) -> dict[str, Any]:
        """Get project-level metadata from root init.yaml.

        Returns:
            Dict with project name, version, registered modules, and module counts
        """
        init_path = self.root_path / "init.yaml"
        if not init_path.exists():
            return {
                "success": False,
                "error": "init_yaml_not_found",
                "message": f"No init.yaml found at {init_path}",
            }

        try:
            with open(init_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # Get module counts from actual scan
            report = self.modules_controller.scan_all_modules()
            counts: dict[str, int] = {}
            for module in report.modules:
                folder = module.folder
                counts[folder] = counts.get(folder, 0) + 1

            return {
                "success": True,
                "name": data.get("name", self.root_path.name),
                "version": data.get("version", "0.0.0"),
                "description": data.get("description", ""),
                "modules_registered": data.get("modules", []),
                "module_counts": counts,
            }
        except Exception as e:
            return {
                "success": False,
                "error": "read_error",
                "message": str(e),
            }

    # --- Tool 2: list_modules ---

    def list_modules(
        self,
        layers: list[str] | None = None,
        with_imports: bool = False,
    ) -> dict[str, Any]:
        """List discovered modules with optional filtering.

        Args:
            layers: Filter by layer (e.g., ["foundation", "runtime", "dev"]), or None for all
            with_imports: Include Python imports scan (for dependency analysis)

        Returns:
            Dict with count and list of module info dicts
        """
        try:
            report = self.modules_controller.scan_all_modules()
            modules_data: list[dict[str, Any]] = []

            for module in report.modules:
                # Filter by layer
                if layers and module.layer.value not in layers:
                    continue

                module_data = self._build_module_summary(module, with_imports=with_imports)
                modules_data.append(module_data)

            return {
                "success": True,
                "count": len(modules_data),
                "modules": modules_data,
            }
        except Exception as e:
            return {
                "success": False,
                "error": "scan_error",
                "message": str(e),
            }

    def _build_module_summary(
        self,
        module: ModuleInfo,
        with_imports: bool = False,
    ) -> dict[str, Any]:
        """Build a summary dict for a module."""
        data: dict[str, Any] = {
            "name": module.name,
            "layer": module.layer.value,
            "is_mcp": module.is_mcp,
            "version": module.version,
            "path": str(module.path.relative_to(self.root_path)),
            "repo_url": module.repo_url,
            "has_issues": len(module.issues) > 0,
        }

        if with_imports:
            imports = scan_module_imports(module.path)
            data["imports"] = {
                "adhd": imports.get("adhd", []),
                "third_party": imports.get("third_party", []),
            }
            data["init_yaml_requirements"] = module.requirements
            
            req_path = module.path / "requirements.txt"
            data["requirements_txt"] = parse_requirements_txt(req_path)

        return data

    # --- Tool 3: get_module_info ---

    def get_module_info(self, module_name: str) -> dict[str, Any]:
        """Get detailed module info including imports, requirements, git status.

        Args:
            module_name: Name of the module to get info for

        Returns:
            Dict with detailed module information
        """
        if not module_name:
            return {
                "success": False,
                "error": "invalid_argument",
                "message": "module_name is required and cannot be empty",
            }
        module = self.modules_controller.get_module_by_name(module_name)
        if not module:
            # Suggest similar module names
            suggestions = self._suggest_module_names(module_name)
            result: dict[str, Any] = {
                "success": False,
                "error": "module_not_found",
                "message": f"Module '{module_name}' not found",
            }
            if suggestions:
                result["suggestions"] = suggestions
                result["message"] += f". Did you mean: {', '.join(suggestions)}?"
            return result

        try:
            # Get imports (always included for get_module_info)
            imports = scan_module_imports(module.path)
            
            # Get git status
            git_status = get_git_status(module.path)
            remote_url = get_git_remote_url(module.path)

            # Get requirements
            req_path = module.path / "requirements.txt"
            requirements_txt = parse_requirements_txt(req_path)

            result: dict[str, Any] = {
                "success": True,
                "name": module.name,
                "layer": module.layer.value,
                "is_mcp": module.is_mcp,
                "version": module.version,
                "path": str(module.path.relative_to(self.root_path)),
                "repo_url": module.repo_url,
                "remote_url": remote_url,
                "git_status": git_status.get("status", "unknown"),
                "git_branch": git_status.get("branch", "unknown"),
                "imports": imports,
                "init_yaml_requirements": module.requirements,
                "requirements_txt": requirements_txt,
                "issues": [
                    {"code": issue.code, "message": issue.message}
                    for issue in module.issues
                ],
            }

            # Add git change counts if dirty
            if git_status.get("status") == "dirty":
                result["git_changes"] = (
                    git_status.get("changed", 0) +
                    git_status.get("added", 0) +
                    git_status.get("deleted", 0)
                )

            return result
        except Exception as e:
            return {
                "success": False,
                "error": "info_error",
                "message": str(e),
                "module": module_name,
            }

    # --- Tool 4: create_module ---

    def create_module(
        self,
        name: str,
        layer: str,
        is_mcp: bool = False,
        create_repo: bool = False,
        owner: str | None = None,
    ) -> dict[str, Any]:
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
        from modules_controller_core import LAYER_SUBFOLDERS

        if layer not in LAYER_SUBFOLDERS:
            return {
                "success": False,
                "error": "invalid_layer",
                "message": f"Layer must be one of: {list(LAYER_SUBFOLDERS)}",
            }

        if create_repo and not owner:
            # Try to get available owners
            try:
                api = GithubApi()
                user_login = api.get_authenticated_user_login()
                orgs = api.get_user_orgs()
                
                available_owners = [{"type": "user", "login": user_login}]
                for org in orgs:
                    available_owners.append({
                        "type": "org",
                        "login": org.get("login", ""),
                    })

                return {
                    "success": False,
                    "error": "owner_required",
                    "message": "Specify 'owner' parameter to create GitHub repo",
                    "available_owners": available_owners,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": "owner_required",
                    "message": f"Specify 'owner' parameter. Failed to list owners: {e}",
                }

        try:
            creator = ModuleCreator()
            
            repo_options: RepoCreationOptions | None = None
            if create_repo and owner:
                repo_options = RepoCreationOptions(
                    owner=owner,
                    visibility="public",
                )

            params = ModuleCreationParams(
                module_name=name,
                layer=layer,
                is_mcp=is_mcp,
                repo_options=repo_options,
            )

            target_path = creator.create(params)

            # Get list of created files
            files_created = [
                f.name for f in target_path.iterdir()
                if f.is_file() and not f.name.startswith(".")
            ]

            result: dict[str, Any] = {
                "success": True,
                "name": name,
                "layer": layer,
                "is_mcp": is_mcp,
                "path": str(target_path.relative_to(self.root_path)),
                "files_created": files_created,
            }

            if repo_options and repo_options.repo_url:
                result["repo_url"] = repo_options.repo_url

            return result
        except Exception as e:
            return {
                "success": False,
                "error": "creation_error",
                "message": str(e),
            }

    def _suggest_module_names(self, name: str, max_suggestions: int = 3) -> list[str]:
        """Suggest similar module names using fuzzy matching."""
        try:
            report = self.modules_controller.scan_all_modules()
            all_names = [m.name for m in report.modules]
            return difflib.get_close_matches(name, all_names, n=max_suggestions, cutoff=0.4)
        except Exception:
            return []

    # --- Tool 5: list_context_files (delegates to ContextController) ---

    def list_context_files(
        self,
        file_type: str | None = None,
        include_modules: bool = True,
    ) -> dict[str, Any]:
        """List AI context files (instructions, agents, prompts).

        Args:
            file_type: Filter by type: "instruction", "agent", "prompt", or None for all
            include_modules: Include module-specific files

        Returns:
            Dict with lists of files by type
        """
        return self.context_controller.list_context_files(
            file_type=file_type,
            include_modules=include_modules,
        )

    # --- Tool 6: git_modules (delegates to GitController) ---

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
        return self.git_controller.git_modules(
            action=action,
            module_name=module_name,
            layers=layers,
            commit_message=commit_message,
        )


# Module-level singleton
_controller: AdhdController | None = None


def get_adhd_controller(root_path: Path | str | None = None) -> AdhdController:
    """Get or create the AdhdController singleton."""
    global _controller
    if _controller is None:
        _controller = AdhdController(root_path=root_path)
    return _controller
