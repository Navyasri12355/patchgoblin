"""Tests for workspace path-safety utilities (path traversal protection)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from patchgoblin.workspace.safety import (
    PathTraversalError,
    is_allowed_extension,
    validate_workspace_path,
)


@pytest.fixture()
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace" / "repo"
    root.mkdir(parents=True)
    return root


class TestValidateWorkspacePath:
    def test_normal_relative_path(self, workspace_root: Path) -> None:
        result = validate_workspace_path("src/config.py", workspace_root)
        assert result == (workspace_root / "src" / "config.py").resolve()

    def test_nested_relative_path(self, workspace_root: Path) -> None:
        result = validate_workspace_path("a/b/c.py", workspace_root)
        assert result.parent == (workspace_root / "a" / "b").resolve()

    def test_simple_filename(self, workspace_root: Path) -> None:
        result = validate_workspace_path("README.md", workspace_root)
        assert result == (workspace_root / "README.md").resolve()

    def test_parent_traversal_rejected(self, workspace_root: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_workspace_path("../outside.py", workspace_root)

    def test_deep_traversal_rejected(self, workspace_root: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_workspace_path("../../secret.txt", workspace_root)

    def test_absolute_path_outside_workspace_rejected(self, workspace_root: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_workspace_path("/etc/passwd", workspace_root)

    def test_absolute_path_inside_workspace_allowed(self, workspace_root: Path) -> None:
        # An absolute path that resolves inside the workspace should be accepted
        abs_inside = str(workspace_root / "src" / "main.py")
        result = validate_workspace_path(abs_inside, workspace_root)
        assert result == Path(abs_inside).resolve()

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
    def test_windows_absolute_path_rejected(self, workspace_root: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_workspace_path(r"C:\Users\secret\file.py", workspace_root)

    def test_path_with_current_dir_dots(self, workspace_root: Path) -> None:
        # "src/./config.py" should normalise to inside workspace
        result = validate_workspace_path("src/./config.py", workspace_root)
        assert result == (workspace_root / "src" / "config.py").resolve()

    def test_path_traversal_after_valid_prefix_rejected(self, workspace_root: Path) -> None:
        with pytest.raises(PathTraversalError):
            validate_workspace_path("src/../../../etc/passwd", workspace_root)

    def test_symlink_escaping_workspace(self, workspace_root: Path, tmp_path: Path) -> None:
        """A symlink whose target is outside the workspace must be rejected."""
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("secret")

        link = workspace_root / "evil_link.py"
        try:
            link.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform/OS-level.")

        # The resolved path of the symlink points outside the workspace
        with pytest.raises(PathTraversalError):
            validate_workspace_path("evil_link.py", workspace_root)


class TestIsAllowedExtension:
    @pytest.mark.parametrize(
        "ext",
        [
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".go",
            ".rs",
            ".rb",
            ".php",
            ".md",
            ".rst",
            ".txt",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
        ],
    )
    def test_allowed_extensions(self, ext: str) -> None:
        assert is_allowed_extension(f"file{ext}") is True

    @pytest.mark.parametrize(
        "ext",
        [
            ".png",
            ".jpg",
            ".exe",
            ".dll",
            ".so",
            ".zip",
            ".tar",
            ".pyc",
            ".db",
            ".sqlite",
            ".mp4",
            ".whl",
        ],
    )
    def test_rejected_extensions(self, ext: str) -> None:
        assert is_allowed_extension(f"file{ext}") is False

    def test_no_extension_rejected(self) -> None:
        assert is_allowed_extension("Makefile") is False

    def test_case_insensitive(self) -> None:
        assert is_allowed_extension("FILE.PY") is True
        assert is_allowed_extension("FILE.PNG") is False
