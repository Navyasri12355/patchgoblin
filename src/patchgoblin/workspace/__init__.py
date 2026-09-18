"""PatchGoblin workspace package — isolated disposable workspaces."""

from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceMetadata, WorkspaceStatus
from patchgoblin.workspace.safety import (
    ALLOWED_WRITE_EXTENSIONS,
    MAX_READ_BYTES,
    MAX_WRITE_BYTES,
    PathTraversalError,
    is_allowed_extension,
    validate_workspace_path,
)

__all__ = [
    "WorkspaceError",
    "WorkspaceManager",
    "WorkspaceMetadata",
    "WorkspaceStatus",
    "PathTraversalError",
    "validate_workspace_path",
    "is_allowed_extension",
    "ALLOWED_WRITE_EXTENSIONS",
    "MAX_READ_BYTES",
    "MAX_WRITE_BYTES",
]
