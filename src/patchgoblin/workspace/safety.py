"""Path-traversal and workspace safety utilities.

This is a critical security boundary.  Every file path that originates from
model output **must** pass through ``validate_workspace_path`` before any
filesystem operation.
"""

from __future__ import annotations

from pathlib import Path

# File extensions the coding agent is allowed to write.
ALLOWED_WRITE_EXTENSIONS: frozenset[str] = frozenset(
    {
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
    }
)

# Maximum size of a file the agent may write (bytes).
MAX_WRITE_BYTES: int = 500_000  # 500 KB

# Maximum size of a file that will be read into a prompt (bytes).
MAX_READ_BYTES: int = 100_000  # 100 KB


class PathTraversalError(ValueError):
    """Raised when a path would escape the workspace root."""


def validate_workspace_path(path: str | Path, workspace_root: Path) -> Path:
    """Resolve *path* and verify it stays inside *workspace_root*.

    Parameters
    ----------
    path:
        A relative or absolute path supplied by model output.
    workspace_root:
        The absolute root of the PatchGoblin workspace.

    Returns
    -------
    Path
        The fully resolved, safe absolute path.

    Raises
    ------
    PathTraversalError
        If the resolved path is not inside *workspace_root*.
    """
    workspace_root = workspace_root.resolve()

    # Treat the path as relative to the workspace root even if it looks absolute
    raw = Path(path)
    if raw.is_absolute():
        # Absolute paths from model output must resolve inside the workspace.
        # Strip any leading root/drive so we can re-anchor it.
        try:
            resolved = raw.resolve()
        except (OSError, ValueError) as exc:
            raise PathTraversalError(f"Cannot resolve path {path!r}: {exc}") from exc
    else:
        resolved = (workspace_root / raw).resolve()

    # Check containment — use str comparison to avoid symlink confusion
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise PathTraversalError(
            f"Path {path!r} resolves to {resolved} which is outside the "
            f"workspace root {workspace_root}."
        ) from exc

    return resolved


def is_allowed_extension(path: str | Path) -> bool:
    """Return ``True`` if the file extension is in ``ALLOWED_WRITE_EXTENSIONS``."""
    return Path(path).suffix.lower() in ALLOWED_WRITE_EXTENSIONS
