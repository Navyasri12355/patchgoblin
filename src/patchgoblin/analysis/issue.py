"""Issue analysis — deterministic heuristics for Stage 1."""

from __future__ import annotations

from patchgoblin.github.models import IssueInfo

# Labels commonly associated with beginner-friendly issues.
_BEGINNER_LABELS = frozenset(
    {
        "good first issue",
        "good-first-issue",
        "beginner",
        "beginner-friendly",
        "easy",
        "starter",
        "help wanted",
    }
)


def is_beginner_friendly(issue: IssueInfo) -> bool:
    """Return True if the issue has a beginner-friendly label."""
    return bool(_BEGINNER_LABELS & {lbl.lower() for lbl in issue.labels})


def analyze_issue(issue: IssueInfo) -> dict:
    """
    Return a simple analysis dict for an issue.

    This is a deterministic Stage 1 placeholder.
    LLM-based analysis will be introduced in a later stage.
    """
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "label_count": len(issue.labels),
        "beginner_friendly": is_beginner_friendly(issue),
        "has_description": bool(issue.body and issue.body.strip()),
        "comment_count": issue.comments,
    }
