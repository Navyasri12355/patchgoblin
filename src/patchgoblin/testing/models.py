"""Testing models for Stage 5 test execution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TestingLanguage(StrEnum):
    """Supported programming languages for testing."""

    PYTHON = "python"
    NODE = "node"
    UNKNOWN = "unknown"


class TestRunResult(BaseModel):
    """Result of a sandboxed test run."""

    task_id: str = Field(description="Task ID for this test run.")
    command: str = Field(description="Command that was executed.")
    exit_code: int = Field(description="Exit code from the test command.")
    passed: bool = Field(description="Whether tests passed (exit code 0).")
    duration_seconds: float = Field(description="Wall-clock duration in seconds.")
    truncated_output: str = Field(description="Truncated stdout/stderr output.")
    killed_by_limit: bool = Field(
        default=False, description="Whether run was killed by a resource limit."
    )
    limit_reason: str | None = Field(default=None, description="Reason if killed by limit.")
    language: TestingLanguage = Field(
        default=TestingLanguage.UNKNOWN, description="Detected language."
    )
    test_count: int | None = Field(default=None, description="Number of tests run (if parsed).")
    failure_count: int | None = Field(
        default=None, description="Number of test failures (if parsed)."
    )
    error_count: int | None = Field(default=None, description="Number of test errors (if parsed).")

    @property
    def success(self) -> bool:
        """Whether the test run was successful (passed and not killed)."""
        return self.passed and not self.killed_by_limit
