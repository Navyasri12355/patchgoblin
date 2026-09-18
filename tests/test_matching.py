"""Tests for contribution-fit matching and newbie-friendly detection."""

from __future__ import annotations

from datetime import UTC, datetime

from patchgoblin.analysis.difficulty import Difficulty
from patchgoblin.analysis.issue import is_newbie_friendly
from patchgoblin.analysis.matching import FitResult, calculate_fit
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo

_NOW = datetime.now(tz=UTC)


def _make_issue(
    labels: list[str] | None = None,
    title: str = "Fix the thing",
    body: str | None = "Detailed description here.",
    comments: int = 2,
) -> IssueInfo:
    return IssueInfo(
        number=42,
        title=title,
        body=body,
        state="open",
        url="https://github.com/pallets/flask/issues/42",
        labels=labels or [],
        author="contributor",
        comments=comments,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_repo(language: str | None = "Python", stars: int = 5000) -> RepositoryInfo:
    return RepositoryInfo(
        owner="pallets",
        name="flask",
        full_name="pallets/flask",
        url="https://github.com/pallets/flask",
        language=language,
        stargazers_count=stars,
        forks_count=500,
        open_issues_count=30,
    )


def _make_contributor(languages: list[str] | None = None) -> ContributorProfile:
    return ContributorProfile(
        username="devuser",
        name="Dev User",
        public_repositories=10,
        followers=5,
        following=3,
        profile_url="https://github.com/devuser",
        known_languages=languages or [],
    )


# ---------------------------------------------------------------------------
# is_newbie_friendly
# ---------------------------------------------------------------------------


def test_newbie_friendly_good_first_issue() -> None:
    issue = _make_issue(labels=["good first issue"])
    assert is_newbie_friendly(issue) is True


def test_newbie_friendly_documentation_label() -> None:
    issue = _make_issue(labels=["documentation"])
    assert is_newbie_friendly(issue) is True


def test_newbie_friendly_typo_in_title() -> None:
    issue = _make_issue(title="Fix typo in docs")
    assert is_newbie_friendly(issue) is True


def test_not_newbie_friendly_security_label() -> None:
    issue = _make_issue(labels=["security"])
    assert is_newbie_friendly(issue) is False


def test_not_newbie_friendly_breaking_change_label() -> None:
    issue = _make_issue(labels=["breaking change"])
    assert is_newbie_friendly(issue) is False


def test_not_newbie_friendly_refactor_in_title() -> None:
    issue = _make_issue(title="Refactor entire codebase")
    assert is_newbie_friendly(issue) is False


def test_newbie_friendly_conflicting_labels_returns_false() -> None:
    # Negative label overrides positive
    issue = _make_issue(labels=["good first issue", "security"])
    assert is_newbie_friendly(issue) is False


def test_newbie_friendly_no_signals_returns_false() -> None:
    issue = _make_issue(labels=[], title="Something vague", body=None)
    assert is_newbie_friendly(issue) is False


# ---------------------------------------------------------------------------
# calculate_fit — score direction
# ---------------------------------------------------------------------------


def test_language_match_increases_score() -> None:
    repo = _make_repo(language="Python")
    contributor_match = _make_contributor(languages=["python"])
    contributor_no_match = _make_contributor(languages=["Go"])

    fit_match = calculate_fit(_make_issue(), repo, contributor_match)
    fit_no_match = calculate_fit(_make_issue(), repo, contributor_no_match)

    assert fit_match.score > fit_no_match.score


def test_good_first_issue_increases_score() -> None:
    repo = _make_repo()
    contributor = _make_contributor()

    fit_with = calculate_fit(_make_issue(labels=["good first issue"]), repo, contributor)
    fit_without = calculate_fit(_make_issue(labels=[]), repo, contributor)

    assert fit_with.score > fit_without.score


def test_advanced_label_decreases_score() -> None:
    repo = _make_repo()
    contributor = _make_contributor()

    fit_advanced = calculate_fit(_make_issue(labels=["architecture"]), repo, contributor)
    fit_plain = calculate_fit(_make_issue(labels=[]), repo, contributor)

    assert fit_advanced.score < fit_plain.score


def test_score_within_bounds() -> None:
    repo = _make_repo()
    contributor = _make_contributor(languages=["python"])
    issue = _make_issue(
        labels=["good first issue", "help wanted", "documentation"],
        body="Detailed steps here.",
    )
    fit = calculate_fit(issue, repo, contributor)
    assert 0 <= fit.score <= 100


def test_score_within_bounds_worst_case() -> None:
    repo = _make_repo()
    contributor = _make_contributor(languages=[])
    issue = _make_issue(
        labels=["architecture", "security", "epic"],
        body=None,
        comments=50,
    )
    fit = calculate_fit(issue, repo, contributor)
    assert 0 <= fit.score <= 100


def test_fit_result_has_reasons() -> None:
    repo = _make_repo(language="Python")
    contributor = _make_contributor(languages=["python"])
    issue = _make_issue(labels=["good first issue"])
    fit = calculate_fit(issue, repo, contributor)
    assert len(fit.reasons) > 0


def test_fit_result_has_concerns_for_advanced() -> None:
    repo = _make_repo()
    contributor = _make_contributor()
    issue = _make_issue(labels=["architecture"])
    fit = calculate_fit(issue, repo, contributor)
    assert len(fit.concerns) > 0


def test_fit_result_type() -> None:
    repo = _make_repo()
    contributor = _make_contributor()
    issue = _make_issue()
    fit = calculate_fit(issue, repo, contributor)
    assert isinstance(fit, FitResult)
    assert isinstance(fit.difficulty, Difficulty)
