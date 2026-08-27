"""Tests for the safe PyMuPDF reader boundary."""

from __future__ import annotations

from pathlib import Path
import struct

import pytest

from researchmind.models import Page, TextBlock
from researchmind.pdf import (
    MAX_RENDER_ZOOM,
    PdfExtractionError,
    PdfPageError,
    PdfRenderError,
    PdfValidationError,
    extract_page,
    open_pdf,
    render_page_image,
)
from tests.fixtures.pdf_factory import create_text_pdf


def test_open_pdf_extracts_metadata_pages_text_and_blocks(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf)

    assert opened.document.title == "Fixture Research Paper"
    assert opened.document.authors == ["Ada Researcher", "Grace Scientist"]
    assert opened.document.source_type == "pdf"
    assert opened.document.path == single_page_pdf.resolve()
    assert opened.document.num_pages == 1
    assert len(opened.document.id) == 16

    page = extract_page(opened, 1)
    assert isinstance(page, Page)
    assert page.page_number == 1
    assert "ResearchMind introduction" in page.text
    assert "Second context block" in page.text
    assert len(page.blocks) == 2
    assert all(isinstance(block, TextBlock) for block in page.blocks)
    assert all(block.bbox is not None and len(block.bbox) == 4 for block in page.blocks)


def test_open_pdf_preserves_one_based_page_order(multi_page_pdf: Path) -> None:
    opened = open_pdf(multi_page_pdf)

    assert opened.document.num_pages == 3
    assert [page.page_number for page in opened.pages] == [1, 2, 3]
    assert "Page one" in opened.pages[0].text
    assert "Page two" in opened.pages[1].text
    assert "Page three" in opened.pages[2].text


def test_open_pdf_uses_filename_when_metadata_title_is_empty(tmp_path: Path) -> None:
    path = create_text_pdf(tmp_path / "fallback-title.pdf", [["content"]])

    opened = open_pdf(path)

    assert opened.document.title == "fallback-title"
    assert opened.document.authors == []


def test_blank_page_extracts_empty_text_and_blocks(blank_page_pdf: Path) -> None:
    opened = open_pdf(blank_page_pdf)

    assert opened.pages[0].text == ""
    assert opened.pages[0].blocks == []


def test_unicode_and_mathematical_content_is_extracted(
    unicode_math_pdf: Path,
) -> None:
    text = open_pdf(unicode_math_pdf).pages[0].text

    assert "中文文本" in text
    assert "α" in text
    assert "β" in text
    assert "γ" in text
    assert "x^2 + y^2 = z^2" in text


@pytest.mark.parametrize("page_number", (0, 2, -1, True))
def test_extract_page_rejects_invalid_page_numbers(
    single_page_pdf: Path,
    page_number: int,
) -> None:
    opened = open_pdf(single_page_pdf)

    with pytest.raises(PdfPageError):
        extract_page(opened, page_number)


def test_render_page_image_returns_zoomed_png(single_page_pdf: Path) -> None:
    opened = open_pdf(single_page_pdf)

    normal_png = render_page_image(opened, 1, zoom=1.0)
    zoomed_png = render_page_image(opened, 1, zoom=2.0)

    assert normal_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert zoomed_png.startswith(b"\x89PNG\r\n\x1a\n")
    normal_width, normal_height = _png_dimensions(normal_png)
    zoomed_width, zoomed_height = _png_dimensions(zoomed_png)
    assert (zoomed_width, zoomed_height) == (
        normal_width * 2,
        normal_height * 2,
    )


@pytest.mark.parametrize("zoom", (0.0, -1.0, float("inf"), MAX_RENDER_ZOOM + 0.1))
def test_render_page_image_rejects_unsafe_zoom(
    single_page_pdf: Path,
    zoom: float,
) -> None:
    opened = open_pdf(single_page_pdf)

    with pytest.raises(PdfRenderError):
        render_page_image(opened, 1, zoom=zoom)


def test_missing_pdf_raises_project_validation_error(tmp_path: Path) -> None:
    with pytest.raises(PdfValidationError, match="does not exist"):
        open_pdf(tmp_path / "missing.pdf")


def test_non_pdf_extension_is_rejected(single_page_pdf: Path) -> None:
    renamed_path = single_page_pdf.with_suffix(".txt")
    single_page_pdf.rename(renamed_path)

    with pytest.raises(PdfValidationError, match=".pdf extension"):
        open_pdf(renamed_path)


def test_invalid_pdf_magic_is_rejected(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.pdf"
    invalid_path.write_bytes(b"plain text")

    with pytest.raises(PdfValidationError, match="signature"):
        open_pdf(invalid_path)


def test_oversized_pdf_is_rejected(single_page_pdf: Path) -> None:
    with pytest.raises(PdfValidationError, match="size limit"):
        open_pdf(single_page_pdf, max_size_bytes=single_page_pdf.stat().st_size - 1)


def test_corrupt_pdf_maps_parser_failure_to_project_error(
    corrupt_pdf: Path,
) -> None:
    with pytest.raises(PdfExtractionError) as error:
        open_pdf(corrupt_pdf)

    assert error.value.__cause__ is not None
    assert error.value.__cause__.__class__.__module__.startswith("pymupdf")


def test_render_maps_changed_corrupt_source_to_project_error(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf)
    single_page_pdf.write_bytes(b"%PDF-1.7\ncorrupt replacement")

    with pytest.raises(PdfRenderError) as error:
        render_page_image(opened, 1)

    assert error.value.__cause__ is not None


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    return struct.unpack(">II", png_bytes[16:24])
