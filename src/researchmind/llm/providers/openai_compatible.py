"""OpenAI-compatible implementation of the ResearchMind LLM provider."""

from __future__ import annotations

from collections.abc import Callable
import math
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    DefaultHttpxClient,
    OpenAI,
    OpenAIError,
)

from researchmind.config import DEFAULT_LLM_API_KEY_HEADER, DEFAULT_LLM_BASE_URL
from researchmind.llm.base import ChatMessage
from researchmind.llm.errors import (
    LlmApiError,
    LlmBadResponseError,
    LlmConfigurationError,
)


DEFAULT_LLM_TIMEOUT_SECONDS = 60.0
DEFAULT_LLM_MAX_RETRIES = 2
SUPPORTED_API_KEY_HEADERS = frozenset({"authorization", "api-key"})

# V1 sends text-only chat requests. An allowlist prevents callers from quietly
# granting tools, function calling, web search, streaming, or other authority.
ALLOWED_COMPLETION_OPTIONS = frozenset(
    {
        "frequency_penalty",
        "max_completion_tokens",
        "max_tokens",
        "presence_penalty",
        "reasoning_effort",
        "seed",
        "stop",
        "temperature",
        "top_p",
        "verbosity",
    }
)

CompletionCreate = Callable[..., object]


class OpenAiCompatibleProvider:
    """Text-only chat provider for OpenAI-compatible HTTP endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        api_key_header: str = DEFAULT_LLM_API_KEY_HEADER,
        model: str,
        base_url: str = DEFAULT_LLM_BASE_URL,
        timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_LLM_MAX_RETRIES,
        completion_create: CompletionCreate | None = None,
    ) -> None:
        normalized_api_key = api_key.strip()
        normalized_api_key_header = api_key_header.strip()
        normalized_model = model.strip()
        normalized_base_url = base_url.strip()
        _validate_configuration(
            api_key=normalized_api_key,
            api_key_header=normalized_api_key_header,
            model=normalized_model,
            base_url=normalized_base_url,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        self._model = normalized_model
        self._completion_create = completion_create or _build_completion_create(
            api_key=normalized_api_key,
            api_key_header=normalized_api_key_header,
            base_url=normalized_base_url,
            timeout_seconds=float(timeout_seconds),
            max_retries=max_retries,
        )

    def complete(
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> str:
        """Send a text-only chat completion and return validated assistant text."""

        if not messages:
            raise LlmConfigurationError("At least one chat message is required.")

        unsupported_options = sorted(set(kwargs) - ALLOWED_COMPLETION_OPTIONS)
        if unsupported_options:
            joined_options = ", ".join(unsupported_options)
            raise LlmConfigurationError(
                f"Unsupported LLM completion options: {joined_options}"
            )

        provider_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
        ]

        try:
            response = self._completion_create(
                model=self._model,
                messages=provider_messages,
                **kwargs,
            )
        except APITimeoutError:
            raise LlmApiError("The LLM request timed out.") from None
        except APIConnectionError:
            raise LlmApiError("Could not connect to the configured LLM service.") from None
        except APIStatusError as exc:
            raise LlmApiError(
                f"The LLM service returned HTTP status {exc.status_code}."
            ) from None
        except APIError:
            raise LlmApiError(
                "The configured LLM service rejected the request."
            ) from None

        return parse_response(response)


def parse_response(response: object) -> str:
    """Extract non-empty text from one OpenAI-compatible chat response."""

    try:
        choices = getattr(response, "choices")
        if not choices:
            raise LlmBadResponseError("The LLM response contained no choices.")
        content = choices[0].message.content
    except LlmBadResponseError:
        raise
    except (AttributeError, IndexError, TypeError) as exc:
        raise LlmBadResponseError(
            "The LLM response had an unexpected structure."
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise LlmBadResponseError("The LLM response contained no assistant text.")
    return content.strip()


def _build_completion_create(
    *,
    api_key: str,
    api_key_header: str,
    base_url: str,
    timeout_seconds: float,
    max_retries: int,
) -> CompletionCreate:
    try:
        if api_key_header.casefold() == "authorization":
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=max_retries,
            )
        else:
            http_client = DefaultHttpxClient(
                event_hooks={
                    "request": [
                        _custom_api_key_request_hook(
                            api_key_header=api_key_header,
                            api_key=api_key,
                        )
                    ]
                }
            )
            client = OpenAI(
                api_key="custom-header-auth",
                base_url=base_url,
                timeout=timeout_seconds,
                max_retries=max_retries,
                http_client=http_client,
            )
    except (OpenAIError, TypeError, ValueError):
        raise LlmConfigurationError(
            "Could not initialize the configured LLM provider."
        ) from None
    return client.chat.completions.create


def _custom_api_key_request_hook(
    *,
    api_key_header: str,
    api_key: str,
) -> Callable[[Any], None]:
    """Replace the SDK Bearer header immediately before an HTTP request."""

    def apply_custom_header(request: Any) -> None:
        request.headers.pop("Authorization", None)
        request.headers[api_key_header] = api_key

    return apply_custom_header


def _validate_configuration(
    *,
    api_key: str,
    api_key_header: str,
    model: str,
    base_url: str,
    timeout_seconds: float,
    max_retries: int,
) -> None:
    if not api_key:
        raise LlmConfigurationError("LLM_API_KEY is required to use the LLM provider.")
    if api_key_header.casefold() not in SUPPORTED_API_KEY_HEADERS:
        raise LlmConfigurationError(
            "LLM_API_KEY_HEADER must be Authorization or api-key."
        )
    if not model:
        raise LlmConfigurationError("LLM_MODEL is required to use the LLM provider.")
    if not base_url:
        raise LlmConfigurationError("LLM_BASE_URL must not be empty.")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or timeout_seconds <= 0
    ):
        raise LlmConfigurationError("LLM timeout must be a positive finite number.")
    if (
        isinstance(max_retries, bool)
        or not isinstance(max_retries, int)
        or max_retries < 0
    ):
        raise LlmConfigurationError("LLM max retries must be a non-negative integer.")
