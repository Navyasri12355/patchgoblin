"""Tests for the discovery service and query builder."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from patchgoblin.github.client import GitHubAPIError, GitHubClient
from patchgoblin.github.models import ContributorProfile
from patchgoblin.models.candidate import ContributionCandidate
from patchgoblin.services.discovery import DiscoveryFilters, discover_candidates
from patchgoblin.services.query import build_issue_search_query

BASE = "https://api.github.com"
_NOW = datetime.now(tz=UTC).isoformat()

_USER = {
    "login": "devuser",
    "name": "Dev User",
    "bio": None,
    "public_repos": 5,
    "followers": 10,
    "following": 5,
    "html_url": "https://github.com/devuser",
}

_REPO = {
    "owner": {"login": "pallets"},
    "name": "flask",
    "full_name": "pallets/flask",
    "description": "Micro framework",
    "html_url": "https://github.com/pallets/flask",
    "language": "Python",
    "stargazers_count": 60000,
    "forks_count": 15000,
    "open_issues_count": 30,
    "default_branch": "main",
}

_ISSUE = {
    "number": 123,
    "title": "Fix documentation typo",
    "body": "There is a typo.",
    "state": "open",
    "html_url": "https://github.com/pallets/flask/issues/123",
    "labels": [{"name": "good first issue"}, {"name": "documentation"}],
    "user": {"login": "someone"},
    "comments": 2,
    "created_at": _NOW,
    "updated_at": _NOW,
}

_USER_REPOS = [
    {"language": "Python"},
    {"language": "JavaScript"},
    {"language": None},
]

_SEARCH_RESPONSE = {"items": [_ISSUE], "total_count": 1}


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------


def test_query_basic() -> None:
    q = build_issue_search_query()
    assert "is:issue" in q
    assert "is:open" in q


def test_query_with_language() -> None:
    q = build_issue_search_query(language="python")
    assert "language:python" in q


def test_query_with_label() -> None:
    q = build_issue_search_query(label="good first issue")
    assert 'label:"good first issue"' in q


def test_query_with_min_stars() -> None:
    q = build_issue_search_query(min_stars=100)
    assert "stars:>=100" in q


def test_query_with_star_range() -> None:
    q = build_issue_search_query(min_stars=100, max_stars=50000)
    assert "stars:100..50000" in q


def test_query_with_topic() -> None:
    q = build_issue_search_query(topic="machine-learning")
    assert "topic:machine-learning" in q


def test_query_invalid_language_raises() -> None:
    with pytest.raises(ValueError, match="Invalid language"):
        build_issue_search_query(language="py thon!")


def test_query_invalid_label_raises() -> None:
    with pytest.raises(ValueError, match="Invalid label"):
        build_issue_search_query(label='<script>alert("xss")</script>')


# ---------------------------------------------------------------------------
# Discovery service
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> GitHubClient:
    return GitHubClient("ghp_testtoken", base_url=BASE)


@respx.mock
def test_discover_candidates_returns_candidates(client: GitHubClient) -> None:
    respx.get(f"{BASE}/search/issues").mock(return_value=httpx.Response(200, json=_SEARCH_RESPONSE))
    respx.get(f"{BASE}/user/repos").mock(return_value=httpx.Response(200, json=_USER_REPOS))
    respx.get(f"{BASE}/repos/pallets/flask").mock(return_value=httpx.Response(200, json=_REPO))

    contributor = ContributorProfile(
        username="devuser",
        public_repositories=5,
        followers=10,
        following=5,
        profile_url="https://github.com/devuser",
    )
    results = discover_candidates(client, contributor, DiscoveryFilters(limit=5))
    assert len(results) >= 1
    assert isinstance(results[0], ContributionCandidate)
    assert results[0].issue.number == 123


@respx.mock
def test_discover_candidates_respects_limit(client: GitHubClient) -> None:
    many_issues = [dict(_ISSUE, number=i) for i in range(1, 10)]
    for issue in many_issues:
        issue["html_url"] = f"https://github.com/pallets/flask/issues/{issue['number']}"

    respx.get(f"{BASE}/search/issues").mock(
        return_value=httpx.Response(200, json={"items": many_issues, "total_count": 9})
    )
    respx.get(f"{BASE}/user/repos").mock(return_value=httpx.Response(200, json=_USER_REPOS))
    respx.get(f"{BASE}/repos/pallets/flask").mock(return_value=httpx.Response(200, json=_REPO))

    contributor = ContributorProfile(
        username="devuser",
        public_repositories=5,
        followers=10,
        following=5,
        profile_url="https://github.com/devuser",
    )
    results = discover_candidates(client, contributor, DiscoveryFilters(limit=3))
    assert len(results) <= 3


@respx.mock
def test_discover_candidates_deduplicates_repo_requests(client: GitHubClient) -> None:
    """Two issues from the same repo should only cause one repo API call."""
    issue_a = dict(_ISSUE, number=1)
    issue_b = dict(_ISSUE, number=2)
    issue_a["html_url"] = "https://github.com/pallets/flask/issues/1"
    issue_b["html_url"] = "https://github.com/pallets/flask/issues/2"

    respx.get(f"{BASE}/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [issue_a, issue_b], "total_count": 2})
    )
    respx.get(f"{BASE}/user/repos").mock(return_value=httpx.Response(200, json=_USER_REPOS))
    repo_route = respx.get(f"{BASE}/repos/pallets/flask").mock(
        return_value=httpx.Response(200, json=_REPO)
    )

    contributor = ContributorProfile(
        username="devuser",
        public_repositories=5,
        followers=10,
        following=5,
        profile_url="https://github.com/devuser",
    )
    discover_candidates(client, contributor, DiscoveryFilters(limit=5))
    # Repo should have been fetched exactly once
    assert repo_route.call_count == 1


@respx.mock
def test_discover_candidates_empty_results(client: GitHubClient) -> None:
    respx.get(f"{BASE}/search/issues").mock(
        return_value=httpx.Response(200, json={"items": [], "total_count": 0})
    )
    respx.get(f"{BASE}/user/repos").mock(return_value=httpx.Response(200, json=[]))

    contributor = ContributorProfile(
        username="devuser",
        public_repositories=5,
        followers=10,
        following=5,
        profile_url="https://github.com/devuser",
    )
    results = discover_candidates(client, contributor)
    assert results == []


@respx.mock
def test_discover_candidates_api_failure_on_search(client: GitHubClient) -> None:
    respx.get(f"{BASE}/search/issues").mock(
        return_value=httpx.Response(500, json={"message": "Server error"})
    )
    contributor = ContributorProfile(
        username="devuser",
        public_repositories=5,
        followers=10,
        following=5,
        profile_url="https://github.com/devuser",
    )
    with pytest.raises(GitHubAPIError):
        discover_candidates(client, contributor)
