"""Tests for application-layer knowledge capture and Vault saving."""

from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    capture_knowledge,
    open_pdf,
    save_note_to_vault,
)
from researchmind.config import Settings
from researchmind.integration.obsidian import VaultConfigurationError
from researchmind.models import KnowledgeNote, Message, ReadingSelection


def test_capture_knowledge_preserves_selected_messages_and_provenance(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf, settings=Settings())
    selection = ReadingSelection(
        text="Second context block",
        locator={"page_number": 1, "block_index": 1},
    )
    messages = [
        Message(role="assistant", task="translate", content="第二个上下文块"),
        Message(role="user", task="explain:contextual", content="Why relevant?"),
        Message(role="assistant", task="explain:contextual", content="Evidence."),
        Message(role="user", task="followup", content="Why next?"),
        Message(role="assistant", task="followup", content="Dependency."),
    ]

    note = capture_knowledge(
        opened,
        selection,
        messages,
        "  My understanding.  ",
        [" Optimization ", "optimization", "algorithm", ""],
        title="  Evidence chain  ",
    )

    assert note.title == "Evidence chain"
    assert note.source == "Fixture Research Paper"
    assert note.authors == ["Ada Researcher", "Grace Scientist"]
    assert note.page_number == 1
    assert note.selected_text == "Second context block"
    assert note.translation == "第二个上下文块"
    assert note.question == "Why relevant?\n\nWhy next?"
    assert note.ai_explanation == "Evidence.\n\nDependency."
    assert note.user_notes == "My understanding."
    assert note.tags == ["Optimization", "algorithm"]


def test_capture_knowledge_handles_optional_selection_and_title_fallback(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf, settings=Settings())

    note = capture_knowledge(opened, None, [], " ", [], title=None)

    assert note.title == "Fixture Research Paper"
    assert note.page_number is None
    assert note.selected_text is None
    assert note.translation is None
    assert note.question is None
    assert note.ai_explanation is None
    assert note.user_notes is None


def test_save_note_to_vault_requires_configured_root() -> None:
    with pytest.raises(VaultConfigurationError, match="OBSIDIAN_VAULT_PATH"):
        save_note_to_vault(
            KnowledgeNote(title="Test", source="Paper"),
            settings=Settings(obsidian_vault_path=None),
        )
