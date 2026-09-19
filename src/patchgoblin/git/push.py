"""Push management for Stage 5."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.git.branch import BranchManager
from patchgoblin.repository.git import GitError, GitHelper


class PushError(Exception):
    """Raised when push operations fail."""


class PushManager:
    """Manages git push operations with safety constraints."""

    def __init__(self, workspace_path: Path):
        """Initialize with the workspace path."""
        self._workspace_path = Path(workspace_path).resolve()
        self._git = GitHelper(self._workspace_path)
        self._branch_manager = BranchManager(self._workspace_path)

    def commit_and_push(
        self,
        branch_name: str,
        approved_files: list[str],
        commit_message: str,
        remote: str = "origin",
    ) -> str:
        """Commit approved files and push to remote.

        Args:
            task_id: Task ID for verification.
            branch_name: Branch name to push (must be PatchGoblin-owned).
            approved_files: Files approved for modification (Stage 4 scope).
            commit_message: Commit message.
            remote: Remote name (default: "origin").

        Returns:
            The full branch reference that was pushed (e.g., "origin/patchgoblin/pg-xxx").

        Raises:
            PushError: If push fails or violates safety rules.
        """
        # Safety check: ensure branch is PatchGoblin-owned
        if not self._branch_manager.is_patchgoblin_branch(branch_name):
            raise PushError(
                f"Cannot push non-PatchGoblin branch: {branch_name}. "
                f"PatchGoblin only pushes branches it created."
            )

        # Safety check: ensure branch is not protected
        if self._branch_manager.is_protected_branch(branch_name):
            raise PushError(
                f"Cannot push protected branch: {branch_name}. "
                f"PatchGoblin never pushes to main/master/etc."
            )

        # Safety check: ensure we're on the correct branch
        current_branch = self._branch_manager.get_current_branch()
        if current_branch != branch_name:
            raise PushError(
                f"Current branch ({current_branch}) does not match target branch ({branch_name})."
            )

        try:
            # Stage only approved files
            self._git.add_files(approved_files)

            # Commit with message
            self._git.commit(commit_message)

            # Push to remote
            self._git.push(remote, branch_name)

            return f"{remote}/{branch_name}"

        except GitError as exc:
            raise PushError(f"Failed to commit and push: {exc}") from exc

    def get_remote_url(self, remote: str = "origin") -> str:
        """Get the URL for a remote.

        Args:
            remote: Remote name (default: "origin").

        Returns:
            Remote URL.

        Raises:
            PushError: If unable to get remote URL.
        """
        try:
            result = self._git._run(["git", "remote", "get-url", remote])
            return result.stdout.strip()
        except GitError as exc:
            raise PushError(f"Failed to get remote URL for {remote}: {exc}") from exc
