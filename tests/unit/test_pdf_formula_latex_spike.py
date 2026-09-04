"""Evidence for the isolated digital formula / LaTeX geometry spike."""

from __future__ import annotations

import json
from pathlib import Path, PurePath

import pymupdf

from experiments.pdf_formula_latex_spike.formula_geometry import (
    recognize_formula_candidates,
)


MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "pdf_formula_latex_spike"
    / "corpus.json"
)


class _FakePage:
    def __init__(self, blocks: list[dict[str, object]]) -> None:
        self._blocks = blocks

    def get_text(self, mode: str, *, sort: bool) -> dict[str, object]:
        assert mode == "dict"
        assert sort is False
        return {"blocks": self._blocks}


def _span(
    text: str,
    bbox: tuple[float, float, float, float],
    *,
    size: float = 12.0,
    font: str = "Helvetica",
    origin_y: float = 100.0,
) -> dict[str, object]:
    return {
        "text": text,
        "bbox": bbox,
        "size": size,
        "font": font,
        "flags": 0,
        "origin": (bbox[0], origin_y),
    }


def _text_page(lines: list[list[dict[str, object]]]) -> _FakePage:
    return _FakePage(
        [
            {
                "type": 0,
                "lines": [{"spans": line} for line in lines],
            }
        ]
    )


def test_superscript_display_formula_has_bbox_and_safe_latex() -> None:
    page = _text_page(
        [[
            _span("E = mc", (40, 88, 82, 102)),
            _span("2", (82, 80, 87, 88), size=7.0, origin_y=92.0),
        ]]
    )

    candidates = recognize_formula_candidates(page, page_number=2)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.page_number == 2
    assert candidate.bbox == (40.0, 80.0, 87.0, 102.0)
    assert candidate.origin == "digital_text_geometry"
    assert "script" in candidate.signals
    assert candidate.latex_candidate == "E = mc^{2}"
    assert candidate.needs_model is False


def test_subscript_superscript_and_unicode_symbols_become_latex() -> None:
    page = _text_page(
        [[
            _span("x", (40, 88, 48, 102)),
            _span("i", (48, 98, 52, 106), size=7.0, origin_y=106.0),
            _span("∈", (58, 88, 68, 102)),
            _span("R", (74, 88, 84, 102)),
            _span("n", (84, 80, 89, 88), size=7.0, origin_y=92.0),
        ]]
    )

    candidate = recognize_formula_candidates(page, page_number=1)[0]

    assert candidate.latex_candidate == r"x_{i} \in R^{n}"
    assert {"math_symbol", "script"} <= set(candidate.signals)


def test_inline_formula_is_bounded_away_from_surrounding_prose() -> None:
    page = _text_page(
        [[
            _span("The model uses", (30, 88, 110, 102)),
            _span("P(Y|X)", (116, 88, 158, 102)),
            _span("for prediction.", (164, 88, 250, 102)),
        ]]
    )

    candidates = recognize_formula_candidates(page, page_number=1)

    assert len(candidates) == 1
    assert candidates[0].kind == "inline"
    assert candidates[0].source_text == "P(Y|X)"
    assert candidates[0].bbox == (116.0, 88.0, 158.0, 102.0)
    assert candidates[0].latex_candidate == r"P(Y\mid X)"


def test_mixed_chinese_prose_keeps_scripted_formula_bounded() -> None:
    page = _text_page(
        [[
            _span("其中", (30, 88, 54, 102), font="SimSun"),
            _span("(x", (54, 88, 66, 102)),
            _span("i", (66, 98, 70, 106), size=7.0, origin_y=106.0),
            _span(",y", (70, 88, 82, 102)),
            _span("i", (82, 98, 86, 106), size=7.0, origin_y=106.0),
            _span(")", (86, 88, 92, 102)),
            _span("称为样本点", (92, 88, 152, 102), font="SimSun"),
        ]]
    )

    candidates = recognize_formula_candidates(page, page_number=1)

    assert len(candidates) == 1
    assert candidates[0].source_text == "(xi,yi)"
    assert candidates[0].bbox == (54.0, 88.0, 92.0, 106.0)
    assert candidates[0].latex_candidate == "(x_{i},y_{i})"


def test_prose_and_code_false_positives_are_rejected() -> None:
    page = _text_page(
        [
            [_span("Version 2.0 = current baseline.", (30, 88, 230, 102))],
            [
                _span(
                    "cursor.execute('SELECT x FROM t WHERE id=%s')",
                    (30, 112, 310, 126),
                    font="Courier",
                    origin_y=124,
                )
            ],
        ]
    )

    assert recognize_formula_candidates(page, page_number=1) == []


def test_image_only_formula_remains_an_explicit_ocr_gap() -> None:
    page = _FakePage(
        [
            {
                "type": 1,
                "bbox": (40.0, 70.0, 200.0, 140.0),
                "image": b"not-inspected",
            }
        ]
    )

    assert recognize_formula_candidates(page, page_number=1) == []


def test_stacked_rows_are_not_claimed_as_fraction_or_matrix_latex() -> None:
    page = _text_page(
        [
            [_span("a + b", (80, 70, 120, 84), origin_y=82)],
            [_span("c + d", (80, 96, 120, 110), origin_y=108)],
        ]
    )

    candidates = recognize_formula_candidates(page, page_number=1)

    assert all(
        token not in (candidate.latex_candidate or "")
        for candidate in candidates
        for token in (r"\frac", r"\begin{matrix}", r"\begin{aligned}")
    )


def test_display_fragments_on_one_visual_line_merge_with_all_source_lines() -> None:
    page = _FakePage(
        [
            {
                "type": 0,
                "lines": [{"spans": [_span("E =", (40, 88, 68, 102))]}],
            },
            {
                "type": 0,
                "lines": [
                    {
                        "spans": [
                            _span("mc", (70, 88, 86, 102), font="CMMI10"),
                            _span(
                                "2",
                                (86, 80, 91, 88),
                                size=7.0,
                                font="CMMI10",
                                origin_y=92.0,
                            ),
                        ]
                    }
                ],
            },
        ]
    )

    candidates = recognize_formula_candidates(page, page_number=1)

    assert len(candidates) == 1
    assert candidates[0].source_lines == ((0, 0), (1, 0))
    assert "cross_block_merge" in candidates[0].signals
    assert candidates[0].latex_candidate == "E = mc^{2}"


def test_real_pymupdf_dictionary_boundary_produces_bounded_candidate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "digital-formula.pdf"
    document = pymupdf.open()
    try:
        page = document.new_page(width=360, height=220)
        page.insert_text(
            (40, 60),
            "Ordinary prose without mathematical notation.",
            fontname="helv",
            fontsize=11,
        )
        page.insert_text(
            (70, 120),
            "x^2 + y^2 = z^2",
            fontname="helv",
            fontsize=14,
        )
        document.save(path)
    finally:
        document.close()

    with pymupdf.open(path) as reopened:
        candidates = recognize_formula_candidates(reopened[0], page_number=1)

    assert any(
        candidate.source_text == "x^2 + y^2 = z^2"
        and candidate.bbox[0] >= 0
        and candidate.latex_candidate == "x^2 + y^2 = z^2"
        for candidate in candidates
    )


def test_spike_manifest_covers_digital_and_image_formula_boundaries() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = manifest["documents"]
    categories = {
        category
        for document in documents
        for category in document["categories"]
    }

    assert manifest["schema_version"] == 1
    assert len({document["id"] for document in documents}) == len(documents)
    assert {
        "digital_text",
        "formula",
        "image_formula_boundary",
        "math_fonts",
        "non_english",
        "scanned",
        "scripts",
    } <= categories
    assert all(len(document["sha256"]) == 64 for document in documents)
    assert all(
        not PurePath(document["filename"]).is_absolute()
        for document in documents
    )
    assert all(document["sample_pages"] for document in documents)
    labels = {
        document["id"]: document["manual_labels"]
        for document in documents
    }
    assert labels["code_security"]["digital_display_formula_regions"] == 3
    assert labels["statistical_learning"] == {
        "digital_display_formula_regions": 0,
        "image_formula_regions": 1,
    }
    assert labels["chinese_scan"] is None
