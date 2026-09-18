"""Issue discovery service — Stage 1 placeholder."""

from __future__ import annotations

from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import IssueInfo


def discover_issues(
    client: GitHubClient,
    query: str,
) -> list[IssueInfo]:
    """
    Search GitHub for issues matching the query.

    Stage 1: thin wrapper around the GitHub search API.
    Stage 2 will add filtering, difficulty estimation, and
    contributor-fit matching.
    """
    return client.search_issues(query)
