"""Test executor for sandboxed test execution."""

from __future__ import annotations

from pathlib import Path

from patchgoblin.sandbox.models import SandboxConfig, SandboxOperation
from patchgoblin.sandbox.runner import SandboxError, SandboxRunner
from patchgoblin.testing.detector import DetectorError, LanguageDetector
from patchgoblin.testing.models import TestingLanguage, TestRunResult
from patchgoblin.testing.parser import TestParser


class TestExecutionError(Exception):
    """Raised when test execution fails."""


class TestExecutor:
    """Executes tests in a sandboxed environment."""

    def __init__(self, workspace_path: Path):
        """Initialize with the workspace path."""
        self._workspace_path = Path(workspace_path).resolve()
        self._detector = LanguageDetector(self._workspace_path)
        self._parser = TestParser()

    def execute(self, task_id: str, skip_install: bool = False) -> TestRunResult:
        """Execute tests in the sandbox.

        Args:
            task_id: Task ID for this execution.
            skip_install: If True, skip dependency installation.

        Returns:
            TestRunResult with execution details.

        Raises:
            TestExecutionError: If execution fails.
        """
        # Detect language
        try:
            language = self._detector.detect()
        except DetectorError as exc:
            raise TestExecutionError(f"Language detection failed: {exc}") from exc

        if language == TestingLanguage.UNKNOWN:
            raise TestExecutionError(
                "Unsupported language/tooling. "
                "Sandboxed testing is only supported for Python and Node.js repositories."
            )

        # Create sandbox runner
        runner = SandboxRunner(self._workspace_path)

        # Install dependencies (if not skipped)
        if not skip_install:
            install_config = SandboxConfig.with_network_for_install()
            try:
                install_result = runner.run(
                    SandboxOperation.INSTALL_DEPENDENCIES,
                    install_config,
                    language=language.value,
                )
                if install_result.exit_code != 0:
                    raise TestExecutionError(
                        f"Dependency installation failed with exit code "
                        f"{install_result.exit_code}: {install_result.stderr}"
                    )
            except SandboxError as exc:
                raise TestExecutionError(f"Dependency installation failed: {exc}") from exc

        # Run tests
        test_config = SandboxConfig.isolated()
        try:
            test_result = runner.run(
                SandboxOperation.RUN_TESTS,
                test_config,
                language=language.value,
            )
        except SandboxError as exc:
            raise TestExecutionError(f"Test execution failed: {exc}") from exc

        # Parse test output
        combined_output = f"{test_result.stdout}\n{test_result.stderr}"
        parsed = self._parser.parse(combined_output, language)

        # Build result
        command_str = f"test ({language.value})"
        return TestRunResult(
            task_id=task_id,
            command=command_str,
            exit_code=test_result.exit_code,
            passed=test_result.exit_code == 0,
            duration_seconds=test_result.duration_seconds,
            truncated_output=combined_output[:10000],  # Limit to 10KB
            killed_by_limit=test_result.resource_usage.killed_by_limit,
            limit_reason=test_result.resource_usage.limit_reason,
            language=language,
            test_count=parsed.get("test_count"),
            failure_count=parsed.get("failure_count"),
            error_count=parsed.get("error_count"),
        )
