"""Offline checks for the versioned T0 real-paper evaluation corpus."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchmind.core.research_context import build_research_context
from researchmind.core.selection import locate_selection
from researchmind.llm.latex import parse_latex_response
from researchmind.models import Document, Page, ReadingSelection, TextBlock


CORPUS_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluations"
    / "v1_baseline"
    / "corpus.json"
)


@pytest.fixture(scope="module")
def corpus() -> dict[str, object]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def test_corpus_has_minimum_real_samples(corpus: dict[str, object]) -> None:
    assert corpus["schema_version"] == 1
    for collection in (
        "selection_cases",
        "research_context_cases",
        "formula_cases",
    ):
        cases = corpus[collection]
        assert isinstance(cases, list)
        assert len(cases) >= 2
        assert all(case["source"]["filename"] for case in cases)


def test_selection_cases_reproduce_v132_location(
    corpus: dict[str, object],
) -> None:
    for case in corpus["selection_cases"]:
        pages = [_page_from_payload(page) for page in case["pages"]]

        selection = locate_selection(
            case["selected_text"],
            pages,
            current_page=case["current_page"],
        )

        assert selection.locator is not None
        assert selection.locator["page_number"] == case["expected_locator"]["page_number"]
        assert selection.locator["block_index"] == case["expected_locator"]["block_index"]
        assert list(selection.locator["bbox"]) == case["expected_locator"]["bbox"]
        located_block = pages[0].blocks[0]
        assert list(located_block.bbox or ()) == case["observed_source_bbox"]


def test_research_context_cases_reproduce_structure_evidence(
    corpus: dict[str, object],
) -> None:
    for case in corpus["research_context_cases"]:
        page = Page(
            page_number=case["page_number"],
            text="\n\n".join(block["text"] for block in case["blocks"]),
            blocks=[_block_from_payload(block) for block in case["blocks"]],
        )
        document = Document(
            id=case["id"],
            title=case["document_title"],
            authors=[],
            source_type="pdf",
            path=Path(case["source"]["filename"]),
            num_pages=case["page_number"],
        )
        selection = ReadingSelection(
            text=case["selected_text"],
            locator={
                "page_number": case["page_number"],
                "block_index": case["selected_block_index"],
            },
        )

        context = build_research_context(
            selection,
            document,
            [page],
            user_question="Explain this evidence.",
            context_token_budget=400,
            history_token_budget=100,
        )

        assert context.section_heading == case["expected"]["section_heading"]
        assert context.related_caption == case["expected"]["related_caption"]
        assert context.related_formula == case["expected"]["related_formula"]
        assert context.page_number == case["page_number"]


def test_formula_cases_have_safe_parseable_reference_latex(
    corpus: dict[str, object],
) -> None:
    for case in corpus["formula_cases"]:
        expression = parse_latex_response(case["accepted_latex_response"])

        assert case["candidate_role"] == "formula"
        assert case["extracted_text"].strip()
        assert all(
            fragment in expression
            for fragment in case["required_latex_fragments"]
        )


def _page_from_payload(payload: dict[str, object]) -> Page:
    blocks = [_block_from_payload(block) for block in payload["blocks"]]
    return Page(
        page_number=payload["page_number"],
        text="\n\n".join(block.text for block in blocks),
        blocks=blocks,
    )


def _block_from_payload(payload: dict[str, object]) -> TextBlock:
    bbox = payload.get("bbox")
    return TextBlock(
        block_index=payload["block_index"],
        text=payload["text"],
        bbox=None if bbox is None else tuple(bbox),
        role=payload["role"],
    )
