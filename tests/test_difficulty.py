"""Tests for difficulty estimation."""

from __future__ import annotations

from datetime import UTC, datetime

from patchgoblin.analysis.difficulty import Difficulty, estimate_difficulty
from patchgoblin.github.models import IssueInfo

_NOW = datetime.now(tz=UTC)


def _make_issue(
    labels: list[str] | None = None,
    title: str = "Some issue",
    body: str | None = None,
    comments: int = 0,
) -> IssueInfo:
    return IssueInfo(
        number=1,
        title=title,
        body=body,
        state="open",
        url="https://github.com/owner/repo/issues/1",
        labels=labels or [],
        author="user",
        comments=comments,
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Beginner signals
# ---------------------------------------------------------------------------


def test_good_first_issue_label_is_beginner() -> None:
    issue = _make_issue(labels=["good first issue"])
    assert estimate_difficulty(issue) == Difficulty.BEGINNER


def test_first_timers_only_is_beginner() -> None:
    issue = _make_issue(labels=["first-timers-only"])
    assert estimate_difficulty(issue) == Difficulty.BEGINNER


def test_documentation_label_is_beginner() -> None:
    issue = _make_issue(labels=["documentation"])
    assert estimate_difficulty(issue) == Difficulty.BEGINNER


def test_test_label_is_beginner() -> None:
    issue = _make_issue(labels=["tests"])
    assert estimate_difficulty(issue) == Difficulty.BEGINNER


def test_help_wanted_alone_is_beginner() -> None:
    issue = _make_issue(labels=["help wanted"])
    assert estimate_difficulty(issue) == Difficulty.BEGINNER


def test_typo_in_title_is_beginner() -> None:
    issue = _make_issue(title="Fix typo in README")
    assert estimate_difficulty(issue) == Difficulty.BEGINNER


# ---------------------------------------------------------------------------
# Advanced signals
# ---------------------------------------------------------------------------


def test_architecture_label_is_advanced() -> None:
    issue = _make_issue(labels=["architecture"])
    assert estimate_difficulty(issue) == Difficulty.ADVANCED


def test_security_label_is_advanced() -> None:
    issue = _make_issue(labels=["security"])
    assert estimate_difficulty(issue) == Difficulty.ADVANCED


def test_performance_label_is_advanced() -> None:
    issue = _make_issue(labels=["performance"])
    assert estimate_difficulty(issue) == Difficulty.ADVANCED


def test_refactor_in_title_is_advanced() -> None:
    issue = _make_issue(title="Refactor the entire auth module")
    assert estimate_difficulty(issue) == Difficulty.ADVANCED


def test_very_many_comments_pushes_toward_advanced() -> None:
    # No labels, no keyword — but 35 comments adds advanced signal → ADVANCED
    issue = _make_issue(comments=35)
    assert estimate_difficulty(issue) == Difficulty.ADVANCED


# ---------------------------------------------------------------------------
# Conflicting / unknown signals
# ---------------------------------------------------------------------------


def test_conflicting_signals_unknown() -> None:
    issue = _make_issue(labels=["good first issue", "architecture"])
    result = estimate_difficulty(issue)
    # Beginner signal (2) vs advanced signal (2) — equal → UNKNOWN
    assert result == Difficulty.UNKNOWN


def test_no_signals_unknown() -> None:
    issue = _make_issue()
    assert estimate_difficulty(issue) == Difficulty.UNKNOWN


def test_empty_body_no_signal() -> None:
    issue = _make_issue(body="")
    assert estimate_difficulty(issue) == Difficulty.UNKNOWN
