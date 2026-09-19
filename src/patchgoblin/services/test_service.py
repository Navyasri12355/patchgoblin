"""Test service for Stage 5 sandboxed test execution."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.testing.executor import TestExecutionError, TestExecutor
from patchgoblin.testing.models import TestRunResult
from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceStatus


class TestServiceError(Exception):
    """Raised when test service operations fail."""


class TestService:
    """Service for running sandboxed tests on workspaces."""

    def __init__(self, workspace_manager: WorkspaceManager | None = None) -> None:
        """Initialize with optional workspace manager."""
        self._ws_manager = workspace_manager or WorkspaceManager()

    def run_tests(self, task_id: str, skip_install: bool = False) -> TestRunResult:
        """Run tests in a sandboxed environment for a workspace.

        Args:
            task_id: Task ID of the workspace to test.
            skip_install: If True, skip dependency installation.

        Returns:
            TestRunResult with execution details.

        Raises:
            TestServiceError: If test execution fails.
        """
        # Load workspace metadata
        try:
            meta = self._ws_manager.load(task_id)
        except WorkspaceError as exc:
            raise TestServiceError(f"Failed to load workspace {task_id}: {exc}") from exc

        # Check workspace status
        if meta.status.value not in ("review", "modified"):
            raise TestServiceError(
                f"Workspace {task_id} is in {meta.status.value} status. "
                "Tests can only be run on workspaces in 'review' or 'modified' status."
            )

        # Create test executor
        workspace_path = Path(meta.local_path)
        executor = TestExecutor(workspace_path)

        try:
            result = executor.execute(task_id, skip_install=skip_install)
        except TestExecutionError as exc:
            raise TestServiceError(f"Test execution failed: {exc}") from exc

        # Update workspace metadata with test results
        meta.test_run_result = result.model_dump()
        meta.status = WorkspaceStatus.TESTED
        self._ws_manager.save(meta)

        return result
