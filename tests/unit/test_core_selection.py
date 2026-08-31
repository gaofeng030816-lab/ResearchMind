"""Tests for pure reading-selection location rules."""

import pytest

from researchmind.core.selection import locate_selection, select_text_block
from researchmind.models import Page, TextBlock


def test_locate_selection_prefers_current_page_then_block() -> None:
    pages = [
        Page(
            page_number=1,
            text="Repeated phrase",
            blocks=[TextBlock(block_index=10, text="Repeated phrase")],
        ),
        Page(
            page_number=2,
            text="Repeated phrase",
            blocks=[
                TextBlock(
                    block_index=20,
                    text="Repeated   phrase",
                    bbox=(10.0, 20.0, 30.0, 40.0),
                )
            ],
        ),
    ]

    selection = locate_selection(" repeated phrase ", pages, current_page=2)

    assert selection.text == "repeated phrase"
    assert selection.locator == {
        "page_number": 2,
        "block_index": 20,
        "bbox": (10.0, 20.0, 30.0, 40.0),
    }


def test_locate_selection_searches_full_document_after_current_page() -> None:
    pages = [
        Page(
            page_number=1,
            text="Earlier result",
            blocks=[TextBlock(block_index=4, text="Earlier Result")],
        ),
        Page(
            page_number=2,
            text="Current page",
            blocks=[TextBlock(block_index=7, text="Current page")],
        ),
    ]

    selection = locate_selection("earlier result", pages, current_page=2)

    assert selection.locator == {"page_number": 1, "block_index": 4}


def test_unlocated_selection_remains_usable_without_locator() -> None:
    pages = [Page(page_number=1, text="Paper text", blocks=[])]

    selection = locate_selection("Manually entered formula", pages, current_page=1)

    assert selection.text == "Manually entered formula"
    assert selection.locator is None
    assert selection.source_type == "pdf"


def test_locate_selection_rejects_blank_text() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        locate_selection("  \n ", [], current_page=None)


def test_select_text_block_preserves_exact_text_and_source_bbox() -> None:
    page = Page(
        page_number=7,
        text="Formula fragment",
        blocks=[
            TextBlock(
                block_index=3,
                text="x^2 + y^2 = z^2",
                bbox=(11.0, 22.0, 33.0, 44.0),
                role="formula",
            )
        ],
    )

    selection = select_text_block(page, block_index=3)

    assert selection.text == "x^2 + y^2 = z^2"
    assert selection.locator == {
        "page_number": 7,
        "block_index": 3,
        "bbox": (11.0, 22.0, 33.0, 44.0),
    }


def test_select_text_block_rejects_unknown_block() -> None:
    page = Page(page_number=1, text="", blocks=[])

    with pytest.raises(ValueError, match="not found"):
        select_text_block(page, block_index=99)
