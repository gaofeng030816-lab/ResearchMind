"""Tests for the OpenAI-compatible provider without network access."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from openai import APIError, APITimeoutError
import pytest

from researchmind.llm import (
    ChatMessage,
    LlmApiError,
    LlmBadResponseError,
    LlmConfigurationError,
)
from researchmind.llm.providers import (
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    OpenAiCompatibleProvider,
    parse_response,
)
import researchmind.llm.providers.openai_compatible as provider_module


def test_complete_serializes_messages_and_forwards_safe_options() -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> object:
        captured.update(kwargs)
        return _response("  Grounded explanation.  ")

    provider = _provider(fake_create)
    messages = [
        ChatMessage(role="system", content="System instructions"),
        ChatMessage(role="user", content="Research question"),
    ]

    result = provider.complete(messages, temperature=0.2, max_tokens=300)

    assert result == "Grounded explanation."
    assert captured == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "System instructions"},
            {"role": "user", "content": "Research question"},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }


@pytest.mark.parametrize(
    "response",
    (
        SimpleNamespace(choices=[]),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="   "))]
        ),
        object(),
    ),
)
def test_parse_response_rejects_empty_or_malformed_responses(response: object) -> None:
    with pytest.raises(LlmBadResponseError):
        parse_response(response)


def test_timeout_is_mapped_without_provider_details() -> None:
    def timeout(**_: object) -> object:
        raise APITimeoutError(request=cast(Any, object()))

    provider = _provider(timeout)

    with pytest.raises(LlmApiError, match="timed out") as error:
        provider.complete([ChatMessage(role="user", content="question")])

    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


def test_api_error_does_not_expose_request_body_or_secret() -> None:
    secret = "sk-test-sensitive-value"

    def api_failure(**_: object) -> object:
        raise APIError(
            "provider failure containing internal details",
            request=cast(Any, object()),
            body={"api_key": secret, "paper": "sensitive paper text"},
        )

    provider = _provider(api_failure)

    with pytest.raises(LlmApiError) as error:
        provider.complete([ChatMessage(role="user", content="question")])

    public_error = str(error.value)
    assert secret not in public_error
    assert "sensitive paper text" not in public_error
    assert "provider failure" not in public_error
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "unsafe_options",
    (
        {"tools": []},
        {"tool_choice": "auto"},
        {"functions": []},
        {"web_search_options": {}},
        {"stream": True},
    ),
)
def test_complete_rejects_options_that_add_authority_or_change_response_shape(
    unsafe_options: dict[str, object],
) -> None:
    called = False

    def fake_create(**_: object) -> object:
        nonlocal called
        called = True
        return _response("unused")

    provider = _provider(fake_create)

    with pytest.raises(LlmConfigurationError, match="Unsupported"):
        provider.complete(
            [ChatMessage(role="user", content="question")],
            **unsafe_options,
        )

    assert called is False


def test_complete_rejects_empty_message_list() -> None:
    provider = _provider(lambda **_: _response("unused"))

    with pytest.raises(LlmConfigurationError, match="At least one"):
        provider.complete([])


def test_provider_constructs_sdk_client_with_timeout_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        @staticmethod
        def create(**_: object) -> object:
            return _response("response")

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    def fake_openai(**kwargs: object) -> object:
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(provider_module, "OpenAI", fake_openai)

    provider = OpenAiCompatibleProvider(
        api_key="test-secret",
        model="test-model",
        base_url="http://localhost:11434/v1",
    )

    assert provider.complete([ChatMessage(role="user", content="question")]) == "response"
    assert captured == {
        "api_key": "test-secret",
        "base_url": "http://localhost:11434/v1",
        "timeout": DEFAULT_LLM_TIMEOUT_SECONDS,
        "max_retries": DEFAULT_LLM_MAX_RETRIES,
    }
    assert "test-secret" not in repr(provider)


def test_provider_maps_custom_api_key_header_to_sdk_default_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    http_client_arguments: dict[str, object] = {}

    class FakeCompletions:
        @staticmethod
        def create(**_: object) -> object:
            return _response("dots response")

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )

    def fake_openai(**kwargs: object) -> object:
        captured.update(kwargs)
        return fake_client

    fake_http_client = object()

    def fake_default_httpx_client(**kwargs: object) -> object:
        http_client_arguments.update(kwargs)
        return fake_http_client

    monkeypatch.setattr(provider_module, "OpenAI", fake_openai)
    monkeypatch.setattr(
        provider_module,
        "DefaultHttpxClient",
        fake_default_httpx_client,
    )

    provider = OpenAiCompatibleProvider(
        api_key="test-secret",
        api_key_header="api-key",
        model="dots3-note-prev",
        base_url="https://note3-prev-api.askdiandian.com/v1",
    )

    assert provider.complete([ChatMessage(role="user", content="question")]) == "dots response"
    assert captured == {
        "api_key": "custom-header-auth",
        "base_url": "https://note3-prev-api.askdiandian.com/v1",
        "timeout": DEFAULT_LLM_TIMEOUT_SECONDS,
        "max_retries": DEFAULT_LLM_MAX_RETRIES,
        "http_client": fake_http_client,
    }
    event_hooks = cast(Any, http_client_arguments["event_hooks"])
    request = SimpleNamespace(
        headers={
            "Authorization": "Bearer custom-header-auth",
            "Content-Type": "application/json",
        }
    )
    event_hooks["request"][0](request)
    assert request.headers == {
        "Content-Type": "application/json",
        "api-key": "test-secret",
    }
    assert "test-secret" not in repr(provider)


@pytest.mark.parametrize(
    "overrides",
    (
        {"api_key": ""},
        {"api_key_header": "X-Unsupported-Key"},
        {"model": ""},
        {"base_url": ""},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("inf")},
        {"max_retries": -1},
        {"max_retries": True},
    ),
)
def test_provider_rejects_invalid_configuration(
    overrides: dict[str, object],
) -> None:
    arguments: dict[str, object] = {
        "api_key": "test-key",
        "model": "test-model",
        "base_url": "https://example.invalid/v1",
        "completion_create": lambda **_: _response("unused"),
    }
    arguments.update(overrides)

    with pytest.raises(LlmConfigurationError):
        OpenAiCompatibleProvider(**cast(Any, arguments))


def _provider(completion_create: Any) -> OpenAiCompatibleProvider:
    return OpenAiCompatibleProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.invalid/v1",
        completion_create=completion_create,
    )


def _response(content: str) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
