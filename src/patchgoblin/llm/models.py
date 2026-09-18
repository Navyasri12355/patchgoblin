"""LLM domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """Configuration for an LLM provider instance."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout: float = 60.0
    max_retries: int = 2


@dataclass
class LLMResponse:
    """Raw response from the LLM provider."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)
