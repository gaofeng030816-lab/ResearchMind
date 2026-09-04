"""Tests for application-layer knowledge capture and Vault saving."""

from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    capture_code_knowledge,
    capture_knowledge,
    create_code_line_selection,
    create_code_symbol_selection,
    open_code_project,
    open_pdf,
    save_note_to_vault,
)
from researchmind.config import Settings
from researchmind.integration.obsidian import VaultConfigurationError
from researchmind.models import (
    CodeEvidenceReference,
    EvidenceLink,
    KnowledgeNote,
    Message,
    PaperEvidenceReference,
    ReadingSelection,
)


def test_capture_knowledge_preserves_selected_messages_and_provenance(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf, settings=Settings())
    selection = ReadingSelection(
        text="Second context block",
        locator={
            "page_number": 1,
            "block_index": 1,
            "bbox": (50.0, 100.0, 300.0, 130.0),
        },
    )
    messages = [
        Message(role="assistant", task="translate", content="第二个上下文块"),
        Message(
            role="assistant",
            task="convert:latex",
            content=r"x_{k+1}=x_k+\alpha d_k",
        ),
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
    assert note.source_type == "pdf"
    assert note.block_index == 1
    assert note.bbox == (50.0, 100.0, 300.0, 130.0)
    assert note.selected_text == "Second context block"
    assert note.translation == "第二个上下文块"
    assert note.latex == r"x_{k+1}=x_k+\alpha d_k"
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
    assert note.source_type == "pdf"
    assert note.block_index is None
    assert note.bbox is None
    assert note.selected_text is None
    assert note.translation is None
    assert note.latex is None
    assert note.question is None
    assert note.ai_explanation is None
    assert note.user_notes is None


def test_capture_knowledge_copies_confirmed_evidence_links(
    single_page_pdf: Path,
) -> None:
    opened = open_pdf(single_page_pdf, settings=Settings())
    link = EvidenceLink(
        paper=PaperEvidenceReference(
            document_id=opened.document.id,
            document_title=opened.document.title,
            evidence_kind="paper",
            page_number=1,
            block_index=1,
            bbox=(50.0, 100.0, 300.0, 130.0),
            excerpt="Second context block",
        ),
        code=CodeEvidenceReference(
            project_id="project-1",
            project_name="optimizer",
            relative_path="solver.py",
            start_line=1,
            end_line=2,
            excerpt="def step(x):\n    return x + 1",
            extraction_method="ast",
            symbol_kind="function",
            symbol_name="step",
        ),
        relation="implements",
        confidence=0.9,
        generation_method="user_confirmed",
    )
    links = [link]

    note = capture_knowledge(
        opened,
        ReadingSelection(
            text="Second context block",
            locator={"page_number": 1, "block_index": 1},
        ),
        [],
        "",
        [],
        evidence_links=links,
    )
    links.clear()

    assert note.evidence_links == [link]


def test_save_note_to_vault_requires_configured_root() -> None:
    with pytest.raises(VaultConfigurationError, match="OBSIDIAN_VAULT_PATH"):
        save_note_to_vault(
            KnowledgeNote(title="Test", source="Paper"),
            settings=Settings(obsidian_vault_path=None),
        )


def test_capture_code_knowledge_preserves_relative_provenance_and_explanation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private-code-project"
    root.mkdir()
    (root / "solver.py").write_text(
        "def step(value):\n    return value + 1\n",
        encoding="utf-8",
    )
    project = open_code_project(root)
    selection = create_code_symbol_selection(
        project,
        "solver.py",
        symbol_index=0,
    )
    response = Message(
        role="assistant",
        task="explain:code",
        content="This function advances the value by one.",
        selection_id=selection.id,
    )

    note = capture_code_knowledge(
        project,
        selection,
        response,
        question="  What does this function do?  ",
        response_question="What does this function do?",
        user_notes="  This is one update step.  ",
        tags=[" Reproduction ", "reproduction", "beginner"],
        title="  Solver update  ",
    )

    assert note.title == "Solver update"
    assert note.source == "private-code-project"
    assert note.source_type == "code"
    assert note.code_selection == selection
    assert note.selected_text == selection.text
    assert note.question == "What does this function do?"
    assert note.ai_explanation == "This function advances the value by one."
    assert note.user_notes == "This is one update step."
    assert note.tags == ["Reproduction", "beginner"]
    assert str(root) not in repr(note)


def test_capture_code_knowledge_rejects_stale_explanation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "code-project"
    root.mkdir()
    (root / "model.py").write_text("value = 1\n", encoding="utf-8")
    project = open_code_project(root)
    current = create_code_line_selection(
        project,
        "model.py",
        start_line=1,
        end_line=1,
    )
    stale = Message(
        role="assistant",
        task="explain:code",
        content="Stale response",
        selection_id="another-selection",
    )

    with pytest.raises(ValueError, match="current code selection"):
        capture_code_knowledge(
            project,
            current,
            stale,
            question="Explain this.",
            user_notes="",
            tags=[],
        )


def test_capture_code_knowledge_rejects_explanation_for_another_question(
    tmp_path: Path,
) -> None:
    root = tmp_path / "question-project"
    root.mkdir()
    (root / "model.py").write_text("value = 1\n", encoding="utf-8")
    project = open_code_project(root)
    selection = create_code_line_selection(
        project,
        "model.py",
        start_line=1,
        end_line=1,
    )
    response = Message(
        role="assistant",
        task="explain:code",
        content="It assigns one.",
        selection_id=selection.id,
    )

    with pytest.raises(ValueError, match="current code question"):
        capture_code_knowledge(
            project,
            selection,
            response,
            question="How is this used?",
            response_question="What does this assign?",
            user_notes="",
            tags=[],
        )
