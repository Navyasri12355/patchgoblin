"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os


class Config:
    """Central configuration for PatchGoblin."""

    GITHUB_API_URL: str = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    @staticmethod
    def github_token() -> str | None:
        """Return the GitHub token from the environment, or None if not set."""
        return os.environ.get("GITHUB_TOKEN")
