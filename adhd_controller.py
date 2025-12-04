"""
ADHD MCP Controller - Business logic for ADHD framework MCP tools.

This controller provides the implementation for all adhd_mcp tools:
- get_project_info: Get root project metadata
- list_modules: List modules with filtering
- get_module_info: Get detailed module info
- create_module: Scaffold new modules
- list_context_files: List instructions, agents, prompts
- git_modules: Git operations across modules
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.logger_util.logger import Logger
from cores.modules_controller_core.modules_controller import ModulesController, ModuleInfo
from cores.yaml_reading_core.yaml_reading import YamlReadingCore as YamlReader
from cores.module_creator_core.module_creator import ModuleCreator, ModuleCreationParams
from cores.creator_common_core.creator_common_core import RepoCreationOptions
from cores.github_api_core.api import GithubApi

from mcps.adhd_mcp.helpers import (
    scan_module_imports,
    parse_requirements_txt,
    get_git_status,
    get_git_remote_url,
    get_git_diff_stat,
    git_pull,
    git_commit_and_push,
)


class AdhdController:
    """Controller for ADHD framework MCP operations."""

    def __init__(self, root_path: Path | str | None = None):
        self.root_path = Path(root_path).resolve() if root_path else Path.cwd().resolve()
        self.logger = Logger(name=self.__class__.__name__)
        self._modules_controller: ModulesController | None = None

    @property
    def modules_controller(self) -> ModulesController:
        """Lazy-load the modules controller."""
        if self._modules_controller is None:
            self._modules_controller = ModulesController(root_path=self.root_path)
        return self._modules_controller

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
            yf = YamlReader.read_yaml(init_path)
            if not yf:
                return {
                    "success": False,
                    "error": "invalid_init_yaml",
                    "message": "Failed to parse init.yaml",
                }

            data = yf.to_dict()
            
            # Get module counts from actual scan
            report = self.modules_controller.scan_all_modules()
            counts: dict[str, int] = {}
            for module in report.modules:
                type_name = module.module_type.name
                counts[type_name] = counts.get(type_name, 0) + 1

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
        include_cores: bool = False,
        types: list[str] | None = None,
        with_imports: bool = False,
    ) -> dict[str, Any]:
        """List discovered modules with optional filtering.

        Args:
            include_cores: Include cores/ modules (default: False)
            types: Filter by module types, or None for all
            with_imports: Include Python imports scan (for dependency analysis)

        Returns:
            Dict with count and list of module info dicts
        """
        try:
            report = self.modules_controller.scan_all_modules()
            modules_data: list[dict[str, Any]] = []

            for module in report.modules:
                # Filter by type
                type_name = module.module_type.name
                if not include_cores and type_name == "core":
                    continue
                if types and type_name not in types:
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
            "type": module.module_type.name,
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
        module = self.modules_controller.get_module_by_name(module_name)
        if not module:
            return {
                "success": False,
                "error": "module_not_found",
                "message": f"Module '{module_name}' not found",
            }

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
                "type": module.module_type.name,
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
        module_type: str,
        create_repo: bool = False,
        owner: str | None = None,
    ) -> dict[str, Any]:
        """Create a new module with scaffolding.

        Args:
            name: Module name (snake_case with type suffix)
            module_type: One of: manager, util, plugin, mcp
            create_repo: Whether to create GitHub repo
            owner: GitHub owner (required if create_repo=True)

        Returns:
            Dict with success status and created module info
        """
        valid_types = ["manager", "util", "plugin", "mcp", "core"]
        if module_type not in valid_types:
            return {
                "success": False,
                "error": "invalid_type",
                "message": f"Module type must be one of: {valid_types}",
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
                module_type=module_type,
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
                "type": module_type,
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

    # --- Tool 5: list_context_files ---

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
        valid_types = ["instruction", "agent", "prompt", None]
        if file_type not in valid_types:
            return {
                "success": False,
                "error": "invalid_type",
                "message": f"file_type must be one of: {valid_types}",
            }

        try:
            result: dict[str, Any] = {"success": True}

            # Core paths
            core_data_path = self.root_path / "cores" / "instruction_core" / "data"
            github_path = self.root_path / ".github"

            def scan_files(
                pattern: str,
                source: str,
                search_path: Path,
            ) -> list[dict[str, str]]:
                """Scan for files matching pattern."""
                files = []
                if search_path.exists():
                    for f in search_path.glob(pattern):
                        files.append({
                            "name": f.stem,
                            "path": str(f.relative_to(self.root_path)),
                            "source": source,
                        })
                return files

            # Scan instructions
            if file_type is None or file_type == "instruction":
                instructions = []
                # Core instructions
                instructions.extend(scan_files(
                    "*.instructions.md",
                    "core",
                    core_data_path / "instructions",
                ))
                # GitHub synced instructions
                instructions.extend(scan_files(
                    "*.instructions.md",
                    "synced",
                    github_path / "instructions",
                ))
                # Module instructions (if requested)
                if include_modules:
                    report = self.modules_controller.list_all_modules()
                    for module in report.modules:
                        instructions.extend(scan_files(
                            f"{module.name}.instructions.md",
                            module.name,
                            module.path,
                        ))
                result["instructions"] = instructions

            # Scan agents
            if file_type is None or file_type == "agent":
                agents = []
                # Core agents
                agents.extend(scan_files(
                    "*.agent.md",
                    "core",
                    core_data_path / "agents",
                ))
                # GitHub synced agents
                agents.extend(scan_files(
                    "*.agent.md",
                    "synced",
                    github_path / "agents",
                ))
                # Module agents
                if include_modules:
                    report = self.modules_controller.list_all_modules()
                    for module in report.modules:
                        agents.extend(scan_files(
                            "*.agent.md",
                            module.name,
                            module.path,
                        ))
                result["agents"] = agents

            # Scan prompts
            if file_type is None or file_type == "prompt":
                prompts = []
                # Core prompts
                prompts.extend(scan_files(
                    "*.prompt.md",
                    "core",
                    core_data_path / "prompts",
                ))
                # GitHub synced prompts
                prompts.extend(scan_files(
                    "*.prompt.md",
                    "synced",
                    github_path / "prompts",
                ))
                # Module prompts
                if include_modules:
                    report = self.modules_controller.list_all_modules()
                    for module in report.modules:
                        prompts.extend(scan_files(
                            "*.prompt.md",
                            module.name,
                            module.path,
                        ))
                result["prompts"] = prompts

            return result
        except Exception as e:
            return {
                "success": False,
                "error": "scan_error",
                "message": str(e),
            }

    # --- Tool 6: git_modules ---

    def git_modules(
        self,
        action: str = "status",
        module_name: str | None = None,
        include_cores: bool = False,
        commit_message: str | None = None,
    ) -> dict[str, Any]:
        """Git operations across modules.

        Args:
            action: One of "status", "diff", "pull", "push"
            module_name: Specific module, or None for all
            include_cores: Include cores/ (default: False)
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
                    if include_cores or m.module_type.name != "core"
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


# Module-level singleton
_controller: AdhdController | None = None


def get_adhd_controller(root_path: Path | str | None = None) -> AdhdController:
    """Get or create the AdhdController singleton."""
    global _controller
    if _controller is None:
        _controller = AdhdController(root_path=root_path)
    return _controller
