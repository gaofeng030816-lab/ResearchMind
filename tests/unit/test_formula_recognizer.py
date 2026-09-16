"""Provider adapter tests for one-crop formula recognition without networking."""

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

from openai import APITimeoutError
import pytest

from researchmind.config import Settings
from researchmind.llm import (
    LlmApiError,
    LlmBadResponseError,
    LlmConfigurationError,
    OpenAiCompatibleFormulaRecognizer,
    canonicalize_formula_latex,
    create_formula_recognizer,
)
from researchmind.models import FormulaCrop, FormulaRegion


def test_recognizer_sends_exactly_one_png_crop_and_fixed_prompt() -> None:
    captured: dict[str, object] = {}

    def fake_create(**kwargs: object) -> object:
        captured.update(kwargs)
        return _response(r"<latex>\sum_{i=1}^{n} i</latex>")

    crop = _crop()
    recognizer = _recognizer(fake_create)

    latex = recognizer.recognize(crop)

    assert latex == r"\sum_{i=1}^{n} i"
    assert captured["model"] == "test-vision-model"
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == 3_200
    assert captured["reasoning_effort"] == "low"
    messages = cast(list[dict[str, Any]], captured["messages"])
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert r"\tag{...}" in str(messages[0]["content"])
    assert "braces around every subscript" in str(messages[0]["content"])
    assert "do not invent" in str(messages[0]["content"]).casefold()
    user_content = cast(list[dict[str, Any]], messages[1]["content"])
    image_parts = [part for part in user_content if part["type"] == "image_url"]
    assert len(image_parts) == 1
    data_url = image_parts[0]["image_url"]["url"]
    assert data_url.startswith("data:image/png;base64,")
    assert "C:/" not in str(captured)
    assert "paper" not in str(captured).casefold()


def test_recognizer_returns_none_for_explicit_unreadable() -> None:
    recognizer = _recognizer(lambda **_: _response("<unreadable/>"))

    assert recognizer.recognize(_crop()) is None


def test_formula_recognizer_canonicalizes_only_unbraced_one_token_scripts() -> None:
    recognizer = _recognizer(
        lambda **_: _response(r"<latex>x_i+y^2+z^\top+a_{ij}+b^{-1}</latex>")
    )

    result = recognizer.recognize(_crop())

    assert result == r"x_{i}+y^{2}+z^{\top}+a_{ij}+b^{-1}"
    assert canonicalize_formula_latex(result) == result


@pytest.mark.parametrize(
    "response",
    (
        "```latex\\sum_i i```",
        r"<latex>\input{secret}</latex>",
        r"<latex>$$x$$</latex>",
        "explanation only",
    ),
)
def test_recognizer_rejects_untrusted_or_executable_latex(response: str) -> None:
    recognizer = _recognizer(lambda **_: _response(response))

    with pytest.raises(LlmBadResponseError):
        recognizer.recognize(_crop())


def test_recognizer_maps_timeout_without_crop_or_secret_details() -> None:
    def timeout(**_: object) -> object:
        raise APITimeoutError(request=cast(Any, object()))

    recognizer = _recognizer(timeout)

    with pytest.raises(LlmApiError, match="timed out") as error:
        recognizer.recognize(_crop())

    assert "unit-test" not in str(error.value)
    assert error.value.__cause__ is None


def test_recognizer_rejects_tampered_non_png_crop() -> None:
    crop = replace(_crop(), png_bytes=b"not-png")

    with pytest.raises(LlmConfigurationError, match="PNG"):
        _recognizer(lambda **_: _response("unused")).recognize(crop)


def test_factory_requires_existing_llm_credentials_without_network() -> None:
    with pytest.raises(LlmConfigurationError, match="LLM_API_KEY"):
        create_formula_recognizer(Settings())


def _recognizer(completion_create: Any) -> OpenAiCompatibleFormulaRecognizer:
    return OpenAiCompatibleFormulaRecognizer(
        api_key="unit-test-placeholder",
        model="test-vision-model",
        base_url="https://example.invalid/v1",
        completion_create=completion_create,
    )


def _crop() -> FormulaCrop:
    png = b"\x89PNG\r\n\x1a\nunit-test-image"
    region = FormulaRegion(
        id="formula-region-test",
        document_id="document-test",
        document_revision=f"sha256:{'a' * 64}",
        page_number=1,
        bbox=(10.0, 20.0, 100.0, 60.0),
        kind="display",
        source_kind="digital_text",
        detector_origin="unit-test-detector",
        detector_confidence=0.9,
        signals=("strong_symbol",),
    )
    return FormulaCrop(
        region=region,
        png_bytes=png,
        sha256=sha256(png).hexdigest(),
        width_px=270,
        height_px=120,
    )


def _response(content: str) -> object:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
