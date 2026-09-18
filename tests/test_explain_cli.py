"""Tests for the goblin explain CLI command."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from patchgoblin.cli.app import app
from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.models.analysis import IssueAnalysis

runner = CliRunner()


def _make_issue(**kw) -> IssueInfo:
    defaults = {
        "number": 1,
        "title": "Improve error message for invalid configuration",
        "body": "When an invalid config is provided, the error is cryptic.",
        "state": "open",
        "url": "https://github.com/pallets/flask/issues/1",
        "labels": ["bug"],
        "author": "alice",
        "comments": 0,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
    }
    defaults.update(kw)
    return IssueInfo(**defaults)


def _make_repo(**kw) -> RepositoryInfo:
    defaults = {
        "owner": "pallets",
        "name": "flask",
        "full_name": "pallets/flask",
        "url": "https://github.com/pallets/flask",
        "language": "Python",
    }
    defaults.update(kw)
    return RepositoryInfo(**defaults)


def _make_analysis(**kw) -> IssueAnalysis:
    defaults = {
        "summary": "The issue concerns improving the error message for invalid configuration.",
        "problem": "Error message is unhelpful.",
        "expected_behavior": "Clear message pointing to the problem.",
        "current_behavior": "Cryptic traceback.",
        "likely_components": ["Configuration", "Error handling"],
        "likely_files": [{"path": "flask/config.py", "reason": "handles config"}],
        "implementation_steps": ["Locate error", "Update message", "Add test"],
        "testing_strategy": "Add regression test.",
        "potential_risks": ["Backwards compatibility"],
        "unknowns": ["Whether old behavior is relied on externally"],
        "confidence": "medium",
    }
    defaults.update(kw)
    return IssueAnalysis.model_validate(defaults)


def _mock_explain_result():
    from patchgoblin.services.explain import ExplainResult

    return ExplainResult(
        issue=_make_issue(),
        repo=_make_repo(),
        analysis=_make_analysis(),
        commit_sha="abc123def456",
        model_used="gpt-4o-mini",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_explain_help():
    result = runner.invoke(app, ["explain", "--help"])
    assert result.exit_code == 0
    assert "explain" in result.output.lower() or "analysis" in result.output.lower()


def test_explain_missing_github_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    result = runner.invoke(app, ["explain", "pallets/flask#1"])
    assert result.exit_code == 1
    assert "authenticated" in result.output.lower() or "token" in result.output.lower()


def test_explain_missing_llm_api_key(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    result = runner.invoke(app, ["explain", "pallets/flask#1"])
    assert result.exit_code == 1
    assert "LLM_API_KEY" in result.output


def test_explain_invalid_reference(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    result = runner.invoke(app, ["explain", "not-a-valid-ref"])
    assert result.exit_code == 1
    assert "invalid" in result.output.lower()


def test_explain_success_output(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("patchgoblin.cli.explain.create_explain_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.explain.return_value = _mock_explain_result()
        mock_factory.return_value = mock_service

        result = runner.invoke(app, ["explain", "pallets/flask#1"])

    assert result.exit_code == 0
    # Should contain key analysis content
    assert "flask" in result.output.lower()
    assert "config" in result.output.lower()
    assert "abc123def456"[:8] in result.output or "abc123" in result.output


def test_explain_no_credentials_in_output(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_super_secret_token")
    monkeypatch.setenv("LLM_API_KEY", "sk-super-secret-key")

    with patch("patchgoblin.cli.explain.create_explain_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.explain.return_value = _mock_explain_result()
        mock_factory.return_value = mock_service

        result = runner.invoke(app, ["explain", "pallets/flask#1"])

    assert "ghp_super_secret_token" not in result.output
    assert "sk-super-secret-key" not in result.output


def test_explain_graceful_failure(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("patchgoblin.cli.explain.create_explain_service") as mock_factory:
        from patchgoblin.services.explain import ExplainError

        mock_service = MagicMock()
        mock_service.explain.side_effect = ExplainError("LLM provider returned an error")
        mock_factory.return_value = mock_service

        result = runner.invoke(app, ["explain", "pallets/flask#1"])

    assert result.exit_code == 1
    # Should suggest the inspect command as a fallback
    assert "inspect" in result.output
    assert "LLM" in result.output or "Analysis Failed" in result.output


def test_explain_skip_clone_flag(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("patchgoblin.cli.explain.create_explain_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.explain.return_value = _mock_explain_result()
        mock_factory.return_value = mock_service

        result = runner.invoke(app, ["explain", "--skip-clone", "pallets/flask#1"])

    assert result.exit_code == 0
    # Verify --skip-clone was passed to factory as clone_repos=False
    call_kwargs = mock_factory.call_args.kwargs
    assert call_kwargs.get("clone_repos") is False


def test_explain_model_flag(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    with patch("patchgoblin.cli.explain.create_explain_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.explain.return_value = _mock_explain_result()
        mock_factory.return_value = mock_service

        result = runner.invoke(app, ["explain", "--model", "gpt-4o", "pallets/flask#1"])
        assert result.exit_code == 0
        call_kwargs = mock_factory.call_args.kwargs
        assert call_kwargs.get("model") == "gpt-4o"
