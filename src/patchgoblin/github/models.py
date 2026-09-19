"""GitHub domain models for PatchGoblin."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RepositoryInfo(BaseModel):
    """A trimmed-down view of a GitHub repository."""

    owner: str
    name: str
    full_name: str
    description: str | None = None
    url: str
    language: str | None = None
    stars: int = Field(alias="stargazers_count", default=0)
    forks: int = Field(alias="forks_count", default=0)
    open_issues: int = Field(alias="open_issues_count", default=0)
    default_branch: str = "main"

    model_config = {"populate_by_name": True}

    @classmethod
    def from_api(cls, data: dict) -> RepositoryInfo:
        """Construct from a raw GitHub API response dict."""
        return cls(
            owner=data["owner"]["login"],
            name=data["name"],
            full_name=data["full_name"],
            description=data.get("description"),
            url=data["html_url"],
            language=data.get("language"),
            stargazers_count=data.get("stargazers_count", 0),
            forks_count=data.get("forks_count", 0),
            open_issues_count=data.get("open_issues_count", 0),
            default_branch=data.get("default_branch", "main"),
        )


class IssueInfo(BaseModel):
    """A trimmed-down view of a GitHub issue."""

    number: int
    title: str
    body: str | None = None
    state: str
    url: str
    labels: list[str] = Field(default_factory=list)
    author: str
    comments: int = 0
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_api(cls, data: dict) -> IssueInfo:
        """Construct from a raw GitHub API response dict."""
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            url=data["html_url"],
            labels=[lbl["name"] for lbl in data.get("labels", [])],
            author=data["user"]["login"],
            comments=data.get("comments", 0),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


class ContributorProfile(BaseModel):
    """A trimmed-down view of an authenticated GitHub user."""

    username: str
    name: str | None = None
    bio: str | None = None
    public_repositories: int = 0
    followers: int = 0
    following: int = 0
    profile_url: str
    # Populated by the discovery service after fetching the user's public repos.
    known_languages: list[str] = Field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> ContributorProfile:
        """Construct from a raw GitHub API response dict."""
        return cls(
            username=data["login"],
            name=data.get("name"),
            bio=data.get("bio"),
            public_repositories=data.get("public_repos", 0),
            followers=data.get("followers", 0),
            following=data.get("following", 0),
            profile_url=data["html_url"],
        )


class PullRequestInfo(BaseModel):
    """A trimmed-down view of a GitHub pull request."""

    number: int
    title: str
    body: str | None = None
    state: str
    url: str
    head_ref: str
    base_ref: str
    head_repo: str
    base_repo: str
    author: str
    created_at: datetime
    updated_at: datetime
    draft: bool = False
    merged: bool = False
    mergeable: bool | None = None

    @classmethod
    def from_api(cls, data: dict) -> PullRequestInfo:
        """Construct from a raw GitHub API response dict."""
        return cls(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            url=data["html_url"],
            head_ref=data["head"]["ref"],
            base_ref=data["base"]["ref"],
            head_repo=data["head"]["repo"]["full_name"],
            base_repo=data["base"]["repo"]["full_name"],
            author=data["user"]["login"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            draft=data.get("draft", False),
            merged=data.get("merged", False),
            mergeable=data.get("mergeable"),
        )


class PRReviewState(StrEnum):
    """State of a PR review."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"


class PRComment(BaseModel):
    """A comment on a pull request."""

    id: int
    author: str
    body: str
    created_at: datetime
    updated_at: datetime
    path: str | None = None
    position: int | None = None

    @classmethod
    def from_api(cls, data: dict) -> PRComment:
        """Construct from a raw GitHub API response dict."""
        return cls(
            id=data["id"],
            author=data["user"]["login"],
            body=data["body"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            path=data.get("path"),
            position=data.get("position"),
        )


class PRReview(BaseModel):
    """A review on a pull request."""

    id: int
    author: str
    state: PRReviewState
    body: str | None = None
    submitted_at: datetime

    @classmethod
    def from_api(cls, data: dict) -> PRReview:
        """Construct from a raw GitHub API response dict."""
        state_mapping = {
            "APPROVED": PRReviewState.APPROVED,
            "CHANGES_REQUESTED": PRReviewState.CHANGES_REQUESTED,
            "COMMENTED": PRReviewState.COMMENTED,
            "DISMISSED": PRReviewState.DISMISSED,
            "PENDING": PRReviewState.PENDING,
        }
        state = state_mapping.get(data.get("state", "PENDING"), PRReviewState.PENDING)

        return cls(
            id=data["id"],
            author=data["user"]["login"],
            state=state,
            body=data.get("body"),
            submitted_at=data["submitted_at"],
        )


class PRCheckRun(BaseModel):
    """A CI check run on a pull request."""

    id: int
    name: str
    status: str
    conclusion: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    url: str

    @classmethod
    def from_api(cls, data: dict) -> PRCheckRun:
        """Construct from a raw GitHub API response dict."""
        return cls(
            id=data["id"],
            name=data["name"],
            status=data["status"],
            conclusion=data.get("conclusion"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            url=data["html_url"],
        )
