"""Pure assembly of task-bounded ResearchContext values."""

from __future__ import annotations

from collections.abc import Sequence

from researchmind.core.conversation import (
    APPROXIMATE_CHARS_PER_TOKEN,
    trim_conversation_history,
)
from researchmind.models import (
    Conversation,
    Document,
    Page,
    ReadingSelection,
    ResearchContext,
)


CAPTION_BLOCK_DISTANCE = 2
MAX_SECTION_HEADING_CHARS = 160
MAX_RELATED_CAPTION_CHARS = 500


def build_research_context(
    selection: ReadingSelection,
    document: Document,
    pages: Sequence[Page],
    *,
    user_question: str,
    conversation: Conversation | None = None,
    context_token_budget: int,
    history_token_budget: int,
) -> ResearchContext:
    """Build the minimum current-paper context for one LLM-backed task."""

    _validate_token_budget(context_token_budget)
    if conversation is not None and conversation.document_id != document.id:
        raise ValueError("Conversation does not belong to the opened document.")

    page_number = _locator_int(selection, "page_number")
    section_heading, related_caption = _context_landmarks(
        selection,
        pages,
        page_number=page_number,
    )
    history = [] if conversation is None else conversation.messages
    return ResearchContext(
        selected_text=selection.text,
        surrounding_text=_surrounding_text(
            selection,
            pages,
            page_number=page_number,
            token_budget=context_token_budget,
        ),
        page_number=page_number,
        section_heading=section_heading,
        related_caption=related_caption,
        document_id=document.id,
        document_title=document.title,
        author=", ".join(document.authors),
        source=document.source_type,
        user_question=user_question.strip(),
        conversation_history=trim_conversation_history(
            history,
            token_budget=history_token_budget,
        ),
    )


def _context_landmarks(
    selection: ReadingSelection,
    pages: Sequence[Page],
    *,
    page_number: int | None,
) -> tuple[str, str]:
    if page_number is None:
        return "", ""

    page = next((item for item in pages if item.page_number == page_number), None)
    if page is None or not page.blocks:
        return "", ""

    block_index = _locator_int(selection, "block_index")
    anchor_position = next(
        (
            index
            for index, block in enumerate(page.blocks)
            if block.block_index == block_index
        ),
        None,
    )
    if anchor_position is None:
        return "", ""

    section_heading = _nearest_section_heading(
        pages,
        page_number=page_number,
        anchor_position=anchor_position,
    )
    related_caption = _nearest_caption(page, anchor_position=anchor_position)
    return (
        section_heading[:MAX_SECTION_HEADING_CHARS],
        related_caption[:MAX_RELATED_CAPTION_CHARS],
    )


def _nearest_section_heading(
    pages: Sequence[Page],
    *,
    page_number: int,
    anchor_position: int,
) -> str:
    eligible_pages = sorted(
        (page for page in pages if page.page_number <= page_number),
        key=lambda page: page.page_number,
        reverse=True,
    )
    for page in eligible_pages:
        end = anchor_position if page.page_number == page_number else len(page.blocks)
        for block in reversed(page.blocks[:end]):
            if block.role == "heading":
                return block.text
    return ""


def _nearest_caption(page: Page, *, anchor_position: int) -> str:
    candidates = (
        (abs(index - anchor_position), index, block.text)
        for index, block in enumerate(page.blocks)
        if block.role == "caption"
        and abs(index - anchor_position) <= CAPTION_BLOCK_DISTANCE
    )
    nearest = min(candidates, default=None)
    return "" if nearest is None else nearest[2]


def _surrounding_text(
    selection: ReadingSelection,
    pages: Sequence[Page],
    *,
    page_number: int | None,
    token_budget: int,
) -> str:
    if page_number is None:
        return ""

    page = next((item for item in pages if item.page_number == page_number), None)
    if page is None:
        return ""

    max_chars = token_budget * APPROXIMATE_CHARS_PER_TOKEN
    block_index = _locator_int(selection, "block_index")
    anchor_position = next(
        (
            index
            for index, block in enumerate(page.blocks)
            if block.block_index == block_index
        ),
        None,
    )
    if anchor_position is None or not page.blocks:
        return page.text[:max_chars]

    joined_text, spans = _join_blocks_with_spans(page)
    anchor_start, anchor_end = spans[anchor_position]
    selected_position = page.blocks[anchor_position].text.casefold().find(
        selection.text.casefold()
    )
    if selected_position >= 0:
        focus_start = anchor_start + selected_position
        focus_end = focus_start + len(selection.text)
    else:
        focus_start, focus_end = anchor_start, anchor_end

    return _window_around_span(
        joined_text,
        focus_start=focus_start,
        focus_end=focus_end,
        max_chars=max_chars,
    )


def _join_blocks_with_spans(page: Page) -> tuple[str, list[tuple[int, int]]]:
    pieces: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    for block in page.blocks:
        if pieces:
            pieces.append("\n\n")
            cursor += 2
        start = cursor
        pieces.append(block.text)
        cursor += len(block.text)
        spans.append((start, cursor))
    return "".join(pieces), spans


def _window_around_span(
    text: str,
    *,
    focus_start: int,
    focus_end: int,
    max_chars: int,
) -> str:
    if len(text) <= max_chars:
        return text

    focus_length = focus_end - focus_start
    if focus_length >= max_chars:
        return text[focus_start : focus_start + max_chars]

    surrounding_chars = max_chars - focus_length
    start = max(focus_start - surrounding_chars // 2, 0)
    end = min(start + max_chars, len(text))
    start = max(end - max_chars, 0)
    return text[start:end]


def _locator_int(selection: ReadingSelection, key: str) -> int | None:
    if selection.locator is None:
        return None
    value = selection.locator.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _validate_token_budget(token_budget: int) -> None:
    if isinstance(token_budget, bool) or not isinstance(token_budget, int):
        raise ValueError("Token budget must be a positive integer.")
    if token_budget <= 0:
        raise ValueError("Token budget must be a positive integer.")
