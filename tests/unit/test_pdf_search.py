"""Tests for block-level document text search."""

from pathlib import Path

import pytest

from researchmind.models import Document, Page, TextBlock
from researchmind.pdf import OpenedDocument, open_pdf, search_text


def test_search_returns_case_insensitive_hits_in_page_order(
    multi_page_pdf: Path,
) -> None:
    opened = open_pdf(multi_page_pdf)

    matches = search_text(opened, "optimization")

    assert [match.page_number for match in matches] == [1, 2]
    assert all("optimization" in match.excerpt.casefold() for match in matches)


def test_search_normalizes_query_and_block_whitespace(tmp_path: Path) -> None:
    opened = _opened_document(
        tmp_path,
        [TextBlock(block_index=4, text="adaptive\n  optimization method")],
    )

    matches = search_text(opened, "  ADAPTIVE optimization   method ")

    assert len(matches) == 1
    assert matches[0].block_index == 4
    assert matches[0].excerpt == "adaptive optimization method"


def test_search_returns_one_hit_per_matching_block(tmp_path: Path) -> None:
    opened = _opened_document(
        tmp_path,
        [
            TextBlock(block_index=0, text="method method method"),
            TextBlock(block_index=1, text="another method"),
        ],
    )

    matches = search_text(opened, "method")

    assert [match.block_index for match in matches] == [0, 1]


def test_search_builds_bounded_context_excerpt(tmp_path: Path) -> None:
    text = "prefix " * 30 + "needle" + " suffix" * 30
    opened = _opened_document(
        tmp_path,
        [TextBlock(block_index=0, text=text)],
    )

    match = search_text(opened, "needle", excerpt_chars=60)[0]

    assert "needle" in match.excerpt
    assert match.excerpt.startswith("...")
    assert match.excerpt.endswith("...")
    assert len(match.excerpt) <= 66


def test_search_returns_empty_for_blank_or_missing_query(
    multi_page_pdf: Path,
) -> None:
    opened = open_pdf(multi_page_pdf)

    assert search_text(opened, "") == []
    assert search_text(opened, "   ") == []
    assert search_text(opened, "not in this paper") == []


def test_search_rejects_non_positive_excerpt_size(multi_page_pdf: Path) -> None:
    opened = open_pdf(multi_page_pdf)

    with pytest.raises(ValueError, match="excerpt_chars"):
        search_text(opened, "page", excerpt_chars=0)


def _opened_document(tmp_path: Path, blocks: list[TextBlock]) -> OpenedDocument:
    path = tmp_path / "search-model.pdf"
    return OpenedDocument(
        document=Document(
            id="search-document",
            title="Search model",
            authors=[],
            source_type="pdf",
            path=path,
            num_pages=1,
        ),
        pages=(Page(page_number=1, text="", blocks=blocks),),
        max_size_bytes=1024,
    )
