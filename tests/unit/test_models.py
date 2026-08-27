"""Tests for the M0 shared data models."""

from dataclasses import is_dataclass
from datetime import UTC
from pathlib import Path

from researchmind.models import (
    Conversation,
    Document,
    KnowledgeNote,
    Message,
    Page,
    ReadingSelection,
    ResearchContext,
    TextBlock,
)


def test_all_shared_models_are_dataclasses() -> None:
    model_types = (
        Document,
        Page,
        TextBlock,
        ReadingSelection,
        ResearchContext,
        Conversation,
        Message,
        KnowledgeNote,
    )

    assert all(is_dataclass(model_type) for model_type in model_types)


def test_mutable_defaults_are_not_shared() -> None:
    first_page = Page(page_number=1, text="first")
    second_page = Page(page_number=2, text="second")
    first_conversation = Conversation(document_id="doc-1")
    second_conversation = Conversation(document_id="doc-2")
    first_note = KnowledgeNote(title="First", source="pdf")
    second_note = KnowledgeNote(title="Second", source="pdf")

    first_page.blocks.append(TextBlock(block_index=0, text="block"))
    first_conversation.messages.append(
        Message(role="user", task="followup", content="Why?")
    )
    first_note.tags.append("optimization")

    assert second_page.blocks == []
    assert second_conversation.messages == []
    assert second_note.tags == []


def test_model_defaults_are_traceable_and_timezone_aware() -> None:
    document = Document(
        id="doc-1",
        title="Example Paper",
        authors=["Ada Researcher"],
        source_type="pdf",
        path=Path("paper.pdf"),
        num_pages=3,
    )
    selection = ReadingSelection(text="selected text")
    context = ResearchContext(
        selected_text=selection.text,
        surrounding_text="nearby text",
        document_id=document.id,
        document_title=document.title,
        author=document.authors[0],
        source=document.source_type,
        user_question="What does this mean?",
        page_number=1,
    )
    note = KnowledgeNote(
        title="Captured idea",
        source=document.title,
        authors=document.authors.copy(),
        page_number=context.page_number,
        selected_text=context.selected_text,
    )

    assert selection.source_type == "pdf"
    assert context.conversation_history == []
    assert note.selected_text == "selected text"
    assert selection.created_at.tzinfo is UTC
    assert note.created_at.tzinfo is UTC
