"""Application-boundary tests for G4-B durable draft operations."""

from pathlib import Path

import pytest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.database import (
    LibraryConfirmationError,
    LibraryConflictError,
    LibraryImportError,
)
from researchmind.models import Message, UploadedFileData


def test_explicit_draft_and_evidence_persist_without_vault_write(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        obsidian_vault_path=vault,
    )
    draft = use_cases.create_note_draft(
        "Selected idea",
        body_markdown="## My understanding\n",
        settings=settings,
    )
    draft, evidence = use_cases.add_note_evidence(
        draft.id,
        kind="source_text",
        content="Only explicitly selected text.",
        source_label="Temporary PDF · page 1",
        origin="browser_selection",
        expected_draft_revision=1,
        locator={"page_number": 1},
        selection_id="selection-1",
        settings=settings,
    )

    reopened = use_cases.get_note_draft(draft.id, settings=settings)
    stored_evidence = use_cases.list_note_evidence(
        draft.id,
        settings=settings,
    )

    assert reopened == draft
    assert stored_evidence == [evidence]
    assert use_cases.note_evidence_source_state(
        evidence,
        settings=settings,
    ) == "detached"
    assert list(vault.rglob("*.md")) == []


def test_draft_update_and_delete_require_current_revision_and_consent(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    draft = use_cases.create_note_draft("Draft", settings=settings)
    updated = use_cases.update_note_draft(
        draft.id,
        title="Updated",
        body_markdown="# Updated\n",
        status="active",
        expected_revision=1,
        settings=settings,
    )

    with pytest.raises(LibraryConfirmationError, match="confirmation"):
        use_cases.delete_note_draft(
            draft.id,
            expected_revision=updated.revision,
            confirmed=False,
            settings=settings,
        )

    use_cases.delete_note_draft(
        draft.id,
        expected_revision=updated.revision,
        confirmed=True,
        settings=settings,
    )
    assert use_cases.list_note_drafts(settings=settings) == []


def test_note_use_cases_require_data_dir_and_reject_private_locator(
    tmp_path: Path,
) -> None:
    with pytest.raises(LibraryImportError, match="RESEARCHMIND_DATA_DIR"):
        use_cases.create_note_draft("Draft", settings=Settings())

    settings = Settings(researchmind_data_dir=tmp_path / "library")
    draft = use_cases.create_note_draft("Draft", settings=settings)
    with pytest.raises(ValueError, match="relative"):
        use_cases.add_note_evidence(
            draft.id,
            kind="code",
            content="print('safe')",
            source_label="Local code",
            origin="code_selection",
            expected_draft_revision=1,
            locator={"relative_path": "C:/private/project/main.py"},
            settings=settings,
        )


def test_managed_paper_selection_and_translation_are_explicit_snapshots(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        obsidian_vault_path=vault,
        target_language="zh-CN",
    )
    imported = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="paper.pdf",
            content=single_page_pdf.read_bytes(),
        ),
        settings=settings,
    )
    document = use_cases.open_library_paper(
        imported.entry.record.id,
        settings=settings,
    )
    selection = use_cases.create_selection(
        document,
        "ResearchMind introduction",
        current_page=1,
    )
    preview = use_cases.preview_selection_translation(
        selection,
        settings=settings,
    )
    translation = use_cases.bind_translation_to_selection(
        Message(
            role="assistant",
            task="translate",
            content="ResearchMind 简介",
        ),
        selection,
    )
    draft = use_cases.create_paper_note_draft(
        document,
        library_entry=imported.entry,
        settings=settings,
    )

    draft, source = use_cases.capture_reading_selection_evidence(
        draft,
        selection,
        document,
        library_entry=imported.entry,
        settings=settings,
    )
    draft, translated = use_cases.capture_translation_evidence(
        draft,
        selection,
        translation,
        document,
        library_entry=imported.entry,
        settings=settings,
    )

    assert preview.source_text == "ResearchMind introduction"
    assert preview.target_language == "zh-CN"
    assert preview.selection_id == translation.selection_id
    assert source.selection_id == translated.selection_id == preview.selection_id
    assert source.source_record_id == imported.entry.record.id
    assert source.source_asset_id == imported.entry.asset.id
    assert source.source_revision == imported.entry.asset.revision
    assert source.source_sha256 == imported.entry.asset.sha256
    assert source.locator["page_number"] == 1
    assert str(single_page_pdf) not in source.source_label
    assert use_cases.note_evidence_source_state(
        source,
        settings=settings,
    ) == "current"
    assert [item.kind for item in use_cases.list_note_evidence(
        draft.id,
        settings=settings,
    )] == ["source_text", "translation"]
    assert list(vault.rglob("*.md")) == []

    with pytest.raises(LibraryConflictError, match="already"):
        use_cases.capture_reading_selection_evidence(
            draft,
            selection,
            document,
            library_entry=imported.entry,
            settings=settings,
        )

    draft = use_cases.remove_note_evidence(
        draft.id,
        translated.id,
        expected_draft_revision=draft.revision,
        settings=settings,
    )
    assert [item.id for item in use_cases.list_note_evidence(
        draft.id,
        settings=settings,
    )] == [source.id]


def test_paper_capture_rejects_mismatched_managed_revision(
    tmp_path: Path,
    single_page_pdf: Path,
    multi_page_pdf: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    first = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="first.pdf",
            content=single_page_pdf.read_bytes(),
        ),
        settings=settings,
    )
    document = use_cases.open_library_paper(
        first.entry.record.id,
        settings=settings,
    )
    newer = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="second.pdf",
            content=multi_page_pdf.read_bytes(),
        ),
        record_id=first.entry.record.id,
        settings=settings,
    )

    with pytest.raises(LibraryConflictError, match="no longer matches"):
        use_cases.create_paper_note_draft(
            document,
            library_entry=newer.entry,
            settings=settings,
        )


def test_draft_edit_preview_and_vault_save_are_four_explicit_steps(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        obsidian_vault_path=vault,
        obsidian_subdirectory="ResearchMind",
    )
    draft = use_cases.create_note_draft("Initial title", settings=settings)
    draft, evidence = use_cases.add_note_evidence(
        draft.id,
        kind="source_text",
        content="Only this selected sentence.",
        source_label="Detached paper · page 1",
        origin="user_entry",
        expected_draft_revision=draft.revision,
        locator={"page_number": 1},
        settings=settings,
    )
    assert list(vault.rglob("*.md")) == []

    draft = use_cases.update_note_draft(
        draft.id,
        title="Edited title",
        body_markdown="## 我的理解\n\n这是显式保存的正文。",
        status="active",
        expected_revision=draft.revision,
        settings=settings,
    )
    assert list(vault.rglob("*.md")) == []

    preview = use_cases.preview_note_draft_markdown(
        draft.id,
        expected_revision=draft.revision,
        settings=settings,
    )
    assert preview.included_evidence_count == 1
    assert "这是显式保存的正文" in preview.markdown
    assert evidence.source_label in preview.markdown
    assert "detached（未绑定可复查的资料库修订）" in preview.markdown
    assert list(vault.rglob("*.md")) == []

    first = use_cases.save_note_draft_to_vault(preview, settings=settings)
    second = use_cases.save_note_draft_to_vault(preview, settings=settings)

    assert first != second
    assert first.read_bytes() == preview.markdown.encode("utf-8")
    assert second.read_bytes() == preview.markdown.encode("utf-8")


def test_vault_save_rejects_stale_or_tampered_draft_preview(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        obsidian_vault_path=vault,
    )
    draft = use_cases.create_note_draft("Draft", settings=settings)
    preview = use_cases.preview_note_draft_markdown(
        draft.id,
        expected_revision=draft.revision,
        settings=settings,
    )
    updated = use_cases.update_note_draft(
        draft.id,
        title="Changed after preview",
        body_markdown="",
        status="active",
        expected_revision=draft.revision,
        settings=settings,
    )

    with pytest.raises(LibraryConflictError, match="changed before preview"):
        use_cases.save_note_draft_to_vault(preview, settings=settings)

    fresh = use_cases.preview_note_draft_markdown(
        updated.id,
        expected_revision=updated.revision,
        settings=settings,
    )
    tampered = fresh.__class__(
        **{**fresh.__dict__, "markdown": fresh.markdown + "tampered\n"}
    )
    with pytest.raises(LibraryConflictError, match="content changed"):
        use_cases.save_note_draft_to_vault(tampered, settings=settings)
    assert list(vault.rglob("*.md")) == []


def test_vault_save_requires_new_preview_when_source_becomes_stale(
    tmp_path: Path,
    single_page_pdf: Path,
    multi_page_pdf: Path,
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        obsidian_vault_path=vault,
    )
    imported = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="paper.pdf",
            content=single_page_pdf.read_bytes(),
        ),
        settings=settings,
    )
    document = use_cases.open_library_paper(
        imported.entry.record.id,
        settings=settings,
    )
    selection = use_cases.create_selection(
        document,
        "ResearchMind introduction",
        current_page=1,
    )
    draft = use_cases.create_paper_note_draft(
        document,
        library_entry=imported.entry,
        settings=settings,
    )
    draft, _evidence = use_cases.capture_reading_selection_evidence(
        draft,
        selection,
        document,
        library_entry=imported.entry,
        settings=settings,
    )
    preview = use_cases.preview_note_draft_markdown(
        draft.id,
        expected_revision=draft.revision,
        settings=settings,
    )
    assert "current（仍匹配当前资料库修订）" in preview.markdown

    use_cases.import_pdf_to_library(
        UploadedFileData(
            name="paper-v2.pdf",
            content=multi_page_pdf.read_bytes(),
        ),
        record_id=imported.entry.record.id,
        settings=settings,
    )

    with pytest.raises(LibraryConflictError, match="source state changed"):
        use_cases.save_note_draft_to_vault(preview, settings=settings)
    assert list(vault.rglob("*.md")) == []
