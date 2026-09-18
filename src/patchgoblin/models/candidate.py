"""ContributionCandidate — domain model for a discovered contribution opportunity."""

from __future__ import annotations

from pydantic import BaseModel, Field

from patchgoblin.analysis.difficulty import Difficulty
from patchgoblin.github.models import IssueInfo, RepositoryInfo


class ContributionCandidate(BaseModel):
    """A potential open-source issue that PatchGoblin has evaluated."""

    repository: RepositoryInfo
    issue: IssueInfo

    # Derived signals
    language: str | None = None
    good_first_issue: bool = False
    help_wanted: bool = False
    documentation_related: bool = False
    estimated_difficulty: Difficulty = Difficulty.UNKNOWN

    # Fit heuristic
    fit_score: int = Field(default=0, ge=0, le=100)
    fit_reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    @property
    def issue_ref(self) -> str:
        """Return the canonical issue reference: owner/repo#N."""
        return f"{self.repository.full_name}#{self.issue.number}"
