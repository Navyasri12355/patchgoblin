"""Workspace models for Stage 4 isolated workspaces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class WorkspaceStatus(StrEnum):
    """Lifecycle state of a PatchGoblin workspace."""

    CREATED = "created"
    READY = "ready"
    WORKING = "working"
    MODIFIED = "modified"
    REVIEW = "review"
    DISCARDED = "discarded"
    FAILED = "failed"


class WorkspaceMetadata(BaseModel):
    """Persistent metadata for a PatchGoblin workspace."""

    task_id: str = Field(description="Unique task identifier, e.g. pg-7f3a21.")
    issue_reference: str = Field(description="Issue reference, e.g. owner/repo#123.")
    repository: str = Field(description="Repository full name, e.g. owner/repo.")
    source_url: str = Field(description="Git clone URL used to create the workspace.")
    local_path: str = Field(description="Absolute path to the workspace directory.")
    commit_sha: str = Field(default="unknown", description="HEAD commit SHA after cloning.")
    status: WorkspaceStatus = Field(
        default=WorkspaceStatus.CREATED, description="Current lifecycle status."
    )
    approved_files: list[str] = Field(
        default_factory=list,
        description="Files the human approved for modification.",
    )
    modified_files: list[str] = Field(
        default_factory=list,
        description="Files actually modified by the coding agent.",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def path(self) -> Path:
        """Return the workspace path as a :class:`~pathlib.Path`."""
        return Path(self.local_path)

    def model_post_init(self, __context: object) -> None:
        """Ensure ``updated_at`` is always a ``datetime``."""
        # Pydantic v2 calls this after __init__; nothing extra needed here.

    def touch(self) -> None:
        """Update ``updated_at`` to now (mutates in-place)."""
        self.updated_at = datetime.utcnow()
