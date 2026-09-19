"""Tests for sandbox module (Stage 5)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from patchgoblin.sandbox.limits import ResourceLimiter, ResourceLimitError, ResourceUsage
from patchgoblin.sandbox.models import SandboxConfig, SandboxOperation
from patchgoblin.sandbox.runner import SandboxError, SandboxRunner
from patchgoblin.sandbox.safety import CredentialScrubber, PathValidator


class TestSandboxConfig:
    """Test SandboxConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SandboxConfig()
        assert config.max_cpu_time_seconds == 300.0
        assert config.max_wall_time_seconds == 600.0
        assert config.max_memory_mb == 2048
        assert config.network_enabled is False
        assert config.credential_scrubbing is True

    def test_with_network_for_install(self):
        """Test network-enabled config for dependency installation."""
        config = SandboxConfig.with_network_for_install()
        assert config.network_enabled is True
        assert "pypi.org" in config.allowed_network_domains
        assert "registry.npmjs.org" in config.allowed_network_domains

    def test_isolated_config(self):
        """Test isolated config for test execution."""
        config = SandboxConfig.isolated()
        assert config.network_enabled is False
        assert config.allowed_network_domains == []


class TestResourceLimiter:
    """Test ResourceLimiter."""

    def test_start_timing(self):
        """Test that timing starts correctly."""
        config = SandboxConfig()
        limiter = ResourceLimiter(config)
        limiter.start_timing()
        assert limiter._start_time is not None
        assert limiter._process_start_time is not None

    def test_check_limits_cpu_time(self):
        """Test CPU time limit check."""
        config = SandboxConfig(max_cpu_time_seconds=1.0)
        limiter = ResourceLimiter(config)

        usage = ResourceUsage(
            cpu_time_seconds=2.0,
            wall_time_seconds=1.0,
            memory_mb=100,
            disk_mb=100,
            process_count=1,
        )

        with pytest.raises(ResourceLimitError, match="CPU time limit exceeded"):
            limiter.check_limits(usage)

    def test_check_limits_memory(self):
        """Test memory limit check."""
        config = SandboxConfig(max_memory_mb=100)
        limiter = ResourceLimiter(config)

        usage = ResourceUsage(
            cpu_time_seconds=1.0,
            wall_time_seconds=1.0,
            memory_mb=200,
            disk_mb=100,
            process_count=1,
        )

        with pytest.raises(ResourceLimitError, match="Memory limit exceeded"):
            limiter.check_limits(usage)


class TestCredentialScrubber:
    """Test CredentialScrubber."""

    def test_scrub_environment_removes_github_token(self):
        """Test that GITHUB_TOKEN is removed."""
        env = {"GITHUB_TOKEN": "secret", "SAFE_VAR": "value"}
        scrubbed = CredentialScrubber.scrub_environment(env)
        assert "GITHUB_TOKEN" not in scrubbed
        assert "SAFE_VAR" in scrubbed
        assert scrubbed["SAFE_VAR"] == "value"

    def test_scrub_environment_removes_llm_api_key(self):
        """Test that LLM_API_KEY is removed."""
        env = {"LLM_API_KEY": "secret", "SAFE_VAR": "value"}
        scrubbed = CredentialScrubber.scrub_environment(env)
        assert "LLM_API_KEY" not in scrubbed
        assert "SAFE_VAR" in scrubbed

    def test_scrub_environment_removes_all_credentials(self):
        """Test that all credential variables are removed."""
        env = {
            "GITHUB_TOKEN": "secret1",
            "LLM_API_KEY": "secret2",
            "OPENAI_API_KEY": "secret3",
            "SAFE_VAR": "value",
        }
        scrubbed = CredentialScrubber.scrub_environment(env)
        assert "GITHUB_TOKEN" not in scrubbed
        assert "LLM_API_KEY" not in scrubbed
        assert "OPENAI_API_KEY" not in scrubbed
        assert "SAFE_VAR" in scrubbed


class TestPathValidator:
    """Test PathValidator."""

    def test_is_allowed_valid_path(self, tmp_path):
        """Test that valid paths within workspace are allowed."""
        validator = PathValidator(tmp_path)
        assert validator.is_allowed(tmp_path / "subdir" / "file.txt")

    def test_is_allowed_invalid_path(self, tmp_path):
        """Test that paths outside workspace are not allowed."""
        validator = PathValidator(tmp_path)
        other_path = tmp_path.parent / "other"
        assert not validator.is_allowed(other_path)

    def test_validate_valid_path(self, tmp_path):
        """Test validation of valid path."""
        validator = PathValidator(tmp_path)
        result = validator.validate(tmp_path / "file.txt")
        assert result == (tmp_path / "file.txt").resolve()

    def test_validate_invalid_path(self, tmp_path):
        """Test validation of invalid path raises error."""
        validator = PathValidator(tmp_path)
        other_path = tmp_path.parent / "other"
        with pytest.raises(ValueError, match="outside the allowed workspace"):
            validator.validate(other_path)


class TestSandboxRunner:
    """Test SandboxRunner."""

    def test_init_requires_existing_workspace(self):
        """Test that workspace must exist."""
        with pytest.raises(SandboxError, match="Workspace path does not exist"):
            SandboxRunner(Path("/nonexistent/path"))

    @patch("patchgoblin.sandbox.runner.subprocess.Popen")
    def test_run_install_dependencies_python(self, mock_popen, tmp_path):
        """Test running install dependencies for Python."""
        # Setup
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process

        runner = SandboxRunner(tmp_path)
        config = SandboxConfig.with_network_for_install()

        # Execute
        result = runner.run(SandboxOperation.INSTALL_DEPENDENCIES, config, "python")

        # Verify
        assert result.exit_code == 0
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["uv", "sync"]

    @patch("patchgoblin.sandbox.runner.subprocess.Popen")
    def test_run_tests_python(self, mock_popen, tmp_path):
        """Test running tests for Python."""
        # Setup
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process

        runner = SandboxRunner(tmp_path)
        config = SandboxConfig.isolated()

        # Execute
        result = runner.run(SandboxOperation.RUN_TESTS, config, "python")

        # Verify
        assert result.exit_code == 0
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == ["uv", "run", "pytest"]

    def test_run_invalid_operation(self, tmp_path):
        """Test that invalid operations are rejected."""
        runner = SandboxRunner(tmp_path)
        config = SandboxConfig.isolated()

        with pytest.raises(SandboxError, match="not in the allow-list"):
            runner.run("invalid_operation", config, "python")

    def test_unsupported_language(self, tmp_path):
        """Test that unsupported languages are rejected."""
        runner = SandboxRunner(tmp_path)
        config = SandboxConfig.isolated()

        with pytest.raises(SandboxError, match="No command configured"):
            runner.run(SandboxOperation.RUN_TESTS, config, "ruby")
