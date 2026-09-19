"""Push service for Stage 5 branch push operations."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.git.branch import BranchError, BranchManager
from patchgoblin.git.push import PushError, PushManager
from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceStatus


class PushServiceError(Exception):
    """Raised when push service operations fail."""


class PushService:
    """Service for pushing branches with safety constraints."""

    def __init__(self, workspace_manager: WorkspaceManager | None = None) -> None:
        """Initialize with optional workspace manager."""
        self._ws_manager = workspace_manager or WorkspaceManager()

    def push_branch(
        self,
        task_id: str,
        commit_message: str,
        remote: str = "origin",
    ) -> tuple[str, str]:
        """Create branch, commit changes, and push to remote.

        Args:
            task_id: Task ID of the workspace.
            commit_message: Commit message for the changes.
            remote: Remote name (default: "origin").

        Returns:
            Tuple of (branch_name, remote_ref) that was pushed.

        Raises:
            PushServiceError: If push fails or violates safety rules.
        """
        # Load workspace metadata
        try:
            meta = self._ws_manager.load(task_id)
        except WorkspaceError as exc:
            raise PushServiceError(f"Failed to load workspace {task_id}: {exc}") from exc

        # Check workspace status
        if meta.status.value not in ("review", "modified"):
            raise PushServiceError(
                f"Workspace {task_id} is in {meta.status.value} status. "
                "Push can only be done from workspaces in 'review' or 'modified' status."
            )

        # Generate branch name from task ID and issue reference
        branch_name = self._generate_branch_name(task_id, meta.issue_reference)

        # Create branch, commit, and push
        workspace_path = Path(meta.local_path)
        branch_manager = BranchManager(workspace_path)
        push_manager = PushManager(workspace_path)

        try:
            # Create the PatchGoblin branch
            created_branch = branch_manager.create_patchgoblin_branch(task_id, branch_name)

            # Commit and push
            remote_ref = push_manager.commit_and_push(
                branch_name=created_branch,
                approved_files=meta.approved_files,
                commit_message=commit_message,
                remote=remote,
            )

            # Update workspace metadata
            meta.branch_name = created_branch
            meta.pushed = True
            meta.status = WorkspaceStatus.PUSHED
            self._ws_manager.save(meta)

            return created_branch, remote_ref

        except (BranchError, PushError) as exc:
            raise PushServiceError(f"Failed to push branch: {exc}") from exc

    def _generate_branch_name(self, task_id: str, issue_reference: str) -> str:
        """Generate a descriptive slug for the branch name from issue reference."""
        # Extract issue number and create a simple slug
        if "#" in issue_reference:
            parts = issue_reference.split("#")
            if len(parts) == 2:
                return f"fix-issue-{parts[1]}"
        return "fix"
