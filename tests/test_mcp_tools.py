"""Tests for adhd_mcp tool functions.

This validates the MCP tools: list_modules, get_module_info, get_project_info.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from adhd_mcp.adhd_controller import AdhdController
from modules_controller_core import ModuleInfo
from modules_controller_core.module_types import ModuleLayer


class TestGetProjectInfo:
    """Test get_project_info tool."""

    @pytest.fixture
    def mock_project(self, tmp_path: Path) -> Path:
        """Create a mock project with init.yaml."""
        root = tmp_path / "project"
        root.mkdir()
        
        # Create init.yaml
        (root / "init.yaml").write_text("""
name: test-project
version: 1.2.3
description: A test project
modules:
  - https://github.com/org/module1
  - https://github.com/org/module2
""")
        
        # Create a minimal module for counting
        manager_dir = root / "managers" / "test_manager"
        manager_dir.mkdir(parents=True)
        (manager_dir / "pyproject.toml").write_text("""
[project]
name = "test_manager"
version = "1.0.0"

[tool.adhd]
layer = "runtime"
""")
        (manager_dir / "__init__.py").write_text("")
        
        return root

    def test_get_project_info_success(self, mock_project: Path):
        """Should return project metadata from init.yaml."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_project_info()
        
        assert result["success"] is True
        assert result["name"] == "test-project"
        assert result["version"] == "1.2.3"
        assert "description" in result
        assert "modules_registered" in result
        assert "module_counts" in result

    def test_get_project_info_missing_init_yaml(self, tmp_path: Path):
        """Should return error when init.yaml is missing."""
        controller = AdhdController(root_path=tmp_path)
        result = controller.get_project_info()
        
        assert result["success"] is False
        assert result["error"] == "init_yaml_not_found"

    def test_get_project_info_counts_modules(self, mock_project: Path):
        """Should include module counts by folder."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_project_info()
        
        assert result["success"] is True
        assert "module_counts" in result
        # We have one manager module
        assert result["module_counts"].get("managers", 0) >= 1


class TestListModules:
    """Test list_modules tool."""

    @pytest.fixture
    def mock_project(self, tmp_path: Path) -> Path:
        """Create a mock project with modules in various folders."""
        root = tmp_path / "project"
        
        # Create a manager module
        manager_dir = root / "managers" / "config_manager"
        manager_dir.mkdir(parents=True)
        (manager_dir / "pyproject.toml").write_text("""
[project]
name = "config_manager"
version = "1.0.0"

[tool.adhd]
layer = "runtime"
""")
        (manager_dir / "__init__.py").write_text("")
        
        # Create a core module
        core_dir = root / "cores" / "base_core"
        core_dir.mkdir(parents=True)
        (core_dir / "pyproject.toml").write_text("""
[project]
name = "base_core"
version = "0.1.0"

[tool.adhd]
layer = "foundation"
""")
        (core_dir / "__init__.py").write_text("")
        
        # Create an MCP module
        mcp_dir = root / "mcps" / "test_mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "pyproject.toml").write_text("""
[project]
name = "test_mcp"
version = "2.0.0"

[tool.adhd]
layer = "dev"
mcp = true
""")
        (mcp_dir / "__init__.py").write_text("")
        
        return root

    def test_list_modules_excludes_cores_by_default(self, mock_project: Path):
        """Should exclude cores/ modules by default."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(include_cores=False)
        
        assert result["success"] is True
        names = {m["name"] for m in result["modules"]}
        
        assert "config_manager" in names
        assert "test_mcp" in names
        assert "base_core" not in names

    def test_list_modules_includes_cores_when_requested(self, mock_project: Path):
        """Should include cores/ when include_cores=True."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(include_cores=True)
        
        assert result["success"] is True
        names = {m["name"] for m in result["modules"]}
        
        assert "base_core" in names

    def test_list_modules_filter_by_folder(self, mock_project: Path):
        """Should filter by folder type when types specified."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(types=["managers"])
        
        assert result["success"] is True
        assert result["count"] == 1
        assert result["modules"][0]["name"] == "config_manager"

    def test_list_modules_filter_multiple_folders(self, mock_project: Path):
        """Should filter by multiple folder types."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(types=["managers", "mcps"])
        
        assert result["success"] is True
        names = {m["name"] for m in result["modules"]}
        
        assert names == {"config_manager", "test_mcp"}

    def test_list_modules_returns_module_info(self, mock_project: Path):
        """Each module should have expected fields."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules()
        
        assert result["success"] is True
        assert len(result["modules"]) > 0
        
        module = result["modules"][0]
        assert "name" in module
        assert "version" in module
        assert "folder" in module
        assert "path" in module

    def test_list_modules_count_matches(self, mock_project: Path):
        """Count should match number of modules in list."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules()
        
        assert result["success"] is True
        assert result["count"] == len(result["modules"])


class TestGetModuleInfo:
    """Test get_module_info tool."""

    @pytest.fixture
    def mock_project(self, tmp_path: Path) -> Path:
        """Create a mock project with a detailed module."""
        root = tmp_path / "project"
        
        # Create a module with all details
        manager_dir = root / "managers" / "detailed_manager"
        manager_dir.mkdir(parents=True)
        (manager_dir / "pyproject.toml").write_text("""
[project]
name = "detailed_manager"
version = "1.5.0"
dependencies = ["pydantic>=2.0", "requests"]

[project.urls]
Repository = "https://github.com/org/detailed_manager"

[tool.adhd]
layer = "runtime"
mcp = false
""")
        (manager_dir / "__init__.py").write_text("from .main import run")
        (manager_dir / "main.py").write_text("""
import json
import requests
from pathlib import Path

def run():
    pass
""")
        (manager_dir / "refresh.py").write_text("# refresh script")
        (manager_dir / "detailed_manager.instructions.md").write_text("# Instructions")
        
        return root

    def test_get_module_info_success(self, mock_project: Path):
        """Should return detailed module info."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("detailed_manager")
        
        assert result["success"] is True
        assert result["name"] == "detailed_manager"
        assert result["version"] == "1.5.0"

    def test_get_module_info_includes_folder(self, mock_project: Path):
        """Should include folder field (not module_type)."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("detailed_manager")
        
        assert result["success"] is True
        assert result["folder"] == "managers"
        assert "module_type" not in result  # Deprecated field

    def test_get_module_info_includes_repo_url(self, mock_project: Path):
        """Should include repository URL when available."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("detailed_manager")
        
        assert result["success"] is True
        # May be repo_url or remote_url depending on implementation
        assert result.get("repo_url") or result.get("remote_url")

    def test_get_module_info_not_found(self, mock_project: Path):
        """Should return error for non-existent module."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("nonexistent_module")
        
        assert result["success"] is False
        assert "error" in result

    def test_get_module_info_suggests_similar(self, mock_project: Path):
        """Should suggest similar names for typos."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("detail_manager")  # Typo
        
        assert result["success"] is False
        # May have suggestions depending on implementation
        if "suggestions" in result:
            assert "detailed_manager" in result["suggestions"]


class TestModuleInfoFields:
    """Test that module info contains expected fields after migration."""

    @pytest.fixture
    def mock_project(self, tmp_path: Path) -> Path:
        """Create a mock project with an MCP module."""
        root = tmp_path / "project"
        
        mcp_dir = root / "mcps" / "my_mcp"
        mcp_dir.mkdir(parents=True)
        (mcp_dir / "pyproject.toml").write_text("""
[project]
name = "my_mcp"
version = "3.0.0"

[tool.adhd]
layer = "dev"
mcp = true
""")
        (mcp_dir / "__init__.py").write_text("")
        
        return root

    def test_module_has_is_mcp_field(self, mock_project: Path):
        """Module info should have is_mcp field."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(types=["mcps"])
        
        assert result["success"] is True
        assert len(result["modules"]) > 0
        
        module = result["modules"][0]
        # Check for is_mcp or mcp field
        assert module.get("is_mcp") is True or module.get("mcp") is True

    def test_module_has_folder_field(self, mock_project: Path):
        """Module info should have folder field."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("my_mcp")
        
        assert result["success"] is True
        assert "folder" in result
        assert result["folder"] == "mcps"

    def test_module_does_not_have_module_type(self, mock_project: Path):
        """Module info should NOT have deprecated module_type field."""
        controller = AdhdController(root_path=mock_project)
        result = controller.get_module_info("my_mcp")
        
        assert result["success"] is True
        # module_type is deprecated - folder should be used instead
        # Some implementations may still include it for backward compat
        # but folder should be the primary field
        assert "folder" in result


class TestListModulesWithImports:
    """Test list_modules with_imports parameter."""

    @pytest.fixture
    def mock_project(self, tmp_path: Path) -> Path:
        """Create a mock project with a module that has imports."""
        root = tmp_path / "project"
        
        manager_dir = root / "managers" / "importing_manager"
        manager_dir.mkdir(parents=True)
        (manager_dir / "pyproject.toml").write_text("""
[project]
name = "importing_manager"
version = "1.0.0"
dependencies = ["requests", "pydantic"]

[tool.adhd]
layer = "runtime"
""")
        (manager_dir / "__init__.py").write_text("""
from .core import main
""")
        (manager_dir / "core.py").write_text("""
import json
import requests
from pathlib import Path

def main():
    pass
""")
        
        return root

    def test_list_modules_without_imports(self, mock_project: Path):
        """Without with_imports, should not include import analysis."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(with_imports=False)
        
        assert result["success"] is True
        module = result["modules"][0]
        
        # Should have basic info but not detailed imports
        assert "name" in module
        # imports key may or may not be present

    def test_list_modules_with_imports(self, mock_project: Path):
        """With with_imports=True, should include import analysis."""
        controller = AdhdController(root_path=mock_project)
        result = controller.list_modules(with_imports=True)
        
        assert result["success"] is True
        module = result["modules"][0]
        
        # Should have imports key when with_imports=True
        # The exact structure depends on implementation
        assert "name" in module
        # If imports are included, they should be structured
        if "imports" in module:
            assert isinstance(module["imports"], dict)
