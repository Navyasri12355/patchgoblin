"""Repository-specific GitHub API helpers."""

from __future__ import annotations

from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import RepositoryInfo


def get_repository(client: GitHubClient, owner: str, repo: str) -> RepositoryInfo:
    """Fetch a repository by owner and name."""
    return client.get_repository(owner, repo)
