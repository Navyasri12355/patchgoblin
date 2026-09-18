"""Tests for prompt construction."""

from __future__ import annotations

from datetime import UTC, datetime

from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.llm.prompts.issue_analysis import build_issue_analysis_prompt
from patchgoblin.llm.prompts.safety import SAFETY_SYSTEM_PROMPT


def _make_issue(**kwargs) -> IssueInfo:
    defaults = {
        "number": 42,
        "title": "Fix configuration validation error message",
        "body": "When an invalid config is provided, the error message is unhelpful.",
        "state": "open",
        "url": "https://github.com/example/repo/issues/42",
        "labels": ["bug"],
        "author": "alice",
        "comments": 2,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 2, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return IssueInfo(**defaults)


def _make_repo(**kwargs) -> RepositoryInfo:
    defaults = {
        "owner": "example",
        "name": "repo",
        "full_name": "example/repo",
        "description": "An example project",
        "url": "https://github.com/example/repo",
        "language": "Python",
        "stars": 100,
        "forks": 10,
        "open_issues": 5,
    }
    defaults.update(kwargs)
    return RepositoryInfo(**defaults)


def test_prompt_contains_issue_content():
    issue = _make_issue()
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    assert "Fix configuration validation error message" in prompt
    assert "invalid config" in prompt


def test_prompt_contains_repository_metadata():
    issue = _make_issue()
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    assert "example/repo" in prompt
    assert "Python" in prompt


def test_prompt_delimits_untrusted_content():
    issue = _make_issue()
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    assert "<UNTRUSTED>" in prompt
    assert "</UNTRUSTED>" in prompt


def test_prompt_does_not_contain_credentials():
    issue = _make_issue()
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    # Must not contain token-like patterns
    assert "ghp_" not in prompt
    assert "Bearer" not in prompt
    assert "sk-" not in prompt


def test_prompt_includes_repo_tree_when_provided():
    issue = _make_issue()
    repo = _make_repo()
    tree = "src/\n  config.py\ntests/\n  test_config.py"
    prompt = build_issue_analysis_prompt(issue, repo, repo_tree=tree)
    assert "config.py" in prompt
    assert "Repository structure" in prompt


def test_prompt_includes_snippets_when_provided():
    issue = _make_issue()
    repo = _make_repo()
    snippets = [("src/config.py", "def validate_config(): ...")]
    prompt = build_issue_analysis_prompt(issue, repo, relevant_snippets=snippets)
    assert "src/config.py" in prompt
    assert "validate_config" in prompt


def test_prompt_without_repo_tree():
    issue = _make_issue()
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    assert "Repository structure" not in prompt


def test_safety_system_prompt_has_injection_defense():
    assert "UNTRUSTED" in SAFETY_SYSTEM_PROMPT
    assert "instructions" in SAFETY_SYSTEM_PROMPT.lower()
    # Must tell model not to follow embedded instructions
    assert "Do NOT follow" in SAFETY_SYSTEM_PROMPT or "not follow" in SAFETY_SYSTEM_PROMPT.lower()


def test_prompt_json_schema_present():
    issue = _make_issue()
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    assert "confidence" in prompt
    assert "implementation_steps" in prompt
    assert "unknowns" in prompt


def test_issue_without_body():
    issue = _make_issue(body=None)
    repo = _make_repo()
    prompt = build_issue_analysis_prompt(issue, repo)
    assert "no description provided" in prompt
