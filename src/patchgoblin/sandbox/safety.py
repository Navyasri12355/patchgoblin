"""Safety utilities for sandbox execution."""

from __future__ import annotations

import os
from pathlib import Path


class CredentialScrubber:
    """Removes credentials from environment variables."""

    # Credentials that must never be accessible in the sandbox
    FORBIDDEN_VARS = {
        "GITHUB_TOKEN",
        "LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "GCP_CREDENTIALS",
        "TOKEN",
        "API_KEY",
        "SECRET",
        "PASSWORD",
    }

    @classmethod
    def scrub_environment(cls, original_env: dict[str, str] | None = None) -> dict[str, str]:
        """Return a copy of the environment with credentials removed."""
        if original_env is None:
            original_env = dict(os.environ)

        safe_env = {}
        for key, value in original_env.items():
            # Remove any variable that contains credential-related keywords
            if cls._is_credential_variable(key):
                continue
            safe_env[key] = value

        return safe_env

    @classmethod
    def _is_credential_variable(cls, var_name: str) -> bool:
        """Check if a variable name might contain credentials."""
        var_upper = var_name.upper()
        for forbidden in cls.FORBIDDEN_VARS:
            if forbidden in var_upper:
                return True
        return False


class PathValidator:
    """Validates that paths are within the allowed workspace."""

    def __init__(self, workspace_root: Path):
        """Initialize with the allowed workspace root."""
        self._workspace_root = workspace_root.resolve()

    def is_allowed(self, path: Path) -> bool:
        """Check if a path is within the workspace."""
        try:
            resolved = path.resolve()
            resolved.relative_to(self._workspace_root)
            return True
        except ValueError:
            return False

    def validate(self, path: Path) -> Path:
        """Validate a path and raise an error if not allowed."""
        if not self.is_allowed(path):
            raise ValueError(f"Path {path} is outside the allowed workspace {self._workspace_root}")
        return path.resolve()
