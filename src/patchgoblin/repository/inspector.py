"""Repository inspector — orchestrates clone, tree, and relevance discovery."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from patchgoblin.repository.relevance import (
    extract_keywords,
    find_relevant_files,
    read_snippet,
)
from patchgoblin.repository.tree import build_tree


@dataclass
class RepositoryEvidence:
    """Evidence collected from static inspection of a local repository."""

    commit_sha: str
    tree: str
    relevant_files: list[str] = field(default_factory=list)
    snippets: list[tuple[str, str]] = field(default_factory=list)
    """List of (relative_path, content) pairs."""


class RepositoryInspector:
    """Inspects a locally checked-out repository without executing any code."""

    def __init__(self, repo_path: Path) -> None:
        self._root = repo_path

    def get_commit_sha(self) -> str:
        """Return the HEAD commit SHA, or ``"unknown"`` on failure."""
        try:
            result = subprocess.run(  # noqa: S603
                ["git", "-C", str(self._root), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    def build_tree(self) -> str:
        """Return a limited file-tree string."""
        return build_tree(self._root)

    def collect_evidence(self, issue_title: str, issue_body: str | None) -> RepositoryEvidence:
        """Collect all static evidence relevant to the issue.

        1. Build file tree.
        2. Extract keywords from issue text.
        3. Score and rank files.
        4. Read snippets for top files.
        """
        text = issue_title
        if issue_body:
            text = f"{issue_title} {issue_body}"

        keywords = extract_keywords(text)
        tree = self.build_tree()
        commit_sha = self.get_commit_sha()

        relevant_paths = find_relevant_files(self._root, keywords)
        snippets: list[tuple[str, str]] = []
        rel_file_strs: list[str] = []

        for path in relevant_paths:
            rel = str(path.relative_to(self._root)).replace("\\", "/")
            rel_file_strs.append(rel)
            content = read_snippet(path)
            if content is not None:
                snippets.append((rel, content))

        return RepositoryEvidence(
            commit_sha=commit_sha,
            tree=tree,
            relevant_files=rel_file_strs,
            snippets=snippets,
        )
