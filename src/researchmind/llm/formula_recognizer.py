"""Provider-neutral formula recognizer and OpenAI-compatible vision adapter."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Callable
import re
from typing import Protocol

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError

from researchmind.config import DEFAULT_LLM_API_KEY_HEADER, DEFAULT_LLM_BASE_URL, Settings
from researchmind.llm.errors import LlmApiError, LlmConfigurationError
from researchmind.llm.latex import parse_latex_response
from researchmind.llm.providers.openai_compatible import (
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    _build_completion_create,
    _validate_configuration,
    parse_response,
)
from researchmind.models import FormulaCrop, FormulaExecution


MAX_FORMULA_RESPONSE_TOKENS = 3_200
FORMULA_REASONING_EFFORT = "low"
_FORMULA_SYSTEM_PROMPT = (
    "You transcribe exactly one mathematical formula crop into LaTeX. "
    "Preserve visible structure, scripts, limits, matrices, cases, accents, and symbols. "
    "Preserve a clearly visible equation number as \\tag{...}; do not invent one. "
    "Use braces around every subscript and superscript argument, including one token. "
    "Write a visible differential product with a thin space, for example \\,dx. "
    "Do not add prose, conditions, punctuation, or spacing that is not visible. "
    "Do not explain or infer missing content. "
    "Return exactly <latex>...</latex> without math delimiters, or <unreadable/>."
)
_FORMULA_USER_PROMPT = (
    "Transcribe only the attached formula crop. The crop may be incomplete or ambiguous; "
    "return <unreadable/> instead of guessing."
)

CompletionCreate = Callable[..., object]
_UNBRACED_SCRIPT_PATTERN = re.compile(r"([_^])(\\[A-Za-z]+|[A-Za-z0-9])")


class FormulaRecognizer(Protocol):
    """Infrastructure boundary for one bounded formula crop."""

    @property
    def name(self) -> str: ...

    @property
    def model_revision(self) -> str: ...

    @property
    def execution(self) -> FormulaExecution: ...

    def recognize(self, crop: FormulaCrop) -> str | None: ...


class OpenAiCompatibleFormulaRecognizer:
    """Remote vision adapter that sends exactly one validated PNG crop."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        api_key_header: str = DEFAULT_LLM_API_KEY_HEADER,
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

    @property
    def name(self) -> str:
        return "openai-compatible-vision"

    @property
    def model_revision(self) -> str:
        return self._model

    @property
    def execution(self) -> FormulaExecution:
        return "remote"

    def recognize(self, crop: FormulaCrop) -> str | None:
        """Return one strict LaTeX body, or None when unreadable."""

        if not crop.png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise LlmConfigurationError("Formula recognition requires one PNG crop.")
        data_url = "data:image/png;base64," + b64encode(crop.png_bytes).decode("ascii")
        messages: list[dict[str, object]] = [
            {"role": "system", "content": _FORMULA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _FORMULA_USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "high"},
                    },
                ],
            },
        ]
        try:
            response = self._completion_create(
                model=self._model,
                messages=messages,
                temperature=0,
                max_tokens=MAX_FORMULA_RESPONSE_TOKENS,
                reasoning_effort=FORMULA_REASONING_EFFORT,
            )
        except APITimeoutError:
            raise LlmApiError("The formula recognition request timed out.") from None
        except APIConnectionError:
            raise LlmApiError(
                "Could not connect to the configured formula recognition service."
            ) from None
        except APIStatusError as exc:
            raise LlmApiError(
                f"The formula recognition service returned HTTP status {exc.status_code}."
            ) from None
        except APIError:
            raise LlmApiError(
                "The configured formula recognition service rejected the request."
            ) from None

        assistant_text = parse_response(response)
        if assistant_text == "<unreadable/>":
            return None
        parsed = parse_latex_response(assistant_text)
        canonical = canonicalize_formula_latex(parsed)
        return parse_latex_response(f"<latex>{canonical}</latex>")


def canonicalize_formula_latex(expression: str) -> str:
    """Brace one-token scripts without changing mathematical structure."""

    return _UNBRACED_SCRIPT_PATTERN.sub(r"\1{\2}", expression)


def create_formula_recognizer(settings: Settings) -> FormulaRecognizer:
    """Construct the configured remote formula recognizer without making a request."""

    if settings.llm_api_key is None:
        raise LlmConfigurationError(
            "LLM_API_KEY is not configured. Add it before formula recognition."
        )
    if settings.llm_model is None:
        raise LlmConfigurationError(
            "LLM_MODEL is not configured. Add it before formula recognition."
        )
    return OpenAiCompatibleFormulaRecognizer(
        api_key=settings.llm_api_key,
        api_key_header=settings.llm_api_key_header,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
