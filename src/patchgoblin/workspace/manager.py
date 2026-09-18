"""Workspace manager — creates, tracks, and cleans up PatchGoblin workspaces.

Each workspace is a temporary directory that contains a cloned repository.
Metadata is persisted as a JSON file inside the workspace directory so the
user can resume or inspect it later.
"""

from __future__ import annotations

import json
import secrets
import shutil
import tempfile
from pathlib import Path

from patchgoblin.workspace.models import WorkspaceMetadata, WorkspaceStatus


class WorkspaceError(Exception):
    """Raised for workspace management failures."""


class WorkspaceManager:
    """Creates and manages PatchGoblin workspaces.

    Workspaces are stored under a dedicated base directory (defaults to a
    ``patchgoblin`` sub-directory inside the OS temporary folder).
    """

    _METADATA_FILENAME = "patchgoblin-workspace.json"

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(tempfile.gettempdir()) / "patchgoblin"
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def base_dir(self) -> Path:
        """Root directory that contains all PatchGoblin workspaces."""
        return self._base_dir

    def create(
        self,
        issue_reference: str,
        repository: str,
        source_url: str,
    ) -> WorkspaceMetadata:
        """Create a new workspace and return its metadata.

        The workspace directory is created immediately but no clone is
        performed here.  Cloning is handled by the work service so that the
        workspace can be cleaned up properly if cloning fails.
        """
        task_id = self._new_task_id()
        workspace_dir = self._base_dir / task_id / "repository"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        meta = WorkspaceMetadata(
            task_id=task_id,
            issue_reference=issue_reference,
            repository=repository,
            source_url=source_url,
            local_path=str(workspace_dir),
            status=WorkspaceStatus.CREATED,
        )
        self._save(meta)
        return meta

    def load(self, task_id: str) -> WorkspaceMetadata:
        """Load workspace metadata for *task_id*.

        Raises
        ------
        WorkspaceError
            If the workspace does not exist or its metadata is missing.
        """
        meta_path = self._meta_path_for(task_id)
        if not meta_path.exists():
            raise WorkspaceError(f"No workspace found for task {task_id!r}.")
        return self._read(meta_path)

    def save(self, meta: WorkspaceMetadata) -> None:
        """Persist updated metadata to disk."""
        meta.touch()
        self._save(meta)

    def list_all(self) -> list[WorkspaceMetadata]:
        """Return metadata for all tracked workspaces, newest first."""
        results: list[WorkspaceMetadata] = []
        for meta_path in self._base_dir.rglob(self._METADATA_FILENAME):
            try:
                results.append(self._read(meta_path))
            except Exception:
                continue
        results.sort(key=lambda m: m.created_at, reverse=True)
        return results

    def discard(self, task_id: str, *, force: bool = False) -> None:
        """Delete the workspace for *task_id*.

        The caller is responsible for confirming with the user before
        calling this method (unless *force* is True in tests).

        Raises
        ------
        WorkspaceError
            If the workspace is not tracked by PatchGoblin.
        """
        meta = self.load(task_id)
        task_dir = self._base_dir / task_id
        if not task_dir.exists():
            raise WorkspaceError(f"Workspace directory for {task_id!r} does not exist.")

        # Safety: only delete directories that are under our base_dir
        try:
            task_dir.resolve().relative_to(self._base_dir.resolve())
        except ValueError as exc:
            raise WorkspaceError(
                f"Workspace directory {task_dir} is not inside the PatchGoblin "
                "base directory. Refusing to delete."
            ) from exc

        shutil.rmtree(task_dir)
        meta.status = WorkspaceStatus.DISCARDED
        # The directory is gone, so we can't save metadata anymore — that's fine.

    def update_status(self, meta: WorkspaceMetadata, status: WorkspaceStatus) -> None:
        """Convenience: update *status* and persist."""
        meta.status = status
        self.save(meta)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _new_task_id() -> str:
        """Generate a short, unique task identifier like ``pg-7f3a21``."""
        return f"pg-{secrets.token_hex(3)}"

    def _meta_path_for(self, task_id: str) -> Path:
        return self._base_dir / task_id / self._METADATA_FILENAME

    def _save(self, meta: WorkspaceMetadata) -> None:
        meta_path = self._meta_path_for(meta.task_id)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    @staticmethod
    def _read(meta_path: Path) -> WorkspaceMetadata:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return WorkspaceMetadata.model_validate(data)
        except Exception as exc:
            msg = f"Failed to read workspace metadata at {meta_path}: {exc}"
            raise WorkspaceError(msg) from exc
