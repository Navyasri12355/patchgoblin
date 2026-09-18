"""Tests for Pydantic domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo

# ---------------------------------------------------------------------------
# RepositoryInfo
# ---------------------------------------------------------------------------


_REPO_API = {
    "owner": {"login": "pallets"},
    "name": "flask",
    "full_name": "pallets/flask",
    "description": "Python micro framework.",
    "html_url": "https://github.com/pallets/flask",
    "language": "Python",
    "stargazers_count": 60000,
    "forks_count": 15000,
    "open_issues_count": 30,
    "default_branch": "main",
}


def test_repository_info_from_api() -> None:
    repo = RepositoryInfo.from_api(_REPO_API)
    assert repo.owner == "pallets"
    assert repo.name == "flask"
    assert repo.full_name == "pallets/flask"
    assert repo.stars == 60000
    assert repo.forks == 15000
    assert repo.open_issues == 30
    assert repo.language == "Python"
    assert repo.default_branch == "main"


def test_repository_info_optional_fields() -> None:
    data = dict(_REPO_API)
    data["description"] = None
    data["language"] = None
    repo = RepositoryInfo.from_api(data)
    assert repo.description is None
    assert repo.language is None


def test_repository_info_missing_required_raises() -> None:
    with pytest.raises((ValidationError, KeyError)):
        # Missing 'owner', 'name', etc.
        RepositoryInfo.from_api({"full_name": "pallets/flask"})


# ---------------------------------------------------------------------------
# IssueInfo
# ---------------------------------------------------------------------------


_ISSUE_API = {
    "number": 42,
    "title": "A great bug",
    "body": "Here is the description.",
    "state": "open",
    "html_url": "https://github.com/pallets/flask/issues/42",
    "labels": [{"name": "bug"}, {"name": "good first issue"}],
    "user": {"login": "someone"},
    "comments": 3,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-06-01T00:00:00Z",
}


def test_issue_info_from_api() -> None:
    issue = IssueInfo.from_api(_ISSUE_API)
    assert issue.number == 42
    assert issue.title == "A great bug"
    assert issue.state == "open"
    assert "bug" in issue.labels
    assert "good first issue" in issue.labels
    assert issue.author == "someone"
    assert issue.comments == 3


def test_issue_info_empty_labels() -> None:
    data = dict(_ISSUE_API)
    data["labels"] = []
    issue = IssueInfo.from_api(data)
    assert issue.labels == []


def test_issue_info_missing_required_raises() -> None:
    with pytest.raises((ValidationError, KeyError)):
        IssueInfo.from_api({"number": 1})


# ---------------------------------------------------------------------------
# ContributorProfile
# ---------------------------------------------------------------------------


_USER_API = {
    "login": "goblindev",
    "name": "Goblin Dev",
    "bio": "I love open source",
    "public_repos": 25,
    "followers": 120,
    "following": 40,
    "html_url": "https://github.com/goblindev",
}


def test_contributor_profile_from_api() -> None:
    profile = ContributorProfile.from_api(_USER_API)
    assert profile.username == "goblindev"
    assert profile.name == "Goblin Dev"
    assert profile.public_repositories == 25
    assert profile.followers == 120
    assert profile.following == 40
    assert profile.profile_url == "https://github.com/goblindev"


def test_contributor_profile_optional_name() -> None:
    data = dict(_USER_API)
    data["name"] = None
    data["bio"] = None
    profile = ContributorProfile.from_api(data)
    assert profile.name is None
    assert profile.bio is None


def test_contributor_profile_missing_login_raises() -> None:
    with pytest.raises((ValidationError, KeyError)):
        ContributorProfile.from_api({"name": "No Login"})


# ---------------------------------------------------------------------------
# Security: model fields must not inadvertently store tokens
# ---------------------------------------------------------------------------


def test_contributor_profile_does_not_store_token() -> None:
    """Ensure the model has no field that could accidentally hold a token."""
    profile = ContributorProfile.from_api(_USER_API)
    model_json = profile.model_dump_json()
    assert "token" not in model_json.lower()
    assert "secret" not in model_json.lower()
