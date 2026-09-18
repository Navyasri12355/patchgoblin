"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os


class Config:
    """Central configuration for PatchGoblin."""

    # --- GitHub -----------------------------------------------------------
    GITHUB_API_URL: str = os.environ.get("GITHUB_API_URL", "https://api.github.com")

    @staticmethod
    def github_token() -> str | None:
        """Return the GitHub token from the environment, or None if not set."""
        return os.environ.get("GITHUB_TOKEN")

    # --- LLM --------------------------------------------------------------

    @staticmethod
    def llm_api_key() -> str | None:
        """Return the LLM API key, or None if not set."""
        return os.environ.get("LLM_API_KEY")

    @staticmethod
    def llm_base_url() -> str:
        """Return the LLM base URL (defaults to OpenAI)."""
        return os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")

    @staticmethod
    def llm_model() -> str:
        """Return the LLM model name (defaults to gpt-4o-mini)."""
        return os.environ.get("LLM_MODEL", "gpt-4o-mini")
