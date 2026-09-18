"""Tests for the ExplainService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.llm.client import LLMAuthError, LLMResponseError
from patchgoblin.models.analysis import ConfidenceLevel
from patchgoblin.services.explain import ExplainError, ExplainService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(**kw) -> IssueInfo:
    defaults = {
        "number": 42,
        "title": "Fix config validation error",
        "body": "The error message is unhelpful.",
        "state": "open",
        "url": "https://github.com/ex/repo/issues/42",
        "labels": ["bug"],
        "author": "alice",
        "comments": 1,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
    }
    defaults.update(kw)
    return IssueInfo(**defaults)


def _make_repo(**kw) -> RepositoryInfo:
    defaults = {
        "owner": "ex",
        "name": "repo",
        "full_name": "ex/repo",
        "url": "https://github.com/ex/repo",
    }
    defaults.update(kw)
    return RepositoryInfo(**defaults)


def _minimal_analysis_json() -> str:
    import json

    return json.dumps(
        {
            "summary": "Fix config error messages",
            "problem": "Messages are unhelpful",
            "expected_behavior": "Clear message",
            "current_behavior": "Cryptic message",
            "likely_components": ["config"],
            "likely_files": [{"path": "src/config.py", "reason": "config handling"}],
            "implementation_steps": ["locate error", "update message"],
            "testing_strategy": "unit test",
            "potential_risks": [],
            "unknowns": [],
            "confidence": "medium",
        }
    )


def _make_service(llm_response: str, clone_repos: bool = False) -> ExplainService:
    mock_github = MagicMock()
    mock_github.get_issue.return_value = _make_issue()
    mock_github.get_repository.return_value = _make_repo()

    mock_llm = MagicMock()
    mock_llm.generate.return_value = llm_response

    return ExplainService(
        github_client=mock_github,
        llm_provider=mock_llm,
        model_name="test-model",
        clone_repos=clone_repos,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_explain_success():
    service = _make_service(_minimal_analysis_json())
    result = service.explain("ex", "repo", 42)
    assert result.analysis.summary == "Fix config error messages"
    assert result.analysis.confidence == ConfidenceLevel.MEDIUM
    assert result.model_used == "test-model"


def test_explain_components_composed_correctly():
    """Verify that the service calls GitHub and LLM in order."""
    mock_github = MagicMock()
    mock_github.get_issue.return_value = _make_issue()
    mock_github.get_repository.return_value = _make_repo()
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _minimal_analysis_json()

    service = ExplainService(
        github_client=mock_github,
        llm_provider=mock_llm,
        model_name="m",
        clone_repos=False,
    )
    service.explain("ex", "repo", 42)

    mock_github.get_issue.assert_called_once_with("ex", "repo", 42)
    mock_github.get_repository.assert_called_once_with("ex", "repo")
    mock_llm.generate.assert_called_once()


def test_explain_llm_error_raises_explain_error():
    service = _make_service("irrelevant")
    service._llm.generate.side_effect = LLMAuthError("bad key")
    with pytest.raises(ExplainError):
        service.explain("ex", "repo", 42)


def test_explain_malformed_json_raises_explain_error():
    service = _make_service("not valid json at all!!")
    with pytest.raises(LLMResponseError):
        service.explain("ex", "repo", 42)


def test_explain_invalid_schema_raises():
    import json

    bad = json.dumps({"no_summary_field": "oops"})
    service = _make_service(bad)
    with pytest.raises(LLMResponseError):
        service.explain("ex", "repo", 42)


def test_explain_strips_markdown_code_fences():
    fenced = "```json\n" + _minimal_analysis_json() + "\n```"
    service = _make_service(fenced)
    result = service.explain("ex", "repo", 42)
    assert result.analysis.summary == "Fix config error messages"


def test_explain_no_clone_sets_commit_sha_sentinel():
    service = _make_service(_minimal_analysis_json(), clone_repos=False)
    result = service.explain("ex", "repo", 42)
    assert result.commit_sha == "not-cloned"


def test_llm_generate_receives_no_credentials():
    """The prompt sent to the LLM must not contain token-like strings."""
    service = _make_service(_minimal_analysis_json())
    service.explain("ex", "repo", 42)
    call_args = service._llm.generate.call_args
    prompt: str = call_args.args[0] if call_args.args else call_args.kwargs.get("prompt", "")
    system: str = call_args.kwargs.get("system", "") or ""
    full_text = prompt + system
    # No credential patterns
    assert "ghp_" not in full_text
    assert "sk-" not in full_text
    assert "Bearer" not in full_text


def test_explain_clone_failure_gracefully_continues():
    """If clone fails, analysis should still proceed using GitHub metadata only."""
    mock_github = MagicMock()
    mock_github.get_issue.return_value = _make_issue()
    mock_github.get_repository.return_value = _make_repo()
    mock_llm = MagicMock()
    mock_llm.generate.return_value = _minimal_analysis_json()

    service = ExplainService(
        github_client=mock_github,
        llm_provider=mock_llm,
        model_name="m",
        clone_repos=True,
    )

    from patchgoblin.repository.clone import CloneError

    with patch(
        "patchgoblin.services.explain.RepositoryClone.__enter__",
        side_effect=CloneError("network error"),
    ):
        result = service.explain("ex", "repo", 42)

    assert result.analysis.summary == "Fix config error messages"
