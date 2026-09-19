"""Sandbox models for Stage 5 isolated code execution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SandboxOperation(StrEnum):
    """Allow-listed sandbox operations."""

    INSTALL_DEPENDENCIES = "install_dependencies"
    RUN_TESTS = "run_tests"


class SandboxConfig(BaseModel):
    """Configuration for sandbox execution."""

    # Resource limits
    max_cpu_time_seconds: float = Field(default=300.0, description="Maximum CPU time in seconds.")
    max_wall_time_seconds: float = Field(
        default=600.0, description="Maximum wall-clock time in seconds."
    )
    max_memory_mb: int = Field(default=2048, description="Maximum memory in MB.")
    max_disk_mb: int = Field(default=1024, description="Maximum disk usage in MB.")
    max_processes: int = Field(default=100, description="Maximum number of processes.")

    # Network configuration
    network_enabled: bool = Field(default=False, description="Whether network access is enabled.")
    allowed_network_domains: list[str] = Field(
        default_factory=list,
        description="Domains allowed for network access (only if network_enabled=True).",
    )

    # Security
    credential_scrubbing: bool = Field(
        default=True, description="Whether to scrub credentials from environment."
    )

    @classmethod
    def with_network_for_install(cls) -> SandboxConfig:
        """Create a config with network enabled for dependency installation."""
        return cls(
            network_enabled=True,
            allowed_network_domains=["pypi.org", "files.pythonhosted.org", "registry.npmjs.org"],
        )

    @classmethod
    def isolated(cls) -> SandboxConfig:
        """Create a fully isolated config for test execution."""
        return cls(network_enabled=False)
