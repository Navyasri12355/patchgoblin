"""Issue analysis — deterministic heuristics."""

from __future__ import annotations

from patchgoblin.analysis.difficulty import (
    _DOCUMENTATION_LABELS,
    _HELP_WANTED_LABELS,
    _TEST_LABELS,
    estimate_difficulty,
)
from patchgoblin.github.models import IssueInfo, RepositoryInfo

# Labels commonly associated with beginner-friendly issues.
_BEGINNER_LABELS = frozenset(
    {
        "good first issue",
        "good-first-issue",
        "first-timers-only",
        "beginner",
        "beginner-friendly",
        "easy",
        "starter",
        "newcomer",
        "low-hanging-fruit",
        "low hanging fruit",
    }
)

# Labels that suggest this is NOT a beginner task.
_NEGATIVE_LABELS = frozenset(
    {
        "breaking change",
        "breaking-change",
        "architecture",
        "security",
        "performance",
        "large feature",
        "epic",
        "refactor",
    }
)

# Simple keyword checks on title / body
_POSITIVE_KEYWORDS = frozenset(
    {"typo", "documentation", "readme", "test", "add test", "fix test", "docs"}
)
_NEGATIVE_KEYWORDS = frozenset(
    {
        "refactor",
        "architecture",
        "redesign",
        "rewrite",
        "performance",
        "security",
        "vulnerability",
        "breaking change",
        "overhaul",
        "migrate",
    }
)


def _label_set(issue: IssueInfo) -> frozenset[str]:
    return frozenset(lbl.lower() for lbl in issue.labels)


def is_beginner_friendly(issue: IssueInfo) -> bool:
    """Return True if the issue has a beginner-friendly label."""
    return bool(_BEGINNER_LABELS & _label_set(issue))


def is_newbie_friendly(issue: IssueInfo, repo: RepositoryInfo | None = None) -> bool:
    """
    Return True if observable signals suggest this issue is accessible to newcomers.

    Checks labels, title keywords, and body keywords.
    A single negative signal overrides positive ones to stay conservative.
    """
    labels = _label_set(issue)
    title = issue.title.lower()
    body = (issue.body or "").lower()

    # Immediate negative: explicitly complex label
    if labels & _NEGATIVE_LABELS:
        return False

    # Negative keyword in title
    if any(kw in title for kw in _NEGATIVE_KEYWORDS):
        return False

    positive = 0

    if labels & _BEGINNER_LABELS:
        positive += 2
    if labels & _HELP_WANTED_LABELS:
        positive += 1
    if labels & _DOCUMENTATION_LABELS:
        positive += 1
    if labels & _TEST_LABELS:
        positive += 1
    if any(kw in title for kw in _POSITIVE_KEYWORDS):
        positive += 1
    if any(kw in body for kw in _POSITIVE_KEYWORDS):
        positive += 1

    return positive > 0


def analyze_issue(issue: IssueInfo, repo: RepositoryInfo | None = None) -> dict:
    """Return a structured analysis dict for an issue."""
    return {
        "number": issue.number,
        "title": issue.title,
        "state": issue.state,
        "label_count": len(issue.labels),
        "beginner_friendly": is_beginner_friendly(issue),
        "newbie_friendly": is_newbie_friendly(issue, repo),
        "estimated_difficulty": estimate_difficulty(issue).value,
        "has_description": bool(issue.body and issue.body.strip()),
        "comment_count": issue.comments,
    }
