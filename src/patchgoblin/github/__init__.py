"""GitHub package for PatchGoblin."""

from patchgoblin.github.client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo

__all__ = [
    "GitHubClient",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
    "GitHubAPIError",
    "RepositoryInfo",
    "IssueInfo",
    "ContributorProfile",
]
