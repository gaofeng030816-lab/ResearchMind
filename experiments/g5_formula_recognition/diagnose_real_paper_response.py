"""Inspect one authorized provider response structurally without storing its text."""

from __future__ import annotations

import argparse
from base64 import b64encode
import json
from pathlib import Path
from typing import Any, Sequence

from researchmind.config import load_settings
from researchmind.llm.formula_recognizer import (
    MAX_FORMULA_RESPONSE_TOKENS,
    _FORMULA_SYSTEM_PROMPT,
    _FORMULA_USER_PROMPT,
)
from researchmind.llm.providers.openai_compatible import (
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    _build_completion_create,
)
from researchmind.models import FormulaCrop

from experiments.g5_formula_recognition.run_real_paper_recognizer import (
    DEFAULT_ANNOTATIONS,
    DEFAULT_CROP_ROOT,
    DEFAULT_INSPECTION,
    EXPECTED_MODEL,
    _load_json,
    recognize_real_paper_case,
)


class _StructuralDiagnosticRecognizer:
    """Send the normal request and retain only non-content response metadata."""

    name = "openai-compatible-vision-diagnostic"
    model_revision = EXPECTED_MODEL
    execution = "remote"

    def __init__(
        self,
        *,
        max_tokens: int = MAX_FORMULA_RESPONSE_TOKENS,
        reasoning_effort: str | None = None,
    ) -> None:
        settings = load_settings()
        if settings.llm_api_key is None or settings.llm_model != EXPECTED_MODEL:
            raise ValueError("The configured formula credentials/model are unavailable.")
        self._completion_create = _build_completion_create(
            api_key=settings.llm_api_key,
            api_key_header=settings.llm_api_key_header,
            base_url=settings.llm_base_url,
            timeout_seconds=DEFAULT_LLM_TIMEOUT_SECONDS,
            max_retries=DEFAULT_LLM_MAX_RETRIES,
        )
        self._max_tokens = max_tokens
        self._reasoning_effort = reasoning_effort
        self.metadata: dict[str, Any] | None = None

    def recognize(self, crop: FormulaCrop) -> None:
        data_url = "data:image/png;base64," + b64encode(crop.png_bytes).decode("ascii")
        options: dict[str, object] = {
            "temperature": 0,
            "max_tokens": self._max_tokens,
        }
        if self._reasoning_effort is not None:
            options["reasoning_effort"] = self._reasoning_effort
        response = self._completion_create(
            model=EXPECTED_MODEL,
            messages=[
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
            ],
            **options,
        )
        self.metadata = _sanitize_response_structure(response)
        self.metadata["request_options"] = {
            "max_tokens": self._max_tokens,
            "reasoning_effort": self._reasoning_effort,
        }
        return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--confirm-sha256", required=True)
    parser.add_argument("--authorized-external-transfer", action="store_true")
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--inspection", type=Path, default=DEFAULT_INSPECTION)
    parser.add_argument("--crop-root", type=Path, default=DEFAULT_CROP_ROOT)
    parser.add_argument("--max-tokens", type=int, default=MAX_FORMULA_RESPONSE_TOKENS)
    parser.add_argument("--reasoning-effort", choices=("low", "medium", "high"))
    args = parser.parse_args(argv)

    if args.max_tokens < 256 or args.max_tokens > 4_000:
        parser.error("--max-tokens must be between 256 and 4000.")
    recognizer = _StructuralDiagnosticRecognizer(
        max_tokens=args.max_tokens,
        reasoning_effort=args.reasoning_effort,
    )
    recognize_real_paper_case(
        case_id=args.case_id,
        confirmed_sha256=args.confirm_sha256,
        external_transfer_authorized=args.authorized_external_transfer,
        annotations=_load_json(args.annotations),
        inspection=_load_json(args.inspection),
        crop_root=args.crop_root,
        recognizer=recognizer,
    )
    if recognizer.metadata is None:
        raise ValueError("The provider returned no diagnostic response.")
    print(json.dumps(recognizer.metadata, ensure_ascii=False, indent=2))
    return 0


def _sanitize_response_structure(response: object) -> dict[str, Any]:
    choices = getattr(response, "choices", None)
    result: dict[str, Any] = {
        "response_type": type(response).__name__,
        "choices_type": type(choices).__name__,
        "choices_count": len(choices) if isinstance(choices, list) else None,
    }
    if isinstance(choices, list) and choices:
        choice = choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        refusal = getattr(message, "refusal", None)
        model_extra = getattr(message, "model_extra", None)
        result.update(
            finish_reason=getattr(choice, "finish_reason", None),
            message_type=type(message).__name__,
            content_type=type(content).__name__,
            content_is_empty=content is None or content == "",
            content_char_count=len(content) if isinstance(content, str) else None,
            refusal_type=type(refusal).__name__,
            refusal_char_count=len(refusal) if isinstance(refusal, str) else None,
            extra_fields=_field_shapes(model_extra),
        )
    usage = getattr(response, "usage", None)
    result["usage"] = {
        name: getattr(usage, name, None)
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    return result


def _field_shapes(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): {
            "type": type(field_value).__name__,
            "char_count": len(field_value) if isinstance(field_value, str) else None,
        }
        for key, field_value in sorted(value.items())
    }


if __name__ == "__main__":
    raise SystemExit(main())
