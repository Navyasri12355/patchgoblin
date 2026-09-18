"""Tests for the OpenAI-compatible LLM client."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from patchgoblin.llm.client import (
    LLMAuthError,
    LLMContextLengthError,
    LLMNetworkError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
    OpenAICompatibleClient,
)
from patchgoblin.llm.models import LLMConfig

BASE_URL = "https://api.test-llm.example"
MODEL = "test-model"


def _make_client() -> OpenAICompatibleClient:
    cfg = LLMConfig(api_key="sk-test", base_url=BASE_URL, model=MODEL)
    return OpenAICompatibleClient(cfg)


def _ok_response(content: str = "Hello, world!") -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "model": MODEL,
        "usage": {},
    }


@respx.mock
def test_generate_success():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok_response("analysis result"))
    )
    client = _make_client()
    result = client.generate("analyze this")
    assert result == "analysis result"


@respx.mock
def test_generate_with_system_prompt():
    route = respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json=_ok_response("ok"))
    )
    client = _make_client()
    client.generate("user prompt", system="system instruction")
    request_body = json.loads(route.calls[0].request.content)
    messages = request_body["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "system instruction"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "user prompt"


@respx.mock
def test_generate_auth_failure():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    client = _make_client()
    with pytest.raises(LLMAuthError, match="invalid or missing"):
        client.generate("test")


@respx.mock
def test_generate_rate_limit():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )
    client = _make_client()
    with pytest.raises(LLMRateLimitError):
        client.generate("test")


@respx.mock
def test_generate_context_length_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "context length exceeded"}},
        )
    )
    client = _make_client()
    with pytest.raises(LLMContextLengthError):
        client.generate("test")


@respx.mock
def test_generate_malformed_response():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(200, json={"unexpected": "structure"})
    )
    client = _make_client()
    with pytest.raises(LLMResponseError, match="unexpected response structure"):
        client.generate("test")


@respx.mock
def test_generate_network_error():
    respx.post(f"{BASE_URL}/chat/completions").mock(
        side_effect=httpx.NetworkError("connection refused")
    )
    client = _make_client()
    with pytest.raises(LLMNetworkError):
        client.generate("test")


@respx.mock
def test_generate_timeout():
    respx.post(f"{BASE_URL}/chat/completions").mock(side_effect=httpx.TimeoutException("timed out"))
    client = _make_client()
    with pytest.raises(LLMTimeoutError):
        client.generate("test")


def test_repr_does_not_expose_key():
    client = _make_client()
    r = repr(client)
    assert "sk-test" not in r


def test_api_key_not_in_repr_or_str():
    cfg = LLMConfig(api_key="super-secret-key-xyz", base_url=BASE_URL, model=MODEL)
    client = OpenAICompatibleClient(cfg)
    assert "super-secret-key-xyz" not in repr(client)
    assert "super-secret-key-xyz" not in str(client)
