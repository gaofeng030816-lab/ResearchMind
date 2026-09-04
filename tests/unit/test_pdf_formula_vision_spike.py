"""Safety and boundary tests for the isolated formula-vision spike."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from researchmind.llm.errors import LlmBadResponseError
from experiments.pdf_formula_latex_spike.formula_vision import (
    build_formula_vision_messages,
    convert_formula_crop,
    detect_embedded_formula_images,
    parse_formula_vision_response,
    render_formula_crop,
)
from experiments.pdf_formula_latex_spike.probe_multimodal import (
    _build_completion_create,
)


class _FakePage:
    def __init__(self, blocks: list[dict[str, object]]) -> None:
        self._blocks = blocks

    def get_text(self, mode: str, *, sort: bool) -> dict[str, object]:
        assert mode == "dict"
        assert sort is False
        return {"blocks": self._blocks}


def _png_bytes() -> bytes:
    document = pymupdf.open()
    try:
        page = document.new_page(width=120, height=60)
        page.insert_text((12, 34), "E = mc^2", fontsize=14)
        return page.get_pixmap(alpha=False).tobytes("png")
    finally:
        document.close()


def test_wide_short_embedded_image_is_candidate_but_full_page_scan_is_not() -> None:
    page = _FakePage(
        [
            {"type": 1, "bbox": (100, 200, 350, 230)},
            {"type": 1, "bbox": (0, 0, 600, 780)},
            {"type": 1, "bbox": (100, 260, 115, 280)},
        ]
    )

    candidates = detect_embedded_formula_images(page, page_number=4)

    assert len(candidates) == 1
    assert candidates[0].page_number == 4
    assert candidates[0].block_index == 0
    assert candidates[0].bbox == (100.0, 200.0, 350.0, 230.0)
    assert candidates[0].origin == "embedded_image_geometry"


def test_crop_render_is_png_and_respects_page_intersection(tmp_path: Path) -> None:
    path = tmp_path / "formula.pdf"
    document = pymupdf.open()
    try:
        page = document.new_page(width=300, height=180)
        page.insert_text((60, 90), "x^2 + y^2 = z^2", fontsize=16)
        document.save(path)
    finally:
        document.close()

    with pymupdf.open(path) as reopened:
        png = render_formula_crop(reopened[0], (50, 65, 230, 105))

    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png) < 2 * 1024 * 1024


def test_multimodal_message_contains_only_fixed_text_and_png_data_url() -> None:
    messages = build_formula_vision_messages(_png_bytes())

    assert [message["role"] for message in messages] == ["system", "user"]
    content = messages[1]["content"]
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    serialized = repr(messages)
    assert "D:\\" not in serialized
    assert "api-key" not in serialized


def test_formula_vision_response_is_strict_or_explicitly_unreadable() -> None:
    assert parse_formula_vision_response(
        r"<latex>\frac{a+b}{c+d}</latex>"
    ) == r"\frac{a+b}{c+d}"
    assert parse_formula_vision_response("<unreadable/>") is None

    with pytest.raises(LlmBadResponseError):
        parse_formula_vision_response(
            r"<latex>\input{secrets}</latex>"
        )


def test_conversion_uses_fake_provider_and_fixed_limits() -> None:
    captured: dict[str, object] = {}

    def completion_create(**kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=r"<latex>E=mc^{2}</latex>"
                    )
                )
            ]
        )

    expression = convert_formula_crop(
        completion_create=completion_create,
        model="fake-multimodal",
        png_bytes=_png_bytes(),
    )

    assert expression == r"E=mc^{2}"
    assert captured["model"] == "fake-multimodal"
    assert captured["temperature"] == 0
    assert captured["max_tokens"] == 768
    assert isinstance(captured["messages"], list)


@pytest.mark.parametrize(
    "payload",
    (b"not-png", b"", "not-bytes"),
)
def test_non_png_or_non_bytes_payload_is_rejected(payload: object) -> None:
    with pytest.raises(ValueError):
        build_formula_vision_messages(payload)  # type: ignore[arg-type]


def test_live_probe_rejects_arbitrary_authentication_header() -> None:
    with pytest.raises(ValueError):
        _build_completion_create(
            api_key="placeholder",
            api_key_header="X-Arbitrary-Key",
            base_url="https://example.invalid/v1",
        )
