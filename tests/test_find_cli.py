"""CLI tests for goblin find (Stage 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from patchgoblin.analysis.difficulty import Difficulty
from patchgoblin.cli.app import app
from patchgoblin.github.models import ContributorProfile, IssueInfo, RepositoryInfo
from patchgoblin.models.candidate import ContributionCandidate

runner = CliRunner()
_NOW = datetime.now(tz=UTC)


def _make_candidate(
    fit_score: int = 75,
    language: str = "Python",
    labels: list[str] | None = None,
) -> ContributionCandidate:
    repo = RepositoryInfo(
        owner="pallets",
        name="flask",
        full_name="pallets/flask",
        url="https://github.com/pallets/flask",
        language=language,
        stargazers_count=5000,
        forks_count=1000,
        open_issues_count=20,
    )
    issue = IssueInfo(
        number=42,
        title="Fix documentation typo",
        body="A small typo.",
        state="open",
        url="https://github.com/pallets/flask/issues/42",
        labels=labels or ["good first issue"],
        author="contributor",
        comments=2,
        created_at=_NOW,
        updated_at=_NOW,
    )
    return ContributionCandidate(
        repository=repo,
        issue=issue,
        language=language,
        good_first_issue=True,
        help_wanted=False,
        documentation_related=False,
        estimated_difficulty=Difficulty.BEGINNER,
        fit_score=fit_score,
        fit_reasons=["Repository uses Python", 'Labeled "good first issue"'],
        concerns=[],
    )


def _make_contributor() -> ContributorProfile:
    return ContributorProfile(
        username="devuser",
        name="Dev User",
        public_repositories=10,
        followers=5,
        following=3,
        profile_url="https://github.com/devuser",
        known_languages=["python"],
    )


# ---------------------------------------------------------------------------
# goblin find --help
# ---------------------------------------------------------------------------


def test_find_help() -> None:
    result = runner.invoke(app, ["find", "--help"])
    assert result.exit_code == 0
    # The help text should include option descriptions
    assert "language" in result.output.lower()


# ---------------------------------------------------------------------------
# Missing token
# ---------------------------------------------------------------------------


def test_find_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(app, ["find"])
    assert result.exit_code != 0
    assert "not authenticated" in result.output.lower() or "GITHUB_TOKEN" in result.output


# ---------------------------------------------------------------------------
# Successful find
# ---------------------------------------------------------------------------


def test_find_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    candidates = [_make_candidate()]
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=candidates),
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find"])

    assert result.exit_code == 0
    assert "1" in result.output  # at least one result row
    assert "ghp_testtoken" not in result.output


def test_find_language_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    candidates = [_make_candidate()]
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=candidates) as mock_disc,
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find", "--language", "python"])

    assert result.exit_code == 0
    # Verify the filter was forwarded
    call_args = mock_disc.call_args
    assert call_args is not None
    filters = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("filters")
    assert filters is not None
    assert filters.language == "python"


def test_find_label_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    candidates = [_make_candidate()]
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=candidates) as mock_disc,
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find", "--label", "good-first-issue"])

    assert result.exit_code == 0
    call_args = mock_disc.call_args
    filters = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("filters")
    assert filters is not None
    assert filters.label == "good-first-issue"


def test_find_limit_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    candidates = [_make_candidate()]
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=candidates) as mock_disc,
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find", "--limit", "5"])

    assert result.exit_code == 0
    call_args = mock_disc.call_args
    filters = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("filters")
    assert filters is not None
    assert filters.limit == 5


def test_find_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=[]),
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find"])

    assert result.exit_code == 0
    assert "no candidates" in result.output.lower()


def test_find_verbose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    candidates = [_make_candidate()]
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=candidates),
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find", "--verbose"])

    assert result.exit_code == 0
    # Verbose mode should show signals
    assert "Signals" in result.output or "signal" in result.output.lower()


def test_find_token_never_in_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_supersecrettoken")
    candidates = [_make_candidate()]
    contributor = _make_contributor()

    with (
        patch("patchgoblin.cli.find.GitHubClient") as mock_client,
        patch("patchgoblin.cli.find.discover_candidates", return_value=candidates),
    ):
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = contributor
        result = runner.invoke(app, ["find"])

    assert "ghp_supersecrettoken" not in result.output
