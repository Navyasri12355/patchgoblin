"""Coding agent — orchestrates LLM-driven file modification.

The agent uses a bounded loop:
  1. Read approved files
  2. Build prompt
  3. Call LLM → parse CodeChangePlan
  4. Validate plan (scope, paths)
  5. Apply edits
  6. Inspect diff and decide completeness

The loop is capped at MAX_EDIT_ITERATIONS to prevent runaway operation.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from patchgoblin.coding.context import ContextBuilder
from patchgoblin.coding.editor import EditError, FileEditor
from patchgoblin.coding.models import ChangeResult, CodeChangePlan
from patchgoblin.coding.prompts import CODING_SYSTEM_PROMPT, build_coding_prompt
from patchgoblin.github.models import IssueInfo
from patchgoblin.llm.client import LLMError, LLMResponseError
from patchgoblin.llm.provider import LLMProvider
from patchgoblin.models.analysis import ImplementationPlan, IssueAnalysis
from patchgoblin.repository.git import GitHelper

MAX_EDIT_ITERATIONS = 3


class CodingAgentError(Exception):
    """Raised when the coding agent cannot complete its task."""


class CodingAgent:
    """Repository-aware coding agent.

    Parameters
    ----------
    llm:
        The LLM provider to use for generating edit plans.
    workspace_root:
        Absolute path to the cloned repository inside the workspace.
    approved_files:
        Relative paths of files the human approved for modification.
    """

    def __init__(
        self,
        llm: LLMProvider,
        workspace_root: Path,
        approved_files: list[str],
    ) -> None:
        self._llm = llm
        self._root = workspace_root
        self._approved_files = approved_files
        self._context = ContextBuilder(workspace_root)
        self._editor = FileEditor(workspace_root, approved_files)
        self._git = GitHelper(workspace_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        issue: IssueInfo,
        analysis: IssueAnalysis,
        plan: ImplementationPlan,
    ) -> ChangeResult:
        """Execute the modification loop and return a :class:`ChangeResult`.

        The loop is bounded to ``MAX_EDIT_ITERATIONS``.  If the agent needs
        files outside the approved scope it stops and reports that.
        """
        modified_files: list[str] = []
        concerns: list[str] = []

        for iteration in range(MAX_EDIT_ITERATIONS):
            # Read current state of approved files
            file_contents = self._context.read_files(self._approved_files)

            # Build and send prompt
            prompt = build_coding_prompt(
                issue=issue,
                analysis=analysis,
                plan=plan,
                approved_files=self._approved_files,
                file_contents=file_contents,
            )

            try:
                raw = self._llm.generate(prompt, system=CODING_SYSTEM_PROMPT)
            except LLMError as exc:
                return ChangeResult(
                    success=False,
                    modified_files=modified_files,
                    error=f"LLM error on iteration {iteration + 1}: {exc}",
                )

            # Parse response
            try:
                change_plan = self._parse_plan(raw)
            except LLMResponseError as exc:
                return ChangeResult(
                    success=False,
                    modified_files=modified_files,
                    error=f"Could not parse LLM response on iteration {iteration + 1}: {exc}",
                )

            # Stop if model wants files outside approved scope
            if change_plan.additional_files_needed:
                return ChangeResult(
                    success=False,
                    modified_files=modified_files,
                    error=(
                        "The coding agent requires additional files outside the approved scope:\n"
                        + "\n".join(f"  - {f}" for f in change_plan.additional_files_needed)
                        + "\n\nPlease approve these files and retry."
                    ),
                    concerns=change_plan.concerns,
                )

            if change_plan.concerns:
                concerns.extend(change_plan.concerns)

            # Apply edits
            try:
                newly_modified = self._editor.apply_all(change_plan.edits)
            except EditError as exc:
                return ChangeResult(
                    success=False,
                    modified_files=modified_files,
                    error=f"Edit error on iteration {iteration + 1}: {exc}",
                    concerns=concerns,
                )

            modified_files.extend(f for f in newly_modified if f not in modified_files)

            # If no edits, we're done (model indicated nothing else to do)
            if not change_plan.edits:
                break

        # Generate diff
        diff_stat = self._git.diff_stat()
        diff = self._git.diff()

        return ChangeResult(
            success=True,
            modified_files=modified_files,
            diff_stat=diff_stat,
            diff=diff,
            summary=change_plan.summary if "change_plan" in dir() else "",
            concerns=concerns,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_plan(raw: str) -> CodeChangePlan:
        """Parse and validate the LLM JSON response as a :class:`CodeChangePlan`."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                f"LLM returned non-JSON response: {exc}\n\nRaw:\n{raw[:500]}"
            ) from exc

        try:
            return CodeChangePlan.model_validate(data)
        except ValidationError as exc:
            msg = f"LLM response did not match CodeChangePlan schema: {exc}"
            raise LLMResponseError(msg) from exc
