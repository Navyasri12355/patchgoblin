"""Tests for the CodingAgent (LLM mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patchgoblin.coding.agent import CodingAgent
from patchgoblin.github.models import IssueInfo
from patchgoblin.llm.client import LLMError
from patchgoblin.models.analysis import ConfidenceLevel, ImplementationPlan, IssueAnalysis

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue() -> IssueInfo:
    from datetime import datetime

    return IssueInfo(
        number=1,
        title="Fix config validation",
        body="The config parser does not reject invalid values.",
        state="open",
        author="alice",
        labels=["bug"],
        comments=0,
        url="https://github.com/owner/repo/issues/1",
        created_at=datetime(2024, 1, 1),
        updated_at=datetime(2024, 1, 2),
    )


def _make_analysis() -> IssueAnalysis:
    return IssueAnalysis(
        summary="Fix config validation to reject invalid values",
        confidence=ConfidenceLevel.HIGH,
    )


def _make_plan() -> ImplementationPlan:
    return ImplementationPlan(
        objective="Fix config validation",
        steps=["Update validate() to raise ValueError on invalid input"],
        files_to_modify=["config.py"],
    )


def _valid_plan_json(path: str = "config.py", content: str = "# fixed\n") -> str:
    plan = {
        "summary": "Fix config validation",
        "reasoning": "Added check for invalid values",
        "files_to_modify": [path],
        "edits": [
            {
                "path": path,
                "operation": "write_file",
                "start_line": 0,
                "end_line": 0,
                "content": content,
            }
        ],
        "additional_files_needed": [],
        "concerns": [],
    }
    return json.dumps(plan)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture()
def mock_llm() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCodingAgentSuccess:
    def test_valid_plan_applies_edits(self, workspace: Path, mock_llm: MagicMock) -> None:
        mock_llm.generate.return_value = _valid_plan_json("config.py", "# patched\n")

        with patch("patchgoblin.coding.agent.GitHelper") as mock_git_cls:
            mock_git_cls.return_value.diff_stat.return_value = "config.py | 1 +"
            mock_git_cls.return_value.diff.return_value = "+# patched"

            agent = CodingAgent(
                llm=mock_llm,
                workspace_root=workspace,
                approved_files=["config.py"],
            )
            result = agent.run(_make_issue(), _make_analysis(), _make_plan())

        assert result.success is True
        assert "config.py" in result.modified_files
        assert (workspace / "config.py").read_text() == "# patched\n"

    def test_diff_stat_included_in_result(self, workspace: Path, mock_llm: MagicMock) -> None:
        mock_llm.generate.return_value = _valid_plan_json("config.py")

        with patch("patchgoblin.coding.agent.GitHelper") as mock_git_cls:
            mock_git_cls.return_value.diff_stat.return_value = "1 file changed, 1 insertion"
            mock_git_cls.return_value.diff.return_value = "+# fixed"

            agent = CodingAgent(
                llm=mock_llm,
                workspace_root=workspace,
                approved_files=["config.py"],
            )
            result = agent.run(_make_issue(), _make_analysis(), _make_plan())

        assert "1 file changed" in result.diff_stat


class TestCodingAgentMalformedOutput:
    def test_non_json_response(self, workspace: Path, mock_llm: MagicMock) -> None:
        mock_llm.generate.return_value = "Sorry, I can't do that."

        agent = CodingAgent(
            llm=mock_llm,
            workspace_root=workspace,
            approved_files=["config.py"],
        )
        result = agent.run(_make_issue(), _make_analysis(), _make_plan())
        assert result.success is False
        assert "parse" in result.error.lower() or "json" in result.error.lower()

    def test_wrong_schema_response(self, workspace: Path, mock_llm: MagicMock) -> None:
        mock_llm.generate.return_value = json.dumps({"unexpected": "fields"})

        agent = CodingAgent(
            llm=mock_llm,
            workspace_root=workspace,
            approved_files=["config.py"],
        )
        agent.run(_make_issue(), _make_analysis(), _make_plan())
        # A minimal dict may pass Pydantic (all fields have defaults) — that's fine.
        # The important thing is no crash.


class TestCodingAgentScopeViolation:
    def test_unauthorized_file_rejected(self, workspace: Path, mock_llm: MagicMock) -> None:
        mock_llm.generate.return_value = _valid_plan_json("unauthorized.py")

        agent = CodingAgent(
            llm=mock_llm,
            workspace_root=workspace,
            approved_files=["config.py"],  # unauthorized.py is NOT approved
        )
        result = agent.run(_make_issue(), _make_analysis(), _make_plan())
        assert result.success is False
        assert "approved scope" in result.error.lower() or "scope" in result.error.lower()

    def test_path_traversal_in_model_output_rejected(
        self, workspace: Path, mock_llm: MagicMock
    ) -> None:
        plan = {
            "summary": "evil",
            "reasoning": "",
            "files_to_modify": ["../../etc/passwd"],
            "edits": [
                {
                    "path": "../../etc/passwd",
                    "operation": "write_file",
                    "start_line": 0,
                    "end_line": 0,
                    "content": "root:x:0:0",
                }
            ],
            "additional_files_needed": [],
            "concerns": [],
        }
        mock_llm.generate.return_value = json.dumps(plan)

        # Even if somehow "../../etc/passwd" were in approved_files, the path
        # traversal check must still reject it.
        agent = CodingAgent(
            llm=mock_llm,
            workspace_root=workspace,
            approved_files=["../../etc/passwd"],
        )
        result = agent.run(_make_issue(), _make_analysis(), _make_plan())
        assert result.success is False


class TestCodingAgentAdditionalFilesNeeded:
    def test_stops_when_extra_files_needed(self, workspace: Path, mock_llm: MagicMock) -> None:
        response = {
            "summary": "needs more files",
            "reasoning": "",
            "files_to_modify": [],
            "edits": [],
            "additional_files_needed": ["other.py"],
            "concerns": [],
        }
        mock_llm.generate.return_value = json.dumps(response)

        agent = CodingAgent(
            llm=mock_llm,
            workspace_root=workspace,
            approved_files=["config.py"],
        )
        result = agent.run(_make_issue(), _make_analysis(), _make_plan())
        assert result.success is False
        assert "other.py" in result.error


class TestCodingAgentLLMError:
    def test_llm_error_returns_failure(self, workspace: Path, mock_llm: MagicMock) -> None:
        mock_llm.generate.side_effect = LLMError("API timeout")

        agent = CodingAgent(
            llm=mock_llm,
            workspace_root=workspace,
            approved_files=["config.py"],
        )
        result = agent.run(_make_issue(), _make_analysis(), _make_plan())
        assert result.success is False
        assert "LLM error" in result.error


class TestPromptSecurity:
    """Verify that the coding prompt contains correct security markers."""

    def test_issue_content_is_delimited(self) -> None:
        from patchgoblin.coding.prompts import build_coding_prompt

        issue = _make_issue()
        analysis = _make_analysis()
        plan = _make_plan()
        prompt = build_coding_prompt(issue, analysis, plan, ["config.py"], [])
        assert "<UNTRUSTED>" in prompt
        assert "</UNTRUSTED>" in prompt

    def test_system_prompt_mentions_untrusted(self) -> None:
        from patchgoblin.coding.prompts import CODING_SYSTEM_PROMPT

        assert "UNTRUSTED" in CODING_SYSTEM_PROMPT

    def test_system_prompt_forbids_credentials(self) -> None:
        from patchgoblin.coding.prompts import CODING_SYSTEM_PROMPT

        lower = CODING_SYSTEM_PROMPT.lower()
        assert "credentials" in lower or "api key" in lower or "token" in lower

    def test_file_contents_wrapped_in_untrusted(self) -> None:
        from patchgoblin.coding.prompts import build_coding_prompt

        issue = _make_issue()
        analysis = _make_analysis()
        plan = _make_plan()
        file_contents = [("config.py", "SECRET=mysecret\n")]
        prompt = build_coding_prompt(issue, analysis, plan, ["config.py"], file_contents)
        # The file content should be inside UNTRUSTED markers
        untrusted_section = prompt.split("<UNTRUSTED>")
        # At least one section should contain file content
        combined = "".join(untrusted_section[1:])
        assert "SECRET=mysecret" in combined
