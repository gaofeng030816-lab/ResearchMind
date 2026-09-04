"""Tests for pure ResearchContext assembly."""

from pathlib import Path

import pytest

from researchmind.core.research_context import build_research_context
from researchmind.models import (
    Conversation,
    Document,
    Message,
    Page,
    ReadingSelection,
    TextBlock,
)


def test_context_uses_located_page_adjacent_blocks_metadata_and_question() -> None:
    page = Page(
        page_number=2,
        text="before anchor after",
        blocks=[
            TextBlock(block_index=1, text="before context"),
            TextBlock(block_index=8, text="the anchor concept is important"),
            TextBlock(block_index=9, text="after context"),
        ],
    )
    selection = ReadingSelection(
        text="anchor concept",
        locator={"page_number": 2, "block_index": 8},
    )

    context = build_research_context(
        selection,
        _document(),
        [page],
        user_question="  Why here?  ",
        context_token_budget=12,
        history_token_budget=10,
    )

    assert context.selected_text == "anchor concept"
    assert "anchor concept" in context.surrounding_text
    assert len(context.surrounding_text) <= 48
    assert context.page_number == 2
    assert context.document_title == "Optimization Paper"
    assert context.author == "Ada Researcher, Grace Scientist"
    assert context.source == "pdf"
    assert context.user_question == "Why here?"


def test_context_falls_back_to_page_text_when_block_reference_is_unavailable() -> None:
    page = Page(page_number=1, text="0123456789 full page fallback", blocks=[])
    selection = ReadingSelection(text="manual", locator={"page_number": 1})

    context = build_research_context(
        selection,
        _document(),
        [page],
        user_question="Explain",
        context_token_budget=2,
        history_token_budget=2,
    )

    assert context.surrounding_text == "01234567"


def test_unlocated_selection_does_not_attach_arbitrary_document_text() -> None:
    selection = ReadingSelection(text="manual formula")

    context = build_research_context(
        selection,
        _document(),
        [Page(page_number=1, text="unrelated page")],
        user_question="Explain",
        context_token_budget=10,
        history_token_budget=10,
    )

    assert context.page_number is None
    assert context.surrounding_text == ""
    assert context.section_heading == ""
    assert context.related_caption == ""
    assert context.related_formula == ""


def test_context_adds_nearest_section_heading_and_local_caption() -> None:
    pages = [
        Page(
            page_number=1,
            text="3 Results",
            blocks=[TextBlock(block_index=1, text="3 Results", role="heading")],
        ),
        Page(
            page_number=2,
            text="Evidence block Figure 2. Accuracy by training step",
            blocks=[
                TextBlock(block_index=4, text="Earlier evidence"),
                TextBlock(block_index=8, text="The selected evidence is decisive."),
                TextBlock(
                    block_index=9,
                    text="Figure 2. Accuracy by training step",
                    role="caption",
                ),
            ],
        ),
    ]
    selection = ReadingSelection(
        text="selected evidence",
        locator={"page_number": 2, "block_index": 8},
    )

    context = build_research_context(
        selection,
        _document(),
        pages,
        user_question="What does the evidence show?",
        context_token_budget=20,
        history_token_budget=10,
    )

    assert context.section_heading == "3 Results"
    assert context.related_caption == "Figure 2. Accuracy by training step"


def test_context_does_not_attach_a_distant_caption() -> None:
    page = Page(
        page_number=1,
        text="Figure 1 caption filler filler selected text",
        blocks=[
            TextBlock(block_index=1, text="Figure 1. Earlier result", role="caption"),
            TextBlock(block_index=2, text="filler one"),
            TextBlock(block_index=3, text="filler two"),
            TextBlock(block_index=4, text="filler three"),
            TextBlock(block_index=5, text="selected text"),
        ],
    )
    selection = ReadingSelection(
        text="selected text",
        locator={"page_number": 1, "block_index": 5},
    )

    context = build_research_context(
        selection,
        _document(),
        [page],
        user_question="Explain",
        context_token_budget=20,
        history_token_budget=10,
    )

    assert context.related_caption == ""


def test_context_adds_nearby_formula_and_ignores_running_title_header() -> None:
    document = _document()
    pages = [
        Page(
            page_number=1,
            text="2 Proposed Method",
            blocks=[
                TextBlock(
                    block_index=1,
                    text="2 Proposed Method",
                    role="heading",
                )
            ],
        ),
        Page(
            page_number=2,
            text="4 Optimization Paper x(t1) = x(t0) + f(x, t) selected claim",
            blocks=[
                TextBlock(
                    block_index=2,
                    text="4 Optimization Paper",
                    role="heading",
                ),
                TextBlock(
                    block_index=3,
                    text="x(t1) = x(t0) + f(x, t)",
                    role="formula",
                ),
                TextBlock(
                    block_index=4,
                    text="y(t1) = decode(x(t1))",
                    role="formula",
                ),
                TextBlock(block_index=5, text="selected claim"),
            ],
        ),
    ]
    selection = ReadingSelection(
        text="selected claim",
        locator={"page_number": 2, "block_index": 5},
    )

    context = build_research_context(
        selection,
        document,
        pages,
        user_question="Explain",
        context_token_budget=30,
        history_token_budget=10,
    )

    assert context.section_heading == "2 Proposed Method"
    assert context.related_formula == (
        "x(t1) = x(t0) + f(x, t)\ny(t1) = decode(x(t1))"
    )


def test_context_does_not_attach_a_distant_formula() -> None:
    page = Page(
        page_number=1,
        text="formula filler filler selected",
        blocks=[
            TextBlock(block_index=1, text="x = y", role="formula"),
            TextBlock(block_index=2, text="filler one"),
            TextBlock(block_index=3, text="filler two"),
            TextBlock(block_index=4, text="filler three"),
            TextBlock(block_index=5, text="selected"),
        ],
    )
    selection = ReadingSelection(
        text="selected",
        locator={"page_number": 1, "block_index": 5},
    )

    context = build_research_context(
        selection,
        _document(),
        [page],
        user_question="Explain",
        context_token_budget=20,
        history_token_budget=10,
    )

    assert context.related_formula == ""


def test_context_trims_history_and_rejects_conversation_for_other_document() -> None:
    document = _document()
    selection = ReadingSelection(text="x", locator={"page_number": 1})
    conversation = Conversation(
        document_id=document.id,
        messages=[
            Message(role="user", task="followup", content="old question"),
            Message(role="assistant", task="followup", content="new answer"),
        ],
    )

    context = build_research_context(
        selection,
        document,
        [Page(page_number=1, text="page")],
        user_question="Next?",
        conversation=conversation,
        context_token_budget=10,
        history_token_budget=3,
    )

    assert [message.content for message in context.conversation_history] == ["new answer"]

    conversation.document_id = "other-document"
    with pytest.raises(ValueError, match="does not belong"):
        build_research_context(
            selection,
            document,
            [],
            user_question="Next?",
            conversation=conversation,
            context_token_budget=10,
            history_token_budget=10,
        )


def _document() -> Document:
    return Document(
        id="document-1",
        title="Optimization Paper",
        authors=["Ada Researcher", "Grace Scientist"],
        source_type="pdf",
        path=Path("paper.pdf"),
        num_pages=2,
    )
