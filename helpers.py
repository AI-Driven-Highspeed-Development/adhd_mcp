"""
ADHD MCP Helpers - Import scanning and git utilities.

Provides utilities for categorizing Python imports and parsing git status output.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

# ADHD framework module prefixes
ADHD_PREFIXES = ("cores.", "managers.", "utils.", "plugins.", "mcps.", "project.")

# Python stdlib modules - use stdlib_list for Python < 3.10, sys.stdlib_module_names for 3.10+
_STDLIB_MODULES: set[str] | None = None


def get_stdlib_modules() -> set[str]:
    """Get the set of Python standard library module names."""
    global _STDLIB_MODULES
    if _STDLIB_MODULES is not None:
        return _STDLIB_MODULES

    if sys.version_info >= (3, 10):
        _STDLIB_MODULES = set(sys.stdlib_module_names)
    else:
        try:
            from stdlib_list import stdlib_list
            _STDLIB_MODULES = set(stdlib_list("3.10"))
        except ImportError:
            # Fallback: common stdlib modules if stdlib_list not available
            _STDLIB_MODULES = {
                "abc", "argparse", "ast", "asyncio", "base64", "collections",
                "contextlib", "copy", "dataclasses", "datetime", "enum", "functools",
                "glob", "hashlib", "importlib", "inspect", "io", "itertools", "json",
                "logging", "math", "os", "pathlib", "pickle", "platform", "pprint",
                "queue", "random", "re", "shutil", "signal", "socket", "sqlite3",
                "string", "subprocess", "sys", "tempfile", "threading", "time",
                "traceback", "typing", "unittest", "urllib", "uuid", "warnings",
                "weakref", "xml", "zipfile",
            }
    return _STDLIB_MODULES


def categorize_import(module_name: str) -> str:
    """Categorize a Python import into stdlib, adhd, local, or third_party.

    Args:
        module_name: The top-level module name (e.g., 'yaml', 'cores.module_name')

    Returns:
        One of: "stdlib", "adhd", "local", "third_party"
    """
    if not module_name:
        return "third_party"

    # Handle relative imports
    if module_name.startswith("."):
        return "local"

    # Get the top-level module name (before first dot)
    top_level = module_name.split(".")[0]

    # Check if it's ADHD framework module
    if any(module_name.startswith(prefix) for prefix in ADHD_PREFIXES):
        return "adhd"

    # Check if top-level module is in stdlib
    if top_level in get_stdlib_modules():
        return "stdlib"

    return "third_party"


def scan_python_imports(file_path: Path) -> dict[str, list[str]]:
    """Scan a Python file and categorize all its imports.

    Args:
        file_path: Path to the Python file

    Returns:
        Dict with keys: stdlib, adhd, third_party, local - each containing list of module names
    """
    imports: dict[str, set[str]] = {
        "stdlib": set(),
        "adhd": set(),
        "third_party": set(),
        "local": set(),
    }

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {k: list(v) for k, v in imports.items()}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                category = categorize_import(module_name)
                imports[category].add(module_name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            # Handle relative imports
            if node.level > 0:
                # Relative import
                prefix = "." * node.level
                full_name = f"{prefix}{module_name}" if module_name else prefix
                imports["local"].add(full_name)
            else:
                category = categorize_import(module_name)
                imports[category].add(module_name)

    return {k: sorted(v) for k, v in imports.items()}


def scan_module_imports(module_path: Path) -> dict[str, list[str]]:
    """Scan all Python files in a module directory and aggregate imports.

    Args:
        module_path: Path to the module directory

    Returns:
        Dict with keys: stdlib, adhd, third_party, local - each containing sorted list of unique module names
    """
    all_imports: dict[str, set[str]] = {
        "stdlib": set(),
        "adhd": set(),
        "third_party": set(),
        "local": set(),
    }

    if not module_path.is_dir():
        return {k: list(v) for k, v in all_imports.items()}

    for py_file in module_path.rglob("*.py"):
        # Skip __pycache__ and hidden directories
        if "__pycache__" in py_file.parts or any(p.startswith(".") for p in py_file.parts):
            continue
        file_imports = scan_python_imports(py_file)
        for category, modules in file_imports.items():
            all_imports[category].update(modules)

    return {k: sorted(v) for k, v in all_imports.items()}


def parse_requirements_txt(file_path: Path) -> list[str]:
    """Parse a requirements.txt file and return the list of package specifications.

    Args:
        file_path: Path to requirements.txt

    Returns:
        List of package specifications (e.g., ["PyYAML>=6.0", "mcp>=1.2.0"])
    """
    if not file_path.exists():
        return []

    requirements: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Skip options like -e, --index-url, etc.
            if line.startswith("-"):
                continue
            requirements.append(line)
    except OSError:
        pass

    return requirements


# --- Git Helpers ---


def run_git_command(
    args: list[str],
    cwd: Path,
    timeout: int = 30,
) -> subprocess.CompletedProcess[bytes]:
    """Run a git command and return the result.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for the command
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess with stdout and stderr
    """
    cmd = ["git", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def _parse_numstat_line(line: str) -> dict[str, Any] | None:
    """Parse a single line from git diff --numstat output.

    Args:
        line: A line from numstat output (format: insertions\tdeletions\tfilepath)

    Returns:
        Dict with file, insertions, deletions or None if line is invalid
    """
    if not line:
        return None
    parts = line.split("\t")
    if len(parts) < 3:
        return None
    return {
        "file": parts[2],
        "insertions": int(parts[0]) if parts[0] != "-" else 0,
        "deletions": int(parts[1]) if parts[1] != "-" else 0,
    }


def _parse_numstat_output(
    result: subprocess.CompletedProcess[bytes],
) -> list[dict[str, Any]]:
    """Parse git diff --numstat output into a list of change dicts.

    Args:
        result: CompletedProcess from git diff --numstat command

    Returns:
        List of dicts with file, insertions, deletions
    """
    if result.returncode != 0:
        return []
    changes = []
    for line in result.stdout.decode("utf-8").strip().splitlines():
        parsed = _parse_numstat_line(line)
        if parsed:
            changes.append(parsed)
    return changes


def _get_ahead_behind_counts(repo_path: Path) -> tuple[int, int]:
    """Get the ahead/behind commit counts relative to upstream.

    Args:
        repo_path: Path to the git repository

    Returns:
        Tuple of (ahead_count, behind_count)
    """
    ahead = 0
    behind = 0
    ahead_result = run_git_command(["rev-list", "--count", "@{u}..HEAD"], cwd=repo_path)
    if ahead_result.returncode == 0:
        try:
            ahead = int(ahead_result.stdout.decode().strip())
        except ValueError:
            pass
    behind_result = run_git_command(["rev-list", "--count", "HEAD..@{u}"], cwd=repo_path)
    if behind_result.returncode == 0:
        try:
            behind = int(behind_result.stdout.decode().strip())
        except ValueError:
            pass
    return ahead, behind


def _determine_sync_status(ahead: int, behind: int) -> dict[str, Any]:
    """Determine repository sync status from ahead/behind counts.

    Args:
        ahead: Number of commits ahead of upstream
        behind: Number of commits behind upstream

    Returns:
        Dict with status and optional commits/ahead/behind counts
    """
    if ahead > 0 and behind > 0:
        return {"status": "diverged", "ahead": ahead, "behind": behind}
    elif ahead > 0:
        return {"status": "ahead", "commits": ahead}
    elif behind > 0:
        return {"status": "behind", "commits": behind}
    return {"status": "clean"}


def _count_porcelain_changes(status_output: str) -> dict[str, int]:
    """Count changes from git status --porcelain output.

    Args:
        status_output: Output from git status --porcelain

    Returns:
        Dict with changed, added, deleted counts
    """
    changed = added = deleted = 0
    for line in status_output.splitlines():
        if len(line) >= 2:
            status_code = line[:2]
            if "?" in status_code:
                added += 1
            elif "D" in status_code:
                deleted += 1
            else:
                changed += 1
    return {"changed": changed, "added": added, "deleted": deleted}


def get_git_status(repo_path: Path) -> dict[str, Any]:
    """Get git status information for a repository.

    Args:
        repo_path: Path to the git repository

    Returns:
        Dict with status, branch, and change counts
    """
    result: dict[str, Any] = {"status": "unknown", "branch": "unknown"}

    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        result["status"] = "not_a_repo"
        return result

    # Get current branch
    branch_result = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    if branch_result.returncode == 0:
        result["branch"] = branch_result.stdout.decode("utf-8").strip()

    # Get status (porcelain format)
    status_result = run_git_command(["status", "--porcelain"], cwd=repo_path)
    if status_result.returncode != 0:
        return result

    status_output = status_result.stdout.decode("utf-8").strip()
    if not status_output:
        # Clean working tree - check ahead/behind
        ahead, behind = _get_ahead_behind_counts(repo_path)
        result.update(_determine_sync_status(ahead, behind))
    else:
        # Dirty working tree - count changes
        result["status"] = "dirty"
        result.update(_count_porcelain_changes(status_output))

    return result


def get_git_remote_url(repo_path: Path) -> str | None:
    """Get the remote origin URL for a repository.

    Args:
        repo_path: Path to the git repository

    Returns:
        Remote URL or None if not available
    """
    result = run_git_command(["remote", "get-url", "origin"], cwd=repo_path)
    if result.returncode == 0:
        return result.stdout.decode("utf-8").strip()
    return None


def _merge_numstat_changes(
    changes: list[dict[str, Any]],
    new_changes: list[dict[str, Any]],
) -> None:
    """Merge new numstat changes into existing changes list (in-place).

    Args:
        changes: Existing list of changes to update
        new_changes: New changes to merge in
    """
    for change in new_changes:
        existing = next((c for c in changes if c["file"] == change["file"]), None)
        if existing:
            existing["insertions"] += change["insertions"]
            existing["deletions"] += change.get("deletions", 0)
        else:
            changes.append({"file": change["file"], "type": "modified", **change})


def _get_untracked_files(repo_path: Path) -> list[dict[str, Any]]:
    """Get list of untracked files with line counts.

    Args:
        repo_path: Path to the git repository

    Returns:
        List of dicts with file, type='added', insertions (line count)
    """
    untracked: list[dict[str, Any]] = []
    status_result = run_git_command(["status", "--porcelain"], cwd=repo_path)
    if status_result.returncode != 0:
        return untracked

    for line in status_result.stdout.decode("utf-8").strip().splitlines():
        if not line.startswith("??"):
            continue
        file_path = line[3:].strip()
        full_path = repo_path / file_path
        line_count = 0
        try:
            if full_path.is_file():
                line_count = len(full_path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass
        untracked.append({"file": file_path, "type": "added", "insertions": line_count})
    return untracked


def get_git_diff_stat(repo_path: Path) -> list[dict[str, Any]]:
    """Get detailed diff statistics for uncommitted changes.

    Args:
        repo_path: Path to the git repository

    Returns:
        List of dicts with file, type, insertions, deletions
    """
    # Get unstaged changes
    diff_result = run_git_command(["diff", "--numstat"], cwd=repo_path)
    changes = [{"type": "modified", **c} for c in _parse_numstat_output(diff_result)]

    # Merge staged changes
    staged_result = run_git_command(["diff", "--cached", "--numstat"], cwd=repo_path)
    _merge_numstat_changes(changes, _parse_numstat_output(staged_result))

    # Add untracked files
    changes.extend(_get_untracked_files(repo_path))

    return changes


def git_pull(repo_path: Path) -> dict[str, Any]:
    """Pull latest changes for a repository.

    Args:
        repo_path: Path to the git repository

    Returns:
        Dict with success status and message
    """
    result = run_git_command(["pull"], cwd=repo_path)
    if result.returncode == 0:
        output = result.stdout.decode("utf-8").strip()
        return {"success": True, "message": output}
    else:
        error = result.stderr.decode("utf-8").strip()
        return {"success": False, "error": error}


def git_commit_and_push(
    repo_path: Path,
    message: str,
    branch: str = "main",
) -> dict[str, Any]:
    """Stage all changes, commit, and push to remote.

    Args:
        repo_path: Path to the git repository
        message: Commit message
        branch: Branch to push to

    Returns:
        Dict with success status, commit hash, and any errors
    """
    # Stage all changes
    add_result = run_git_command(["add", "--all"], cwd=repo_path)
    if add_result.returncode != 0:
        return {"success": False, "error": f"Failed to stage: {add_result.stderr.decode().strip()}"}

    # Commit
    commit_result = run_git_command(["commit", "-m", message], cwd=repo_path)
    if commit_result.returncode != 0:
        output = (commit_result.stderr.decode() + commit_result.stdout.decode()).lower()
        if "nothing to commit" in output:
            return {"success": False, "error": "nothing_to_commit"}
        return {"success": False, "error": f"Failed to commit: {output.strip()}"}

    # Get commit hash
    hash_result = run_git_command(["rev-parse", "--short", "HEAD"], cwd=repo_path)
    commit_hash = hash_result.stdout.decode().strip() if hash_result.returncode == 0 else "unknown"

    # Push
    push_result = run_git_command(["push", "-u", "origin", branch], cwd=repo_path)
    if push_result.returncode != 0:
        return {"success": False, "error": f"Failed to push: {push_result.stderr.decode().strip()}", "commit": commit_hash}

    return {"success": True, "commit": commit_hash, "message": message}
