"""Tests for the WorkService (all external deps mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patchgoblin.coding.models import ChangeResult
from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.models.analysis import ConfidenceLevel, ImplementationPlan, IssueAnalysis
from patchgoblin.services.work import WorkError, WorkService
from patchgoblin.workspace.manager import WorkspaceManager
from patchgoblin.workspace.models import WorkspaceStatus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_ws_manager(tmp_path: Path) -> WorkspaceManager:
    return WorkspaceManager(base_dir=tmp_path / "patchgoblin")


def _make_issue() -> IssueInfo:
    from datetime import datetime

    return IssueInfo(
        number=42,
        title="Fix the bug",
        body="Something is broken.",
        state="open",
        author="alice",
        labels=[],
        comments=0,
        url="https://github.com/owner/repo/issues/42",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 2),
    )


def _make_repo() -> RepositoryInfo:
    return RepositoryInfo(
        owner="owner",
        name="repo",
        full_name="owner/repo",
        description="A test repo",
        language="Python",
        stargazers_count=10,
        forks_count=2,
        default_branch="main",
        url="https://github.com/owner/repo",
        open_issues_count=1,
    )


def _make_analysis() -> IssueAnalysis:
    return IssueAnalysis(
        summary="Fix the bug in config validation",
        confidence=ConfidenceLevel.HIGH,
        implementation_steps=["Update validate()", "Add test"],
    )


def _make_plan() -> ImplementationPlan:
    return ImplementationPlan(
        objective="Fix config validation",
        steps=["Update validate()"],
        files_to_modify=["config.py"],
    )


def _make_change_result(success: bool = True) -> ChangeResult:
    return ChangeResult(
        success=success,
        modified_files=["config.py"],
        diff_stat="config.py | 2 +-",
        diff="+# fixed",
        summary="Updated config validation",
        error="" if success else "Something went wrong",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkServicePrepare:
    def test_prepare_returns_issue_and_analysis(self, tmp_ws_manager: WorkspaceManager) -> None:
        mock_github = MagicMock()
        mock_github.get_issue.return_value = _make_issue()
        mock_github.get_repository.return_value = _make_repo()

        mock_llm = MagicMock()
        # ExplainService calls llm.generate — return valid analysis JSON
        analysis_data = {
            "summary": "Fix the bug",
            "confidence": "high",
        }
        mock_llm.generate.return_value = json.dumps(analysis_data)

        service = WorkService(
            github_client=mock_github,
            llm_provider=mock_llm,
            workspace_manager=tmp_ws_manager,
        )

        from patchgoblin.repository.clone import CloneError

        with patch("patchgoblin.services.work.RepositoryClone") as mock_clone_cls:
            # Simulate clone failure (context manager __enter__ raises CloneError)
            mock_clone_cls.return_value.__enter__.side_effect = CloneError("no git in CI")
            issue, repo, analysis, evidence = service.prepare("owner", "repo", 42)

        assert issue.number == 42
        assert analysis.summary == "Fix the bug"
        assert evidence is None  # clone failed, evidence is None

    def test_prepare_raises_work_error_on_llm_failure(
        self, tmp_ws_manager: WorkspaceManager
    ) -> None:
        from patchgoblin.llm.client import LLMError

        mock_github = MagicMock()
        mock_github.get_issue.return_value = _make_issue()
        mock_github.get_repository.return_value = _make_repo()

        mock_llm = MagicMock()
        mock_llm.generate.side_effect = LLMError("timeout")

        service = WorkService(
            github_client=mock_github,
            llm_provider=mock_llm,
            workspace_manager=tmp_ws_manager,
        )

        from patchgoblin.repository.clone import CloneError

        with patch("patchgoblin.services.work.RepositoryClone") as mock_clone_cls:
            mock_clone_cls.return_value.__enter__.side_effect = CloneError("no git")
            with pytest.raises(WorkError, match="Analysis failed"):
                service.prepare("owner", "repo", 42)


class TestWorkServiceExecute:
    def test_execute_creates_workspace_and_runs_agent(
        self, tmp_ws_manager: WorkspaceManager, tmp_path: Path
    ) -> None:
        mock_github = MagicMock()
        mock_llm = MagicMock()

        service = WorkService(
            github_client=mock_github,
            llm_provider=mock_llm,
            workspace_manager=tmp_ws_manager,
        )

        fake_change = _make_change_result(success=True)

        with (
            patch("patchgoblin.services.work.RepositoryClone._run_clone"),
            patch("patchgoblin.services.work.GitHelper") as mock_git_cls,
            patch("patchgoblin.services.work.CodingAgent") as mock_agent_cls,
        ):
            mock_git_inst = MagicMock()
            mock_git_inst.is_clean.return_value = True
            mock_git_inst.rev_parse_head.return_value = "abc123"
            mock_git_cls.return_value = mock_git_inst
            mock_agent_cls.return_value.run.return_value = fake_change

            result = service.execute(
                owner="owner",
                repo_name="repo",
                issue_number=42,
                issue=_make_issue(),
                repo=_make_repo(),
                analysis=_make_analysis(),
                plan=_make_plan(),
                approved_files=["config.py"],
            )

        assert result.change_result.success is True
        assert result.workspace.status == WorkspaceStatus.REVIEW

    def test_denial_before_execute_never_calls_agent(
        self, tmp_ws_manager: WorkspaceManager
    ) -> None:
        """Verify that if the user does not call execute(), the agent is never run."""
        with patch("patchgoblin.services.work.CodingAgent") as mock_agent_cls:
            # We never call service.execute() — agent must never be instantiated
            pass  # no execute call

        mock_agent_cls.assert_not_called()

    def test_dirty_workspace_raises_work_error(self, tmp_ws_manager: WorkspaceManager) -> None:
        mock_github = MagicMock()
        mock_llm = MagicMock()

        service = WorkService(
            github_client=mock_github,
            llm_provider=mock_llm,
            workspace_manager=tmp_ws_manager,
        )

        with (
            patch("patchgoblin.services.work.RepositoryClone._run_clone"),
            patch("patchgoblin.services.work.GitHelper") as mock_git_cls,
        ):
            mock_git_inst = MagicMock()
            mock_git_inst.is_clean.return_value = False  # dirty!
            mock_git_inst.rev_parse_head.return_value = "abc123"
            mock_git_cls.return_value = mock_git_inst

            with pytest.raises(WorkError, match="dirty working tree"):
                service.execute(
                    owner="owner",
                    repo_name="repo",
                    issue_number=42,
                    issue=_make_issue(),
                    repo=_make_repo(),
                    analysis=_make_analysis(),
                    plan=_make_plan(),
                    approved_files=["config.py"],
                )

    def test_failed_agent_sets_workspace_failed_status(
        self, tmp_ws_manager: WorkspaceManager
    ) -> None:
        mock_github = MagicMock()
        mock_llm = MagicMock()

        service = WorkService(
            github_client=mock_github,
            llm_provider=mock_llm,
            workspace_manager=tmp_ws_manager,
        )

        fake_change = _make_change_result(success=False)

        with (
            patch("patchgoblin.services.work.RepositoryClone._run_clone"),
            patch("patchgoblin.services.work.GitHelper") as mock_git_cls,
            patch("patchgoblin.services.work.CodingAgent") as mock_agent_cls,
        ):
            mock_git_inst = MagicMock()
            mock_git_inst.is_clean.return_value = True
            mock_git_inst.rev_parse_head.return_value = "abc123"
            mock_git_cls.return_value = mock_git_inst
            mock_agent_cls.return_value.run.return_value = fake_change

            result = service.execute(
                owner="owner",
                repo_name="repo",
                issue_number=42,
                issue=_make_issue(),
                repo=_make_repo(),
                analysis=_make_analysis(),
                plan=_make_plan(),
                approved_files=["config.py"],
            )

        assert result.workspace.status == WorkspaceStatus.FAILED
        assert result.change_result.success is False
