"""Pure rules for locating user-selected text in extracted document pages."""

from __future__ import annotations

from collections.abc import Sequence

from researchmind.models import Page, ReadingSelection


def locate_selection(
    text: str,
    pages: Sequence[Page],
    *,
    current_page: int | None = None,
) -> ReadingSelection:
    """Locate text on the current page first, then across the document.

    A failed location is an allowed product outcome: the returned selection keeps
    the user's text and has no locator, so translation and explanation can still
    proceed.
    """

    selected_text = text.strip()
    normalized_selection = _normalize_for_match(selected_text)
    if not normalized_selection:
        raise ValueError("Selected text must not be blank.")

    ordered_pages = _pages_in_search_order(pages, current_page=current_page)
    for page in ordered_pages:
        for block in page.blocks:
            if normalized_selection in _normalize_for_match(block.text):
                return ReadingSelection(
                    text=selected_text,
                    source_type="pdf",
                    locator={
                        "page_number": page.page_number,
                        "block_index": block.block_index,
                    },
                )

    return ReadingSelection(text=selected_text, source_type="pdf")


def _pages_in_search_order(
    pages: Sequence[Page],
    *,
    current_page: int | None,
) -> list[Page]:
    current = next(
        (page for page in pages if page.page_number == current_page),
        None,
    )
    if current is None:
        return list(pages)
    return [current, *(page for page in pages if page is not current)]


def _normalize_for_match(text: str) -> str:
    return " ".join(text.split()).casefold()
