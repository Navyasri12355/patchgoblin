"""Deterministic difficulty estimator for GitHub issues."""

from __future__ import annotations

from enum import StrEnum

from patchgoblin.github.models import IssueInfo

# ---------------------------------------------------------------------------
# Difficulty levels
# ---------------------------------------------------------------------------


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Label keyword sets
# ---------------------------------------------------------------------------

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

_HELP_WANTED_LABELS = frozenset({"help wanted", "help-wanted"})

_DOCUMENTATION_LABELS = frozenset({"documentation", "docs", "doc", "typo", "readme"})

_TEST_LABELS = frozenset({"test", "tests", "testing"})

_ADVANCED_LABELS = frozenset(
    {
        "architecture",
        "refactor",
        "performance",
        "security",
        "breaking change",
        "breaking-change",
        "compiler",
        "internals",
        "major",
        "epic",
    }
)

# ---------------------------------------------------------------------------
# Title/body keyword sets
# ---------------------------------------------------------------------------

_BEGINNER_TITLE_KEYWORDS = frozenset(
    {"typo", "documentation", "readme", "test", "tests", "add test", "fix typo"}
)

_COMPLEX_TITLE_KEYWORDS = frozenset(
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


def estimate_difficulty(issue: IssueInfo) -> Difficulty:
    """
    Return a deterministic difficulty estimate for an issue.

    The estimate is based on observable signals (labels, title keywords).
    When signals conflict the function returns UNKNOWN rather than
    inventing confidence.
    """
    labels = _label_set(issue)
    title_lower = issue.title.lower()

    beginner_signals = 0
    advanced_signals = 0

    # Label signals
    if labels & _BEGINNER_LABELS:
        beginner_signals += 2
    if labels & _HELP_WANTED_LABELS:
        beginner_signals += 1
    if labels & _DOCUMENTATION_LABELS:
        beginner_signals += 1
    if labels & _TEST_LABELS:
        beginner_signals += 1
    if labels & _ADVANCED_LABELS:
        advanced_signals += 2

    # Title keyword signals
    if any(kw in title_lower for kw in _BEGINNER_TITLE_KEYWORDS):
        beginner_signals += 1
    if any(kw in title_lower for kw in _COMPLEX_TITLE_KEYWORDS):
        advanced_signals += 1

    # Comment thread length — very long threads suggest complexity
    if issue.comments > 30:
        advanced_signals += 1
    elif issue.comments > 50:
        advanced_signals += 2

    # Resolve
    if beginner_signals > 0 and advanced_signals == 0:
        return Difficulty.BEGINNER
    if advanced_signals > 0 and beginner_signals == 0:
        return Difficulty.ADVANCED
    if beginner_signals > 0 and advanced_signals > 0:
        # Conflicting signals — lean beginner only if beginner is clearly stronger
        if beginner_signals >= advanced_signals * 2:
            return Difficulty.BEGINNER
        return Difficulty.UNKNOWN
    return Difficulty.UNKNOWN
