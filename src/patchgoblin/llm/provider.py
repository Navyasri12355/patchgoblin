"""LLM provider abstraction for PatchGoblin."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol that every LLM provider must satisfy.

    The application depends only on this interface, keeping provider-specific
    details inside ``patchgoblin.llm.client``.
    """

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Generate a completion for *prompt*.

        Parameters
        ----------
        prompt:
            The user-facing part of the prompt (untrusted content must be
            clearly delimited **before** being passed here).
        system:
            Optional system-level instruction that the provider should treat
            with higher authority than the user prompt.

        Returns
        -------
        str
            The model's text response.
        """
        ...
