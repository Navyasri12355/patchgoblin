"""Sandbox runner for isolated code execution."""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from patchgoblin.sandbox.limits import ResourceLimiter, ResourceLimitError, ResourceUsage
from patchgoblin.sandbox.models import SandboxConfig, SandboxOperation
from patchgoblin.sandbox.safety import CredentialScrubber, PathValidator


class SandboxError(Exception):
    """Raised when sandbox execution fails."""


class SandboxBackend(StrEnum):
    """Available sandbox backends."""

    SUBPROCESS = "subprocess"
    # Docker could be added here in the future


@dataclass
class SandboxResult:
    """Result of a sandbox execution."""

    operation: SandboxOperation
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    resource_usage: ResourceUsage
    truncated: bool = False
    truncation_reason: str | None = None


class SandboxRunner:
    """Executes allow-listed operations in an isolated environment."""

    # Maximum output size before truncation
    MAX_OUTPUT_SIZE = 1024 * 1024  # 1MB

    def __init__(self, workspace_path: Path, backend: SandboxBackend = SandboxBackend.SUBPROCESS):
        """Initialize the sandbox runner.

        Args:
            workspace_path: Path to the workspace directory (must exist).
            backend: Sandbox backend to use.
        """
        self._workspace_path = Path(workspace_path).resolve()
        self._backend = backend
        self._path_validator = PathValidator(self._workspace_path)

        if not self._workspace_path.exists():
            raise SandboxError(f"Workspace path does not exist: {self._workspace_path}")

    def run(
        self,
        operation: SandboxOperation,
        config: SandboxConfig,
        language: str = "python",
    ) -> SandboxResult:
        """Run an allow-listed operation in the sandbox.

        Args:
            operation: The operation to run.
            config: Sandbox configuration (resource limits, network, etc.).
            language: Programming language (for language-specific commands).

        Returns:
            SandboxResult with execution details.

        Raises:
            SandboxError: If the operation fails or is not allowed.
        """
        # Validate operation is in allow-list
        if operation not in SandboxOperation:
            raise SandboxError(f"Operation {operation} is not in the allow-list")

        # Get the command for this operation
        command = self._get_command(operation, language)
        if not command:
            raise SandboxError(f"No command configured for {operation} with language {language}")

        # Prepare environment (scrub credentials)
        env = CredentialScrubber.scrub_environment() if config.credential_scrubbing else None

        # Set up resource limiter
        limiter = ResourceLimiter(config)
        limiter.start_timing()

        try:
            # Execute the command
            result = self._execute_command(command, operation, config, env, limiter)
        except ResourceLimitError as exc:
            # Record that we were killed by a limit
            usage = limiter.get_usage(self._workspace_path)
            usage.killed_by_limit = True
            usage.limit_reason = str(exc)

            result = SandboxResult(
                operation=operation,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                duration_seconds=usage.wall_time_seconds,
                resource_usage=usage,
                truncated=False,
            )
        except Exception as exc:
            raise SandboxError(f"Sandbox execution failed: {exc}") from exc

        return result

    def _get_command(self, operation: SandboxOperation, language: str) -> list[str] | None:
        """Get the command for an operation based on language."""
        # Language detection and command mapping
        language_commands = {
            "python": {
                SandboxOperation.INSTALL_DEPENDENCIES: ["uv", "sync"],
                SandboxOperation.RUN_TESTS: ["uv", "run", "pytest"],
            },
            "node": {
                SandboxOperation.INSTALL_DEPENDENCIES: ["npm", "ci", "--ignore-scripts"],
                SandboxOperation.RUN_TESTS: ["npm", "test"],
            },
        }

        return language_commands.get(language, {}).get(operation)

    def _execute_command(
        self,
        command: list[str],
        operation: SandboxOperation,
        config: SandboxConfig,
        env: dict[str, str] | None,
        limiter: ResourceLimiter,
    ) -> SandboxResult:
        """Execute a command with resource limits."""

        # Create a thread to monitor resource limits
        stop_event = threading.Event()
        limit_error: ResourceLimitError | None = None

        def monitor_limits():
            """Monitor resource limits in a background thread."""
            while not stop_event.is_set():
                try:
                    usage = limiter.get_usage(self._workspace_path)
                    limiter.check_limits(usage)
                    time.sleep(0.1)  # Check every 100ms
                except ResourceLimitError as exc:
                    nonlocal limit_error
                    limit_error = exc
                    stop_event.set()
                    break

        monitor_thread = threading.Thread(target=monitor_limits, daemon=True)
        monitor_thread.start()

        try:
            # Run the command
            process = subprocess.Popen(
                command,
                cwd=self._workspace_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()

            # Truncate output if too large
            truncated = False
            truncation_reason = None
            if len(stdout) > self.MAX_OUTPUT_SIZE:
                stdout = stdout[: self.MAX_OUTPUT_SIZE]
                truncated = True
                truncation_reason = "stdout truncated"
            if len(stderr) > self.MAX_OUTPUT_SIZE:
                stderr = stderr[: self.MAX_OUTPUT_SIZE]
                truncated = True
                truncation_reason = "stderr truncated"

            # Get final resource usage
            usage = limiter.get_usage(self._workspace_path)

            # If we hit a limit during execution
            if limit_error:
                usage.killed_by_limit = True
                usage.limit_reason = str(limit_error)
                process.kill()
                stdout, stderr = process.communicate()

            duration = time.time() - (limiter._start_time or time.time())
            return SandboxResult(
                operation=operation,
                exit_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                resource_usage=usage,
                truncated=truncated,
                truncation_reason=truncation_reason,
            )

        finally:
            stop_event.set()
            monitor_thread.join(timeout=1.0)
