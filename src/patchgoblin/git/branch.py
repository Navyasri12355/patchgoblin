"""Branch management for Stage 5."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.repository.git import GitError, GitHelper


class BranchError(Exception):
    """Raised when branch operations fail."""


class BranchManager:
    """Manages git branch operations with safety constraints."""

    # Protected branch names that PatchGoblin must never modify
    PROTECTED_BRANCHES = {"main", "master", "develop", "staging", "production"}

    def __init__(self, workspace_path: Path):
        """Initialize with the workspace path."""
        self._workspace_path = Path(workspace_path).resolve()
        self._git = GitHelper(self._workspace_path)

    def create_patchgoblin_branch(self, task_id: str, slug: str) -> str:
        """Create a PatchGoblin-owned branch with safe naming.

        Args:
            task_id: Task ID (e.g., "pg-7f3a21").
            slug: Short descriptive slug for the branch.

        Returns:
            The created branch name.

        Raises:
            BranchError: If branch creation fails or violates safety rules.
        """
        # Generate branch name using PatchGoblin convention
        branch_name = self._generate_branch_name(task_id, slug)

        # Safety check: ensure we're not creating a protected branch
        if branch_name.lower() in self.PROTECTED_BRANCHES:
            raise BranchError(
                f"Cannot create protected branch: {branch_name}. "
                f"PatchGoblin only creates branches under 'patchgoblin/' prefix."
            )

        # Ensure branch name starts with patchgoblin/ prefix
        if not branch_name.startswith("patchgoblin/"):
            raise BranchError(f"Branch name must start with 'patchgoblin/': {branch_name}")

        try:
            # Create and checkout the branch
            self._git.checkout_new_branch(branch_name)
            return branch_name
        except GitError as exc:
            raise BranchError(f"Failed to create branch {branch_name}: {exc}") from exc

    def _generate_branch_name(self, task_id: str, slug: str) -> str:
        """Generate a safe branch name from task ID and slug."""
        # Clean the slug: only alphanumeric and hyphens
        clean_slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug).strip("-")
        clean_slug = clean_slug[:50]  # Limit length

        # Use PatchGoblin convention: patchgoblin/<task-id>-<slug>
        return f"patchgoblin/{task_id}-{clean_slug}"

    def get_current_branch(self) -> str:
        """Get the current branch name.

        Returns:
            Current branch name.

        Raises:
            BranchError: If unable to determine current branch.
        """
        try:
            return self._git.current_branch()
        except GitError as exc:
            raise BranchError(f"Failed to get current branch: {exc}") from exc

    def is_patchgoblin_branch(self, branch_name: str) -> bool:
        """Check if a branch is a PatchGoblin-owned branch."""
        return branch_name.startswith("patchgoblin/")

    def is_protected_branch(self, branch_name: str) -> bool:
        """Check if a branch is protected (should never be modified by PatchGoblin)."""
        return branch_name.lower() in self.PROTECTED_BRANCHES
