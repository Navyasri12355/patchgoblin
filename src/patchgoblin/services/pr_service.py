"""PR service for Stage 5 pull request creation."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.git.branch import BranchError, BranchManager
from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import PullRequestInfo
from patchgoblin.workspace.manager import WorkspaceError, WorkspaceManager
from patchgoblin.workspace.models import WorkspaceStatus


class PRServiceError(Exception):
    """Raised when PR service operations fail."""


class PRService:
    """Service for creating pull requests with safety constraints."""

    def __init__(
        self,
        github_client: GitHubClient,
        workspace_manager: WorkspaceManager | None = None,
    ) -> None:
        """Initialize with GitHub client and optional workspace manager."""
        self._github = github_client
        self._ws_manager = workspace_manager or WorkspaceManager()

    def create_pull_request(
        self,
        task_id: str,
        title: str,
        body: str,
        draft: bool = False,
    ) -> PullRequestInfo:
        """Create a pull request for a workspace.

        Args:
            task_id: Task ID of the workspace.
            title: PR title.
            body: PR body.
            draft: Whether to create as a draft PR.

        Returns:
            PullRequestInfo with the created PR details.

        Raises:
            PRServiceError: If PR creation fails or violates safety rules.
        """
        # Load workspace metadata
        try:
            meta = self._ws_manager.load(task_id)
        except WorkspaceError as exc:
            raise PRServiceError(f"Failed to load workspace {task_id}: {exc}") from exc

        # Parse repository information
        repo_parts = meta.repository.split("/")
        if len(repo_parts) != 2:
            raise PRServiceError(f"Invalid repository format: {meta.repository}")

        owner, repo_name = repo_parts

        # Determine head and base branches
        # We assume the workspace has a PatchGoblin branch checked out
        workspace_path = Path(meta.local_path)
        branch_manager = BranchManager(workspace_path)

        try:
            current_branch = branch_manager.get_current_branch()
        except BranchError as exc:
            raise PRServiceError(f"Failed to get current branch: {exc}") from exc

        # Safety check: ensure we're on a PatchGoblin branch
        if not branch_manager.is_patchgoblin_branch(current_branch):
            raise PRServiceError(
                f"Current branch {current_branch} is not a PatchGoblin-owned branch. "
                "PRs can only be created from PatchGoblin branches."
            )

        # Get the authenticated user to determine the head ref format
        try:
            user = self._github.get_authenticated_user()
            head_ref = f"{user.username}:{current_branch}"
        except Exception as exc:
            raise PRServiceError(f"Failed to get authenticated user: {exc}") from exc

        # Get the default branch for the base
        try:
            repo_info = self._github.get_repository(owner, repo_name)
            base_ref = repo_info.default_branch
        except Exception as exc:
            raise PRServiceError(f"Failed to get repository info: {exc}") from exc

        # Create the PR
        try:
            pr = self._github.create_pull_request(
                owner=owner,
                repo=repo_name,
                title=title,
                head=head_ref,
                base=base_ref,
                body=body,
                draft=draft,
            )

            # Update workspace metadata
            meta.pr_url = pr.url
            meta.pr_number = pr.number
            meta.pr_status = pr.state
            meta.status = WorkspaceStatus.PR_OPENED
            self._ws_manager.save(meta)

            return pr
        except Exception as exc:
            raise PRServiceError(f"Failed to create pull request: {exc}") from exc
