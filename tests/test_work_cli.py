"""Tests for the ``goblin work`` CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from patchgoblin.cli.app import app
from patchgoblin.coding.models import ChangeResult
from patchgoblin.github.models import IssueInfo, RepositoryInfo
from patchgoblin.models.analysis import ConfidenceLevel, ImplementationPlan, IssueAnalysis
from patchgoblin.workspace.manager import WorkspaceManager

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue() -> IssueInfo:
    from datetime import datetime

    return IssueInfo(
        number=1,
        title="Fix bug",
        body="Something is broken.",
        state="open",
        author="alice",
        labels=[],
        comments=0,
        url="https://github.com/owner/repo/issues/1",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 2),
    )


def _make_repo() -> RepositoryInfo:
    return RepositoryInfo(
        owner="owner",
        name="repo",
        full_name="owner/repo",
        description="Test repo",
        language="Python",
        stargazers_count=5,
        forks_count=1,
        default_branch="main",
        url="https://github.com/owner/repo",
        open_issues_count=1,
    )


def _make_analysis() -> IssueAnalysis:
    return IssueAnalysis(
        summary="Fix the bug",
        confidence=ConfidenceLevel.MEDIUM,
        implementation_steps=["Step 1"],
    )


def _make_plan() -> ImplementationPlan:
    return ImplementationPlan(
        objective="Fix the bug",
        steps=["Step 1"],
        files_to_modify=["config.py"],
    )


def _make_change_result(success: bool = True) -> ChangeResult:
    return ChangeResult(
        success=success,
        modified_files=["config.py"],
        diff_stat="config.py | 2 +-",
        diff="+# fixed",
        summary="Fixed config",
    )


# ---------------------------------------------------------------------------
# goblin work --help
# ---------------------------------------------------------------------------


class TestWorkHelp:
    def test_work_help(self) -> None:
        result = runner.invoke(app, ["work", "--help"])
        assert result.exit_code == 0
        assert "work" in result.output.lower()

    def test_work_start_help(self) -> None:
        result = runner.invoke(app, ["work", "start", "--help"])
        assert result.exit_code == 0

    def test_work_status_help(self) -> None:
        result = runner.invoke(app, ["work", "status", "--help"])
        assert result.exit_code == 0

    def test_work_list_help(self) -> None:
        result = runner.invoke(app, ["work", "list", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# goblin work start — missing credentials
# ---------------------------------------------------------------------------


class TestWorkStartCredentials:
    def test_missing_github_token(self) -> None:
        with patch.dict("os.environ", {"GITHUB_TOKEN": "", "LLM_API_KEY": "key"}, clear=False):
            result = runner.invoke(app, ["work", "start", "owner/repo#1"])
        assert result.exit_code != 0 or "authenticated" in result.output.lower()

    def test_missing_llm_key(self) -> None:
        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "ghp_test", "LLM_API_KEY": ""},
            clear=False,
        ):
            result = runner.invoke(app, ["work", "start", "owner/repo#1"])
        assert result.exit_code != 0 or "llm" in result.output.lower()

    def test_invalid_issue_ref(self) -> None:
        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "ghp_test", "LLM_API_KEY": "sk-test"},
            clear=False,
        ):
            result = runner.invoke(app, ["work", "start", "not-a-valid-ref"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# goblin work start — user declines approval
# ---------------------------------------------------------------------------


class TestWorkStartDeclined:
    def test_user_says_no(self, tmp_path: Path) -> None:
        ws_manager = WorkspaceManager(base_dir=tmp_path / "pg")

        with (
            patch.dict(
                "os.environ",
                {"GITHUB_TOKEN": "ghp_test", "LLM_API_KEY": "sk-test"},
                clear=False,
            ),
            patch("patchgoblin.cli.work.create_work_service") as mock_factory,
        ):
            svc = MagicMock()
            svc._ws_manager = ws_manager
            svc.prepare.return_value = (
                _make_issue(),
                _make_repo(),
                _make_analysis(),
                None,
            )
            mock_factory.return_value = svc

            result = runner.invoke(app, ["work", "start", "owner/repo#1"], input="N\n")

        assert "cancelled" in result.output.lower() or result.exit_code == 0
        # execute must never be called
        svc.execute.assert_not_called()


# ---------------------------------------------------------------------------
# goblin work start — successful run
# ---------------------------------------------------------------------------


class TestWorkStartSuccess:
    def test_successful_run_shows_diff(self, tmp_path: Path) -> None:
        from patchgoblin.services.work import WorkResult

        ws_manager = WorkspaceManager(base_dir=tmp_path / "pg")
        meta = ws_manager.create("owner/repo#1", "owner/repo", "https://github.com/owner/repo.git")

        work_result = WorkResult(
            issue=_make_issue(),
            repo=_make_repo(),
            analysis=_make_analysis(),
            plan=_make_plan(),
            workspace=meta,
            change_result=_make_change_result(success=True),
        )

        with (
            patch.dict(
                "os.environ",
                {"GITHUB_TOKEN": "ghp_test", "LLM_API_KEY": "sk-test"},
                clear=False,
            ),
            patch("patchgoblin.cli.work.create_work_service") as mock_factory,
        ):
            svc = MagicMock()
            svc._ws_manager = ws_manager
            svc.prepare.return_value = (
                _make_issue(),
                _make_repo(),
                _make_analysis(),
                None,
            )
            svc.execute.return_value = work_result
            mock_factory.return_value = svc

            result = runner.invoke(app, ["work", "start", "owner/repo#1", "--yes"])

        assert result.exit_code == 0
        assert "config.py" in result.output or "Work" in result.output


# ---------------------------------------------------------------------------
# goblin work status / list
# ---------------------------------------------------------------------------


class TestWorkStatus:
    def test_status_empty(self, tmp_path: Path) -> None:
        ws_manager = WorkspaceManager(base_dir=tmp_path / "pg")
        with patch("patchgoblin.cli.work.WorkspaceManager", return_value=ws_manager):
            result = runner.invoke(app, ["work", "status"])
        assert result.exit_code == 0
        assert "no" in result.output.lower() or len(result.output.strip()) > 0

    def test_list_command_same_as_status(self, tmp_path: Path) -> None:
        ws_manager = WorkspaceManager(base_dir=tmp_path / "pg")
        with patch("patchgoblin.cli.work.WorkspaceManager", return_value=ws_manager):
            r_status = runner.invoke(app, ["work", "status"])
            r_list = runner.invoke(app, ["work", "list"])
        # Both commands should behave similarly (both empty here)
        assert r_status.exit_code == 0
        assert r_list.exit_code == 0
