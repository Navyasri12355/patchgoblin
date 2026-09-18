"""Clones a remote Git repository into a temporary directory.

Safety guarantees
-----------------
- Only `git clone --no-local --depth=1` is used — no code is executed.
- The temporary directory is unique per run.
- The caller is responsible for cleanup (use as a context manager).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class CloneError(Exception):
    """Raised when the git clone operation fails."""


class RepositoryClone:
    """Context manager that clones *clone_url* into a unique temp directory.

    Usage::

        with RepositoryClone("https://github.com/owner/repo.git") as clone:
            tree = build_tree(clone.path)
            ...
        # temporary directory is deleted automatically
    """

    def __init__(self, clone_url: str) -> None:
        self._clone_url = clone_url
        self._tmpdir: tempfile.TemporaryDirectory | None = None  # type: ignore[type-arg]
        self._path: Path | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        """Local path to the cloned repository root."""
        if self._path is None:
            raise RuntimeError("RepositoryClone has not been entered yet.")
        return self._path

    def clone(self) -> Path:
        """Perform the clone and return the local path."""
        self._tmpdir = tempfile.TemporaryDirectory(prefix="patchgoblin-")
        dest = Path(self._tmpdir.name) / "repo"
        dest.mkdir()
        self._run_clone(self._clone_url, dest)
        self._path = dest
        return dest

    def cleanup(self) -> None:
        """Delete the temporary directory."""
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None
            self._path = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> RepositoryClone:
        self.clone()
        return self

    def __exit__(self, *_) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _run_clone(url: str, dest: Path) -> None:
        """Run ``git clone`` into *dest*.

        Uses ``--depth=1`` (shallow) for speed and ``--no-local`` to prevent
        hardlink tricks when the URL happens to be a local path.
        Only the default branch is fetched.
        """
        cmd = [
            "git",
            "clone",
            "--depth=1",
            "--no-local",
            "--single-branch",
            "--",
            url,
            str(dest),
        ]
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise CloneError("git clone timed out after 120 seconds.") from exc
        except FileNotFoundError as exc:
            raise CloneError("git executable not found. Install Git and retry.") from exc

        if result.returncode != 0:
            raise CloneError(
                f"git clone failed (exit {result.returncode}):\n{result.stderr.strip()}"
            )
