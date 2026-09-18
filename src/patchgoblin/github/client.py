"""GitHub API client."""

from __future__ import annotations

import httpx

from patchgoblin.config import Config
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo


class GitHubAuthError(Exception):
    """Raised when authentication fails or the token is missing."""


class GitHubNotFoundError(Exception):
    """Raised when a requested resource does not exist."""


class GitHubRateLimitError(Exception):
    """Raised when the GitHub API rate limit is exceeded."""


class GitHubAPIError(Exception):
    """Raised for unexpected GitHub API errors."""


class GitHubClient:
    """Typed client for the GitHub REST API."""

    def __init__(self, token: str, base_url: str | None = None) -> None:
        self._base_url = (base_url or Config.GITHUB_API_URL).rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=15.0,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.NetworkError as exc:
            raise GitHubAPIError(f"Network error reaching GitHub: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise GitHubAPIError("Request to GitHub timed out.") from exc

        if response.status_code == 401:
            raise GitHubAuthError("GitHub token is invalid or has been revoked.")
        if response.status_code == 403:
            if "rate limit" in response.text.lower():
                raise GitHubRateLimitError("GitHub API rate limit exceeded.")
            raise GitHubAuthError("GitHub token lacks required permissions.")
        if response.status_code == 404:
            raise GitHubNotFoundError("The requested resource was not found on GitHub.")
        if not response.is_success:
            raise GitHubAPIError(f"GitHub API returned status {response.status_code}.")

        try:
            return response.json()
        except Exception as exc:
            raise GitHubAPIError("GitHub returned an unexpected response format.") from exc

    def get_authenticated_user(self) -> ContributorProfile:
        """Return the authenticated user's profile."""
        data = self._request("GET", "/user")
        return ContributorProfile.from_api(data)

    def get_repository(self, owner: str, repo: str) -> RepositoryInfo:
        """Return information about a single repository."""
        data = self._request("GET", f"/repos/{owner}/{repo}")
        return RepositoryInfo.from_api(data)

    def get_issue(self, owner: str, repo: str, issue_number: int) -> IssueInfo:
        """Return a single issue from a repository."""
        data = self._request("GET", f"/repos/{owner}/{repo}/issues/{issue_number}")
        return IssueInfo.from_api(data)

    def list_repository_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        labels: str | None = None,
        per_page: int = 30,
    ) -> list[IssueInfo]:
        """Return issues for a repository."""
        params: dict = {"state": state, "per_page": per_page}
        if labels:
            params["labels"] = labels
        data = self._request("GET", f"/repos/{owner}/{repo}/issues", params=params)
        return [IssueInfo.from_api(item) for item in data]

    def search_issues(self, query: str, per_page: int = 30) -> list[IssueInfo]:
        """Search GitHub issues using the search API."""
        data = self._request(
            "GET",
            "/search/issues",
            params={"q": query, "per_page": per_page},
        )
        return [IssueInfo.from_api(item) for item in data.get("items", [])]

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()
