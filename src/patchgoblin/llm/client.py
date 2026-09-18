"""OpenAI-compatible LLM client.

This is the only module that issues HTTP requests to an LLM provider.
The rest of the application depends on the ``LLMProvider`` protocol in
``patchgoblin.llm.provider``.
"""

from __future__ import annotations

import json

import httpx

from patchgoblin.llm.models import LLMConfig

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base class for LLM-related errors."""


class LLMAuthError(LLMError):
    """Invalid or missing API key."""


class LLMRateLimitError(LLMError):
    """Rate limit exceeded."""


class LLMContextLengthError(LLMError):
    """Prompt exceeds the model's context window."""


class LLMResponseError(LLMError):
    """Provider returned a malformed or unparseable response."""


class LLMTimeoutError(LLMError):
    """Request to the LLM provider timed out."""


class LLMNetworkError(LLMError):
    """Network failure reaching the LLM provider."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OpenAICompatibleClient:
    """Thin HTTP client for any OpenAI-compatible chat-completion endpoint.

    Works with:
    - OpenAI (https://api.openai.com/v1)
    - Local Ollama endpoint (http://localhost:11434/v1)
    - Any other OpenAI-compatible proxy
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config
        # Never expose the key in repr / str
        self._client = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout,
        )

    # ------------------------------------------------------------------
    # LLMProvider protocol implementation
    # ------------------------------------------------------------------

    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Send *prompt* to the configured model and return the response text."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._config.model,
            "messages": messages,
        }

        raw = self._post("/chat/completions", payload)
        return self._extract_content(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = self._client.post(path, content=json.dumps(payload))
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Request to LLM provider timed out after {self._config.timeout}s."
            ) from exc
        except httpx.NetworkError as exc:
            raise LLMNetworkError(f"Network error reaching LLM provider: {exc}") from exc

        if response.status_code == 401:
            raise LLMAuthError(
                "LLM API key is invalid or missing. Set LLM_API_KEY in your environment."
            )
        if response.status_code == 429:
            raise LLMRateLimitError("LLM provider rate limit exceeded. Try again later.")
        if response.status_code == 400:
            body = self._safe_json(response)
            msg = body.get("error", {}).get("message", response.text) if body else response.text
            if "context" in str(msg).lower() or "length" in str(msg).lower():
                raise LLMContextLengthError(f"Prompt exceeds model context length: {msg}")
            raise LLMResponseError(f"LLM provider returned 400: {msg}")
        if not response.is_success:
            raise LLMError(
                f"LLM provider returned unexpected status {response.status_code}: {response.text}"
            )

        body = self._safe_json(response)
        if body is None:
            raise LLMResponseError("LLM provider returned non-JSON response.")
        return body

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict | None:
        try:
            return response.json()
        except Exception:
            return None

    @staticmethod
    def _extract_content(body: dict) -> str:
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                f"LLM provider returned an unexpected response structure: {body}"
            ) from exc

    # ------------------------------------------------------------------
    # Model property for inspection
    # ------------------------------------------------------------------

    @property
    def model(self) -> str:
        """Name of the configured model."""
        return self._config.model

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> OpenAICompatibleClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def __repr__(self) -> str:
        # Intentionally omit api_key
        return (
            f"OpenAICompatibleClient(model={self._config.model!r},"
            f" base_url={self._config.base_url!r})"
        )
