"""Tests for the GitHub API client (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
import respx

from patchgoblin.github.client import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo

BASE = "https://api.github.com"

_USER_PAYLOAD = {
    "login": "testuser",
    "name": "Test User",
    "bio": "Bio here",
    "public_repos": 42,
    "followers": 100,
    "following": 50,
    "html_url": "https://github.com/testuser",
}

_REPO_PAYLOAD = {
    "owner": {"login": "pallets"},
    "name": "flask",
    "full_name": "pallets/flask",
    "description": "The Python micro framework.",
    "html_url": "https://github.com/pallets/flask",
    "language": "Python",
    "stargazers_count": 60000,
    "forks_count": 15000,
    "open_issues_count": 30,
    "default_branch": "main",
}

_ISSUE_PAYLOAD = {
    "number": 123,
    "title": "Fix the bug",
    "body": "It is broken.",
    "state": "open",
    "html_url": "https://github.com/pallets/flask/issues/123",
    "labels": [{"name": "bug"}, {"name": "good first issue"}],
    "user": {"login": "contributor"},
    "comments": 5,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-06-01T00:00:00Z",
}


@pytest.fixture()
def client() -> GitHubClient:
    return GitHubClient("ghp_testtoken", base_url=BASE)


# ---------------------------------------------------------------------------
# get_authenticated_user
# ---------------------------------------------------------------------------


@respx.mock
def test_get_authenticated_user(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json=_USER_PAYLOAD))
    profile = client.get_authenticated_user()
    assert isinstance(profile, ContributorProfile)
    assert profile.username == "testuser"
    assert profile.public_repositories == 42


@respx.mock
def test_get_authenticated_user_401(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    with pytest.raises(GitHubAuthError):
        client.get_authenticated_user()


@respx.mock
def test_get_authenticated_user_403(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(403, json={"message": "Forbidden"}))
    with pytest.raises(GitHubAuthError):
        client.get_authenticated_user()


# ---------------------------------------------------------------------------
# get_repository
# ---------------------------------------------------------------------------


@respx.mock
def test_get_repository(client: GitHubClient) -> None:
    respx.get(f"{BASE}/repos/pallets/flask").mock(
        return_value=httpx.Response(200, json=_REPO_PAYLOAD)
    )
    repo = client.get_repository("pallets", "flask")
    assert isinstance(repo, RepositoryInfo)
    assert repo.full_name == "pallets/flask"
    assert repo.stars == 60000


@respx.mock
def test_get_repository_not_found(client: GitHubClient) -> None:
    respx.get(f"{BASE}/repos/nobody/nothing").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    with pytest.raises(GitHubNotFoundError):
        client.get_repository("nobody", "nothing")


# ---------------------------------------------------------------------------
# get_issue
# ---------------------------------------------------------------------------


@respx.mock
def test_get_issue(client: GitHubClient) -> None:
    respx.get(f"{BASE}/repos/pallets/flask/issues/123").mock(
        return_value=httpx.Response(200, json=_ISSUE_PAYLOAD)
    )
    issue = client.get_issue("pallets", "flask", 123)
    assert isinstance(issue, IssueInfo)
    assert issue.number == 123
    assert issue.title == "Fix the bug"
    assert "bug" in issue.labels
    assert "good first issue" in issue.labels


@respx.mock
def test_get_issue_not_found(client: GitHubClient) -> None:
    respx.get(f"{BASE}/repos/pallets/flask/issues/9999").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    with pytest.raises(GitHubNotFoundError):
        client.get_issue("pallets", "flask", 9999)


# ---------------------------------------------------------------------------
# search_issues
# ---------------------------------------------------------------------------


@respx.mock
def test_search_issues(client: GitHubClient) -> None:
    respx.get(f"{BASE}/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [_ISSUE_PAYLOAD], "total_count": 1})
    )
    issues = client.search_issues("label:good-first-issue language:python")
    assert len(issues) == 1
    assert issues[0].number == 123


# ---------------------------------------------------------------------------
# rate limit
# ---------------------------------------------------------------------------


@respx.mock
def test_rate_limit(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(403, text="rate limit exceeded"))
    with pytest.raises(GitHubRateLimitError):
        client.get_authenticated_user()


# ---------------------------------------------------------------------------
# network failure
# ---------------------------------------------------------------------------


@respx.mock
def test_network_error(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(side_effect=httpx.NetworkError("unreachable"))
    with pytest.raises(GitHubAPIError):
        client.get_authenticated_user()


# ---------------------------------------------------------------------------
# security: token must not appear in exceptions
# ---------------------------------------------------------------------------


@respx.mock
def test_token_not_in_exception_message(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )
    with pytest.raises(GitHubAuthError) as exc_info:
        client.get_authenticated_user()
    assert "ghp_testtoken" not in str(exc_info.value)


@respx.mock
def test_token_not_in_api_error_message(client: GitHubClient) -> None:
    respx.get(f"{BASE}/user").mock(
        return_value=httpx.Response(500, json={"message": "Server error"})
    )
    with pytest.raises(GitHubAPIError) as exc_info:
        client.get_authenticated_user()
    assert "ghp_testtoken" not in str(exc_info.value)
