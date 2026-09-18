"""Tests for CLI commands."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from patchgoblin.cli.app import app
from patchgoblin.github.models import ContributorProfile

runner = CliRunner()


# ---------------------------------------------------------------------------
# --help
# ---------------------------------------------------------------------------


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "goblin" in result.output.lower() or "patchgoblin" in result.output.lower()


def test_auth_help() -> None:
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# auth status
# ---------------------------------------------------------------------------


def test_auth_status_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code != 0
    assert "not configured" in result.output
    # Token must never appear in output
    assert "GITHUB_TOKEN" not in result.output or "Set GITHUB_TOKEN" in result.output


def test_auth_status_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    fake_profile = ContributorProfile(
        username="testuser",
        name="Test User",
        bio=None,
        public_repositories=10,
        followers=5,
        following=3,
        profile_url="https://github.com/testuser",
    )
    with patch("patchgoblin.cli.auth.GitHubClient") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = fake_profile
        result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "valid" in result.output
    assert "testuser" in result.output
    # Token value must never appear in output
    assert "ghp_testtoken" not in result.output


def test_auth_status_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_badtoken")
    from patchgoblin.github.client import GitHubAuthError

    with patch("patchgoblin.cli.auth.GitHubClient") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.side_effect = GitHubAuthError("bad token")
        result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code != 0
    assert "ghp_badtoken" not in result.output


# ---------------------------------------------------------------------------
# auth logout
# ---------------------------------------------------------------------------


def test_auth_logout() -> None:
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0
    assert "unset" in result.output.lower() or "GITHUB_TOKEN" in result.output


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------


def test_profile_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(app, ["profile"])
    assert result.exit_code != 0


def test_profile_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    fake_profile = ContributorProfile(
        username="navyasri",
        name="Navya",
        bio="Open source contributor",
        public_repositories=20,
        followers=50,
        following=30,
        profile_url="https://github.com/navyasri",
    )
    with patch("patchgoblin.cli.profile.GitHubClient") as mock_client:
        instance = mock_client.return_value.__enter__.return_value
        instance.get_authenticated_user.return_value = fake_profile
        result = runner.invoke(app, ["profile"])
    assert result.exit_code == 0
    assert "navyasri" in result.output
    assert "ghp_testtoken" not in result.output


# ---------------------------------------------------------------------------
# issue reference parsing
# ---------------------------------------------------------------------------


def test_valid_issue_reference() -> None:
    from patchgoblin.cli.parse import parse_issue_reference

    ref = parse_issue_reference("pallets/flask#123")
    assert ref.owner == "pallets"
    assert ref.repo == "flask"
    assert ref.number == 123


def test_issue_reference_missing_hash() -> None:
    from patchgoblin.cli.parse import parse_issue_reference

    with pytest.raises(ValueError, match="Invalid issue reference"):
        parse_issue_reference("pallets/flask/123")


def test_issue_reference_missing_owner() -> None:
    from patchgoblin.cli.parse import parse_issue_reference

    with pytest.raises(ValueError):
        parse_issue_reference("/flask#123")


def test_issue_reference_non_numeric() -> None:
    from patchgoblin.cli.parse import parse_issue_reference

    with pytest.raises(ValueError):
        parse_issue_reference("pallets/flask#abc")


def test_issue_reference_empty() -> None:
    from patchgoblin.cli.parse import parse_issue_reference

    with pytest.raises(ValueError):
        parse_issue_reference("")


# ---------------------------------------------------------------------------
# inspect command
# ---------------------------------------------------------------------------


def test_inspect_malformed_ref() -> None:
    result = runner.invoke(app, ["inspect", "not-valid"])
    assert result.exit_code != 0
    assert "invalid" in result.output.lower() or "Invalid" in result.output


def test_inspect_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = runner.invoke(app, ["inspect", "pallets/flask#123"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# find command
# ---------------------------------------------------------------------------


def test_find_requires_auth() -> None:
    """goblin find without a token should exit non-zero and mention authentication."""
    result = runner.invoke(app, ["find"])
    assert result.exit_code != 0
    assert (
        "not authenticated" in result.output.lower() or "goblin auth login" in result.output.lower()
    )
