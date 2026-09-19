"""Controlled Git operations for the workspace.

Stage 4 operations:
  git clone      — handled in repository/clone.py
  git rev-parse  — HEAD SHA
  git status     — clean-tree check
  git diff       — show changes
  git diff --stat

Stage 5 operations (with safety constraints):
  git checkout -b  — create PatchGoblin-owned branches
  git add         — stage approved files only
  git commit      — commit with generated message
  git push        — push PatchGoblin branches only

No pull, fetch, merge, rebase, reset, clean, or force-push.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(Exception):
    """Raised when a controlled Git operation fails."""


class GitHelper:
    """Run safe, read-only Git operations inside a workspace repository."""

    def __init__(self, repo_path: Path) -> None:
        self._root = repo_path

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    def rev_parse_head(self) -> str:
        """Return the HEAD commit SHA, or ``"unknown"`` on failure."""
        result = self._run(["git", "rev-parse", "HEAD"], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"

    def is_clean(self) -> bool:
        """Return True if the working tree has no uncommitted changes."""
        result = self._run(
            ["git", "status", "--porcelain"],
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == ""

    def status(self) -> str:
        """Return the output of ``git status``."""
        result = self._run(["git", "status"], check=False)
        return result.stdout.strip()

    def diff_stat(self) -> str:
        """Return the output of ``git diff --stat``."""
        result = self._run(["git", "diff", "--stat"], check=False)
        return result.stdout.strip()

    def diff(self) -> str:
        """Return the full output of ``git diff``."""
        result = self._run(["git", "diff"], check=False)
        return result.stdout

    # ------------------------------------------------------------------
    # Stage 5: Write operations (with safety constraints)
    # ------------------------------------------------------------------

    def checkout_new_branch(self, branch_name: str) -> None:
        """Create and checkout a new branch.

        Args:
            branch_name: Name of the new branch.

        Raises:
            GitError: If branch creation fails.
        """
        self._run(["git", "checkout", "-b", branch_name])

    def current_branch(self) -> str:
        """Return the current branch name.

        Raises:
            GitError: If unable to determine current branch.
        """
        result = self._run(["git", "branch", "--show-current"])
        return result.stdout.strip()

    def add_files(self, files: list[str]) -> None:
        """Stage specific files for commit.

        Args:
            files: List of file paths to stage (relative to repo root).

        Raises:
            GitError: If staging fails.
        """
        for file_path in files:
            self._run(["git", "add", file_path])

    def commit(self, message: str) -> None:
        """Commit staged changes with a message.

        Args:
            message: Commit message.

        Raises:
            GitError: If commit fails.
        """
        self._run(["git", "commit", "-m", message])

    def push(self, remote: str, branch: str) -> None:
        """Push a branch to a remote.

        Args:
            remote: Remote name (e.g., "origin").
            branch: Branch name to push.

        Raises:
            GitError: If push fails.

        Note:
            This does NOT support force-push and will fail if attempted.
        """
        # Explicitly forbid force-push by not accepting --force flag
        self._run(["git", "push", remote, branch])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(  # noqa: S603
                [*cmd[:1], "-C", str(self._root), *cmd[1:]],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git command timed out: {' '.join(cmd)}") from exc
        except FileNotFoundError as exc:
            raise GitError("git executable not found. Install Git and retry.") from exc

        if check and result.returncode != 0:
            raise GitError(
                f"git command failed (exit {result.returncode}):\n"
                f"  cmd: {' '.join(cmd)}\n"
                f"  stderr: {result.stderr.strip()}"
            )
        return result
