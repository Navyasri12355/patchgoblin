"""Tests for workspace manager (creation, metadata, cleanup, state transitions)."""

from __future__ import annotations

from pathlib import Path

import pytest

from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceStatus


@pytest.fixture()
def tmp_ws_manager(tmp_path: Path) -> WorkspaceManager:
    """A WorkspaceManager that writes into a pytest tmp directory."""
    return WorkspaceManager(base_dir=tmp_path / "patchgoblin")


class TestWorkspaceCreation:
    def test_creates_workspace_directory(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#1",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        assert Path(meta.local_path).parent.exists()

    def test_task_id_format(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#1",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        assert meta.task_id.startswith("pg-")
        assert len(meta.task_id) == 9  # "pg-" + 6 hex chars

    def test_initial_status_is_created(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#1",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        assert meta.status == WorkspaceStatus.CREATED

    def test_metadata_roundtrip(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#42",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        loaded = tmp_ws_manager.load(meta.task_id)
        assert loaded.task_id == meta.task_id
        assert loaded.issue_reference == "owner/repo#42"
        assert loaded.repository == "owner/repo"
        assert loaded.status == WorkspaceStatus.CREATED

    def test_unique_task_ids(self, tmp_ws_manager: WorkspaceManager) -> None:
        ids = {
            tmp_ws_manager.create(
                issue_reference="owner/repo#1",
                repository="owner/repo",
                source_url="https://github.com/owner/repo.git",
            ).task_id
            for _ in range(10)
        }
        assert len(ids) == 10


class TestWorkspaceLoad:
    def test_load_existing(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#5",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        loaded = tmp_ws_manager.load(meta.task_id)
        assert loaded.task_id == meta.task_id

    def test_load_nonexistent_raises(self, tmp_ws_manager: WorkspaceManager) -> None:
        with pytest.raises(WorkspaceError, match="No workspace found"):
            tmp_ws_manager.load("pg-000000")


class TestWorkspaceStatusTransitions:
    def test_update_status(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#1",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        tmp_ws_manager.update_status(meta, WorkspaceStatus.READY)
        loaded = tmp_ws_manager.load(meta.task_id)
        assert loaded.status == WorkspaceStatus.READY

    def test_full_lifecycle(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#1",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        for status in (
            WorkspaceStatus.READY,
            WorkspaceStatus.WORKING,
            WorkspaceStatus.MODIFIED,
            WorkspaceStatus.REVIEW,
        ):
            tmp_ws_manager.update_status(meta, status)
            assert tmp_ws_manager.load(meta.task_id).status == status


class TestWorkspaceDiscard:
    def test_discard_removes_directory(self, tmp_ws_manager: WorkspaceManager) -> None:
        meta = tmp_ws_manager.create(
            issue_reference="owner/repo#1",
            repository="owner/repo",
            source_url="https://github.com/owner/repo.git",
        )
        task_dir = tmp_ws_manager.base_dir / meta.task_id
        assert task_dir.exists()
        tmp_ws_manager.discard(meta.task_id, force=True)
        assert not task_dir.exists()

    def test_discard_nonexistent_raises(self, tmp_ws_manager: WorkspaceManager) -> None:
        with pytest.raises(WorkspaceError):
            tmp_ws_manager.discard("pg-000000")


class TestWorkspaceList:
    def test_list_returns_all(self, tmp_ws_manager: WorkspaceManager) -> None:
        for i in range(3):
            tmp_ws_manager.create(
                issue_reference=f"owner/repo#{i}",
                repository="owner/repo",
                source_url="https://github.com/owner/repo.git",
            )
        assert len(tmp_ws_manager.list_all()) == 3

    def test_list_empty(self, tmp_ws_manager: WorkspaceManager) -> None:
        assert tmp_ws_manager.list_all() == []
