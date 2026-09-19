"""GitHub API client."""

from __future__ import annotations

import httpx

from patchgoblin.config import Config
from patchgoblin.github.models import (
    ContributorProfile,
    IssueInfo,
    PRCheckRun,
    PRComment,
    PRReview,
    PullRequestInfo,
    RepositoryInfo,
)


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

    def search_issues(self, query: str, per_page: int = 30, page: int = 1) -> list[IssueInfo]:
        """Search GitHub issues using the search API."""
        data = self._request(
            "GET",
            "/search/issues",
            params={"q": query, "per_page": per_page, "page": page},
        )
        return [IssueInfo.from_api(item) for item in data.get("items", [])]

    def list_user_repos(self, per_page: int = 100) -> list[dict]:
        """Return the authenticated user's public repositories (raw API dicts)."""
        return self._request(
            "GET",
            "/user/repos",
            params={"per_page": per_page, "type": "owner", "sort": "updated"},
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Stage 5: Pull Request and Feedback methods
    # ------------------------------------------------------------------

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str,
        draft: bool = False,
    ) -> PullRequestInfo:
        """Create a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            title: PR title.
            head: Head branch (e.g., "feature-branch" or "owner:feature-branch").
            base: Base branch (e.g., "main").
            body: PR body/description.
            draft: Whether to create as a draft PR.

        Returns:
            PullRequestInfo with the created PR details.
        """
        data = self._request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "head": head,
                "base": base,
                "body": body,
                "draft": draft,
            },
        )
        return PullRequestInfo.from_api(data)

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequestInfo:
        """Get a single pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            PullRequestInfo with the PR details.
        """
        data = self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")
        return PullRequestInfo.from_api(data)

    def list_pull_request_comments(self, owner: str, repo: str, pr_number: int) -> list[PRComment]:
        """List comments on a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of PRComment objects.
        """
        data = self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/comments")
        return [PRComment.from_api(item) for item in data]

    def list_pull_request_reviews(self, owner: str, repo: str, pr_number: int) -> list[PRReview]:
        """List reviews on a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of PRReview objects.
        """
        data = self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")
        return [PRReview.from_api(item) for item in data]

    def list_pull_request_check_runs(
        self, owner: str, repo: str, pr_number: int
    ) -> list[PRCheckRun]:
        """List CI check runs for a pull request.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of PRCheckRun objects.
        """
        # Get the PR to find the head commit SHA
        pr = self.get_pull_request(owner, repo, pr_number)
        # Use the combined status endpoint which is more commonly available
        data = self._request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{pr.head_ref}/status",
        )
        # Convert statuses to check-run-like objects
        check_runs = []
        for status in data.get("statuses", []):
            check_runs.append(
                PRCheckRun(
                    id=status.get("id", 0),
                    name=status.get("context", "unknown"),
                    status=status.get("state", "unknown"),
                    conclusion="success" if status.get("state") == "success" else "failure",
                    started_at=status.get("created_at", ""),
                    completed_at=status.get("updated_at"),
                    url=status.get("target_url", ""),
                )
            )
        return check_runs
