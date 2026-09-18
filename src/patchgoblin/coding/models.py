"""Structured models for the coding agent's inputs and outputs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EditOperation(StrEnum):
    """The type of edit to apply to a file."""

    REPLACE_LINES = "replace_lines"
    """Replace a range of lines with new content."""

    INSERT_AFTER = "insert_after"
    """Insert lines after a given line number (0 = prepend at top)."""

    WRITE_FILE = "write_file"
    """Write a complete new file (only for new files, never existing ones)."""


class FileEdit(BaseModel):
    """A single targeted edit to apply to a file inside the workspace."""

    path: str = Field(description="Relative path inside the workspace repository.")
    operation: EditOperation = Field(description="The type of edit to perform.")
    start_line: int = Field(
        default=0,
        ge=0,
        description=(
            "For replace_lines: 1-based first line to replace. "
            "For insert_after: insert after this line (0 = before line 1). "
            "For write_file: ignored."
        ),
    )
    end_line: int = Field(
        default=0,
        ge=0,
        description=(
            "For replace_lines: 1-based last line to replace (inclusive). "
            "For insert_after / write_file: ignored."
        ),
    )
    content: str = Field(
        default="",
        description="New content to insert or write.  Use an empty string to delete lines.",
    )


class CodeChangePlan(BaseModel):
    """Structured edit plan produced by the LLM coding agent."""

    summary: str = Field(description="One-sentence description of the planned change.")
    reasoning: str = Field(
        default="",
        description="Explanation of why these edits implement the approved plan.",
    )
    files_to_modify: list[str] = Field(
        default_factory=list,
        description="Relative paths of files the agent intends to edit.",
    )
    edits: list[FileEdit] = Field(
        default_factory=list,
        description="Ordered list of targeted edits to apply.",
    )
    additional_files_needed: list[str] = Field(
        default_factory=list,
        description=(
            "Files outside the approved scope that would be needed. "
            "Non-empty means the agent is requesting scope expansion."
        ),
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Risks or issues the agent identified while planning.",
    )


class ChangeResult(BaseModel):
    """Result returned after the coding agent has applied its changes."""

    success: bool = Field(description="Whether the edit loop completed without fatal errors.")
    modified_files: list[str] = Field(
        default_factory=list,
        description="Relative paths of files that were actually written.",
    )
    diff_stat: str = Field(
        default="",
        description="Output of ``git diff --stat``.",
    )
    diff: str = Field(
        default="",
        description="Full ``git diff`` output.",
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of what was changed.",
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Risks or issues encountered during editing.",
    )
    error: str = Field(
        default="",
        description="Error message if ``success`` is False.",
    )
