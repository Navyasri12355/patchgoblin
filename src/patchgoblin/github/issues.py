"""Issue-specific GitHub API helpers."""

from __future__ import annotations

from patchgoblin.github.client import GitHubClient
from patchgoblin.github.models import IssueInfo


def get_issue(client: GitHubClient, owner: str, repo: str, number: int) -> IssueInfo:
    """Fetch a single issue by owner, repo, and issue number."""
    return client.get_issue(owner, repo, number)


def list_issues(
    client: GitHubClient,
    owner: str,
    repo: str,
    state: str = "open",
    labels: str | None = None,
) -> list[IssueInfo]:
    """List issues in a repository."""
    return client.list_repository_issues(owner, repo, state=state, labels=labels)


def search_issues(client: GitHubClient, query: str) -> list[IssueInfo]:
    """Search GitHub issues using the search API."""
    return client.search_issues(query)
