"""Tests for G5 local formula-region detection and crop rendering."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import shutil

import pymupdf
import pytest

from researchmind.pdf import (
    PdfFormulaError,
    detect_formula_regions,
    open_pdf,
    render_formula_crop,
)
from researchmind.pdf.formulas import _cluster_is_bounded, _formula_text_fragments


CORPUS_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "g5_formula_recognition"
    / "corpus.pdf"
)


def test_cleanroom_corpus_detects_and_crops_all_structural_cases() -> None:
    opened = open_pdf(CORPUS_PDF)

    regions_by_page = [
        detect_formula_regions(opened, page_number)
        for page_number in range(1, opened.document.num_pages + 1)
    ]

    assert opened.document.num_pages == 20
    assert all(regions for regions in regions_by_page)
    assert len(regions_by_page[2]) == 1  # bounded integral with two limits
    assert len(regions_by_page[4]) == 1  # sum, upper/lower limits, fraction
    assert len(regions_by_page[9]) == 1  # matrix product with indexed sum
    assert len(regions_by_page[10]) == 1  # matrix
    assert len(regions_by_page[18]) == 1  # contour integral

    for page_number, regions in enumerate(regions_by_page, start=1):
        for region in regions:
            crop = render_formula_crop(opened, region)
            assert region.page_number == page_number
            assert region.document_revision == f"sha256:{opened.content_sha256}"
            assert crop.png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
            assert crop.sha256 == sha256(crop.png_bytes).hexdigest()
            assert crop.width_px > 0
            assert crop.height_px > 0
            assert str(CORPUS_PDF) not in repr(region)
            assert "png_bytes" not in repr(crop)


def test_embedded_formula_image_is_a_separate_candidate(tmp_path: Path) -> None:
    output = tmp_path / "image-formula.pdf"
    crop_path = (
        Path(__file__).parents[2]
        / "experiments"
        / "g5_formula_recognition"
        / "crops"
        / "01_basic_superscript.png"
    )
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "A normal paragraph without mathematical notation.")
    page.insert_image(
        pymupdf.Rect(180, 300, 420, 390),
        stream=crop_path.read_bytes(),
    )
    document.save(output)
    document.close()

    opened = open_pdf(output)
    regions = detect_formula_regions(opened, 1)

    image_regions = [item for item in regions if item.source_kind == "embedded_image"]
    assert len(image_regions) == 1
    assert image_regions[0].source_text is None
    assert image_regions[0].detector_confidence == 0.55


def test_figure_shaped_embedded_image_is_not_a_formula_candidate(
    tmp_path: Path,
) -> None:
    figure_document = pymupdf.open()
    figure_page = figure_document.new_page(width=240, height=160)
    figure_page.draw_line((20, 140), (220, 140))
    figure_page.draw_line((20, 140), (20, 20))
    figure_page.draw_polyline(((20, 120), (80, 60), (140, 100), (220, 30)))
    figure_png = figure_page.get_pixmap(alpha=False).tobytes("png")
    figure_document.close()

    output = tmp_path / "ordinary-figure.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_image(
        pymupdf.Rect(180, 300, 420, 460),
        stream=figure_png,
    )
    document.save(output)
    document.close()

    regions = detect_formula_regions(open_pdf(output), 1)

    assert all(item.source_kind != "embedded_image" for item in regions)


class _FormulaBlockPage:
    rect = pymupdf.Rect(0, 0, 595, 842)

    def __init__(self, line_count: int) -> None:
        self._lines = [
            {
                "spans": [
                    {
                        "text": f"x_{index} = x_{index - 1} + beta",
                        "font": "SyntheticMath",
                        "size": 12.0,
                    }
                ]
            }
            for index in range(1, line_count + 1)
        ]

    def get_text(self, mode: str, *, sort: bool) -> dict[str, object]:
        assert mode == "dict"
        assert sort is False
        return {
            "blocks": [
                {
                    "type": 0,
                    "bbox": (100.0, 100.0, 495.0, 100.0 + len(self._lines) * 22.0),
                    "lines": self._lines,
                }
            ]
        }


def test_long_algorithm_like_math_block_is_not_a_formula_fragment() -> None:
    assert _formula_text_fragments(
        _FormulaBlockPage(6),  # type: ignore[arg-type]
        include_inline=False,
    ) == []


def test_bounded_multiline_formula_block_remains_a_fragment() -> None:
    fragments = _formula_text_fragments(
        _FormulaBlockPage(2),  # type: ignore[arg-type]
        include_inline=False,
    )

    assert len(fragments) == 1


def test_short_unbalanced_formula_cluster_is_not_a_candidate() -> None:
    page = _FormulaBlockPage(1)
    page._lines[0]["spans"][0]["text"] = "L_f = -H("

    fragments = _formula_text_fragments(
        page,  # type: ignore[arg-type]
        include_inline=False,
    )

    assert len(fragments) == 1
    assert _cluster_is_bounded(tuple(fragments)) is False


def test_plain_prose_does_not_invent_formula_region(tmp_path: Path) -> None:
    output = tmp_path / "prose.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    page.insert_text(
        (72, 100),
        "ResearchMind keeps ordinary prose separate from formula candidates.",
    )
    document.save(output)
    document.close()

    assert detect_formula_regions(open_pdf(output), 1) == ()


def test_crop_rejects_stale_document_and_foreign_region(tmp_path: Path) -> None:
    copied = tmp_path / "corpus.pdf"
    shutil.copyfile(CORPUS_PDF, copied)
    opened = open_pdf(copied)
    region = detect_formula_regions(opened, 3)[0]

    foreign = replace(region, document_id="another-document")
    with pytest.raises(PdfFormulaError, match="another document"):
        render_formula_crop(opened, foreign)

    copied.write_bytes(copied.read_bytes() + b"\nchanged")
    with pytest.raises(PdfFormulaError, match="changed or is no longer readable"):
        render_formula_crop(opened, region)


@pytest.mark.parametrize(
    ("zoom", "padding"),
    ((0, 8), (6.1, 8), (3, -1), (3, 25)),
)
def test_crop_rejects_unbounded_render_options(zoom: float, padding: float) -> None:
    opened = open_pdf(CORPUS_PDF)
    region = detect_formula_regions(opened, 1)[0]

    with pytest.raises(PdfFormulaError):
        render_formula_crop(opened, region, zoom=zoom, padding_points=padding)
