"""Analysis models produced by the AI-powered explain stage."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class ConfidenceLevel(StrEnum):
    """How well available evidence supports the analysis."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FileEvidence(BaseModel):
    """A single file identified as likely relevant to the issue."""

    path: str = Field(description="Relative file path inside the repository.")
    reason: str = Field(description="Why this file is likely relevant.")


class IssueAnalysis(BaseModel):
    """Structured AI analysis of a GitHub issue against a repository."""

    summary: str = Field(description="One-sentence summary of what the issue asks for.")
    problem: str = Field(default="", description="Description of the problem or bug.")
    expected_behavior: str = Field(
        default="", description="What should happen according to the issue."
    )
    current_behavior: str = Field(
        default="", description="What currently happens according to the issue."
    )
    likely_components: list[str] = Field(
        default_factory=list,
        description="Repository components or subsystems involved.",
    )
    likely_files: list[FileEvidence] = Field(
        default_factory=list,
        description="Files likely to be modified.",
    )
    implementation_steps: list[str] = Field(
        default_factory=list,
        description="High-level ordered steps to implement the fix.",
    )
    testing_strategy: str = Field(default="", description="Suggested approach to testing the fix.")
    potential_risks: list[str] = Field(
        default_factory=list,
        description="Backward-compatibility concerns or risks.",
    )
    unknowns: list[str] = Field(
        default_factory=list,
        description="Things that cannot be determined from available evidence.",
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="How well evidence supports this analysis.",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalise_confidence(cls, v: object) -> object:
        """Accept case-insensitive confidence strings."""
        if isinstance(v, str):
            return v.lower()
        return v


class ImplementationPlan(BaseModel):
    """High-level implementation plan derived from issue analysis."""

    objective: str = Field(description="One-sentence statement of what needs to be done.")
    steps: list[str] = Field(
        default_factory=list,
        description="Ordered high-level implementation steps.",
    )
    files_to_modify: list[str] = Field(
        default_factory=list,
        description="Existing files likely to be changed.",
    )
    files_to_add: list[str] = Field(
        default_factory=list,
        description="New files likely to be created.",
    )
    tests_to_update: list[str] = Field(
        default_factory=list,
        description="Test files likely to need changes.",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Risks and concerns for the implementation.",
    )
    unknowns: list[str] = Field(
        default_factory=list,
        description="Things that remain unknown.",
    )
