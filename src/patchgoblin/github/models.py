"""GitHub domain models for PatchGoblin."""

from __future__ import annotations

from datetime import datetime

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
