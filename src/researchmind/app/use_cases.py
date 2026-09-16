"""Application API coordinating ResearchMind domain and infrastructure modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from typing import Literal
from uuid import uuid4

from researchmind.code import (
    CodeProjectError,
    apply_code_change as code_apply_code_change,
    code_file_from_proposal,
    code_file_from_recovery,
    open_code_project as code_open_code_project,
    read_code_snapshot,
    rollback_code_change as code_rollback_code_change,
)
from researchmind.config import ConfigError, Settings, load_settings
from researchmind.database import (
    LibraryBackupError,
    LibraryConfirmationError,
    LibraryConflictError,
    LibraryDatabaseError,
    LibraryError,
    LibraryImportError,
    LibraryNotFoundError,
    LibraryRepository,
    ManagedStorage,
    NoteDraftRepository,
    create_library_backup,
    initialize_database,
    prepare_library_paths,
    restore_library_backup,
)
from researchmind.core import (
    MAX_ASSISTANT_LLM_CALLS,
    MAX_ASSISTANT_TOOL_CALLS,
    add_evidence_link as core_add_evidence_link,
    build_code_change_proposal,
    build_code_context,
    build_research_context,
    create_read_only_assistant_session,
    create_user_confirmed_evidence_link,
    get_code_file as core_get_code_file,
    locate_selection,
    record_assistant_final_step,
    record_assistant_tool_step,
    replace_code_project_file,
    select_code_lines,
    select_code_symbol,
    select_text_block,
    summarize_code_project,
    stop_read_only_assistant_session,
    validate_evidence_snapshot,
    validate_note_draft,
    tool_output_stop_reason,
    tool_request_stop_reason,
    validate_code_change_snapshot,
)
from researchmind.core.conversation import APPROXIMATE_CHARS_PER_TOKEN
from researchmind.llm import (
    ChatMessage,
    FormulaRecognizer,
    LlmError,
    LlmProvider,
    build_algorithm_prompt,
    build_code_change_prompt,
    build_code_explanation_prompt,
    build_concept_prompt,
    build_contextual_prompt,
    build_followup_prompt,
    build_latex_prompt,
    build_math_prompt,
    build_read_only_assistant_prompt,
    create_llm_provider,
    create_formula_recognizer,
    parse_assistant_action,
    parse_code_replacement,
    parse_latex_response,
)
from researchmind.maintenance import (
    diagnose_configuration as maintenance_diagnose_configuration,
)
from researchmind.integration.obsidian import (
    ObsidianError,
    VaultConfigurationError,
    render_markdown,
    render_note_draft_markdown,
    write_markdown_to_vault,
    write_note_to_vault,
)
from researchmind.integration.zotero import (
    ZoteroError,
    ZoteroLocalApi,
)
from researchmind.models import (
    AssistantToolName,
    AssistantToolResult,
    BoundingBox,
    CodeChangeAuditAction,
    CodeChangeAuditEvent,
    CodeChangeAuditStatus,
    CodeChangeProposal,
    CodeChangeReceipt,
    CodeChangeRollbackReceipt,
    CodeContext,
    CodeFile,
    CodeProject,
    CodeProjectSummary,
    CodeSelection,
    Conversation,
    ConfigurationReport,
    EvidenceLink,
    EvidenceKind,
    EvidenceOrigin,
    EvidenceSnapshot,
    EvidenceSourceState,
    EvidenceRelation,
    FormulaCrop,
    FormulaRecognitionCandidate,
    FormulaRegion,
    FormulaTransferPreview,
    KnowledgeNote,
    LibraryEntry,
    LibraryBackupResult,
    LibraryImportResult,
    LibraryItemKind,
    LibraryRecord,
    LibraryRestoreResult,
    Message,
    NoteDraft,
    NoteDraftPreview,
    NoteDraftStatus,
    Page,
    ReadingSelection,
    ResearchContext,
    ReadOnlyAssistantSession,
    AssetReference,
    UploadedFileData,
    PaperEvidenceKind,
    ZoteroAttachment,
    ZoteroBrowseResult,
    ZoteroItemDetails,
    ZoteroSourceLink,
)
from researchmind.pdf import (
    DEFAULT_PDF_VIEWER_MAX_SIZE_BYTES,
    MAX_FORMULA_CROP_BYTES,
    MAX_FORMULA_CROP_PIXELS,
    OpenedDocument,
    PdfError,
    PdfViewerError,
    PdfViewerSource,
    TextMatch,
    extract_page,
    detect_formula_regions as pdf_detect_formula_regions,
    load_pdf_viewer_source as pdf_load_pdf_viewer_source,
    open_pdf as pdf_open_pdf,
    render_figure_images,
    render_page_image,
    render_formula_crop as pdf_render_formula_crop,
    search_text as pdf_search_text,
)
from researchmind.translation import (
    LlmTranslationProvider,
    TranslationError,
    TranslationProvider,
    prepare_translation_request,
    translate_text,
)


ExplainMode = Literal["concept", "math", "algorithm", "contextual"]
MIN_TEXT_COVERAGE_RATIO = 0.1
USER_FACING_ERRORS = (
    CodeProjectError,
    ConfigError,
    LibraryError,
    PdfError,
    LlmError,
    TranslationError,
    ObsidianError,
    ZoteroError,
    ValueError,
)


def get_configuration_report() -> ConfigurationReport:
    """Return a local, non-secret configuration report without network calls."""

    return maintenance_diagnose_configuration()


@dataclass(frozen=True)
class PageView:
    """One rendered page plus its extracted, selectable text."""

    page: Page
    image_png: bytes
    zoom: float
    figure_images: tuple[bytes, ...] = ()


@dataclass(frozen=True)
class DocumentTextCoverage:
    """Document-level visibility into PDF text extraction quality."""

    total_pages: int
    pages_with_text: int

    @property
    def ratio(self) -> float:
        return (
            0.0
            if self.total_pages == 0
            else self.pages_with_text / self.total_pages
        )

    @property
    def is_limited(self) -> bool:
        return self.ratio <= MIN_TEXT_COVERAGE_RATIO


@dataclass(frozen=True)
class ContextEvidencePreview:
    """Read-only evidence and request-size preview for one LLM call."""

    document_title: str
    author: str
    source_type: str
    page_number: int | None
    block_index: int | None
    bbox: BoundingBox | None
    selected_text: str
    section_heading: str
    related_caption: str
    related_formula: str
    surrounding_text: str
    user_question: str
    history_message_count: int
    request_character_count: int
    approximate_request_tokens: int


@dataclass(frozen=True)
class CodeContextEvidencePreview:
    """Read-only code evidence and request-size preview for one LLM call."""

    project_name: str
    source_type: str
    relative_path: str
    start_line: int
    end_line: int
    symbol_kind: str | None
    symbol_name: str | None
    extraction_method: str
    selected_code: str
    surrounding_code: str
    user_question: str
    request_character_count: int
    approximate_request_tokens: int


@dataclass(frozen=True)
class CodeChangeApplication:
    """One applied change plus the refreshed in-memory project model."""

    project: CodeProject
    receipt: CodeChangeReceipt


@dataclass(frozen=True)
class CodeChangeRollbackApplication:
    """One rollback plus the refreshed in-memory project model."""

    project: CodeProject
    receipt: CodeChangeRollbackReceipt


@dataclass(frozen=True)
class TranslationTransferPreview:
    """Exact, local-only fields that one explicit translation will send."""

    source_text: str
    target_language: str
    selection_id: str


_EXPLANATION_BUILDERS = {
    "concept": build_concept_prompt,
    "math": build_math_prompt,
    "algorithm": build_algorithm_prompt,
    "contextual": build_contextual_prompt,
}

_DEFAULT_QUESTIONS = {
    "concept": "Explain this concept.",
    "math": "Explain this mathematical material.",
    "algorithm": "Explain this algorithm.",
    "contextual": "Explain this selection in its paper context.",
}
_LATEX_QUESTION = "Convert the selected mathematical material to LaTeX."


def is_library_configured(
    *,
    settings: Settings | None = None,
) -> bool:
    """Return whether the explicit V3 durable-data root is configured."""

    resolved_settings = settings or load_settings()
    return resolved_settings.researchmind_data_dir is not None


def is_zotero_local_api_enabled(
    *,
    settings: Settings | None = None,
) -> bool:
    """Return whether the user explicitly enabled loopback Zotero reads."""

    resolved_settings = settings or load_settings()
    return resolved_settings.zotero_local_api_enabled


def browse_zotero_items(
    *,
    query: str = "",
    limit: int = 20,
    settings: Settings | None = None,
    client: ZoteroLocalApi | None = None,
) -> ZoteroBrowseResult:
    """Probe Zotero and fetch one explicit, session-only personal list."""

    _require_zotero_enabled(settings)
    api = client or ZoteroLocalApi()
    connection = api.probe()
    items = api.list_recent_items(
        connection,
        query=query,
        limit=limit,
    )
    return ZoteroBrowseResult(
        connection=connection,
        items=tuple(items),
    )


def zotero_attachment_approval_scope(
    *, settings: Settings | None = None,
) -> str | None:
    """Bind explicit copy consent to configured root without exposing its path."""
    resolved = settings or load_settings()
    if (
        os.name != "nt"
        or not resolved.zotero_local_api_enabled
        or not resolved.zotero_attachment_root
    ):
        return None
    return sha256(resolved.zotero_attachment_root.encode("utf-8")).hexdigest()


def get_zotero_item_details(
    browse_result: ZoteroBrowseResult,
    item_key: str,
    *,
    settings: Settings | None = None,
    client: ZoteroLocalApi | None = None,
) -> ZoteroItemDetails:
    """Fetch PDF children only for the explicitly selected browse item."""

    _require_zotero_enabled(settings)
    item = next(
        (
            candidate
            for candidate in browse_result.items
            if candidate.item_key == item_key
        ),
        None,
    )
    if item is None:
        raise ValueError("The selected Zotero item is not in this browse result.")
    _validate_zotero_identity(browse_result, item.server_id)
    api = client or ZoteroLocalApi()
    attachments = api.list_pdf_attachments(
        browse_result.connection,
        item,
    )
    return ZoteroItemDetails(
        connection=browse_result.connection,
        item=item,
        attachments=tuple(attachments),
    )


def get_zotero_source_link(
    record_id: str,
    *,
    settings: Settings | None = None,
) -> ZoteroSourceLink | None:
    """Read a durable Zotero link without contacting Zotero."""

    repository, _storage = _library_infrastructure(settings)
    try:
        return repository.get_zotero_link(record_id)
    except LibraryNotFoundError:
        return None


def link_zotero_item_to_paper(
    record_id: str,
    details: ZoteroItemDetails,
    *,
    attachment_key: str | None = None,
    confirmed: bool,
    settings: Settings | None = None,
) -> ZoteroSourceLink:
    """Persist one explicit paper-to-source relationship and snapshot."""

    if not confirmed:
        raise LibraryConfirmationError(
            "Confirm the Zotero source link before continuing."
        )
    _require_zotero_enabled(settings)
    attachment = _selected_zotero_attachment(details, attachment_key)
    _validate_zotero_details(details)
    repository, _storage = _library_infrastructure(settings)
    entry = repository.get_entry(record_id)
    if entry.record.kind != "paper":
        raise LibraryNotFoundError(
            "A Zotero literature item can only link to a paper record."
        )
    moment = _utc_now()
    return repository.upsert_zotero_link(
        _source_link_from_details(
            record_id,
            details,
            attachment,
            linked_at=moment,
            observed_at=moment,
        )
    )


def unlink_zotero_item_from_paper(
    record_id: str,
    *,
    confirmed: bool,
    settings: Settings | None = None,
) -> bool:
    """Remove only ResearchMind's relationship after confirmation."""

    if not confirmed:
        raise LibraryConfirmationError(
            "Confirm Zotero unlinking before continuing."
        )
    repository, _storage = _library_infrastructure(settings)
    return repository.unlink_zotero_item(record_id)


def import_zotero_pdf_attachment(
    details: ZoteroItemDetails,
    attachment_key: str,
    *,
    confirmed: bool,
    approved_root_scope: str | None = None,
    settings: Settings | None = None,
    client: ZoteroLocalApi | None = None,
) -> LibraryImportResult:
    """Copy one selected Zotero PDF into managed storage, then link it."""

    if not confirmed:
        raise LibraryConfirmationError(
            "Confirm the Zotero PDF import before continuing."
        )
    resolved_settings = _require_zotero_enabled(settings)
    if not resolved_settings.zotero_attachment_root:
        raise ConfigError(
            "Set ZOTERO_ATTACHMENT_ROOT to an explicitly approved local attachment "
            "directory before copying a Zotero PDF."
        )
    expected_scope = zotero_attachment_approval_scope(settings=resolved_settings)
    if expected_scope is None or approved_root_scope != expected_scope:
        raise LibraryConfirmationError(
            "Attachment directory changed or is unsupported; confirm again."
        )
    _validate_zotero_details(details)
    attachment = _selected_zotero_attachment(details, attachment_key)
    if attachment is None:
        raise ValueError("Select a Zotero PDF attachment before importing.")

    repository, _storage = _library_infrastructure(resolved_settings)
    existing_link = repository.find_zotero_link(
        server_id=details.item.server_id,
        library_type=details.item.library_type,
        library_id=details.item.library_id,
        item_key=details.item.item_key,
    )
    if existing_link is not None:
        raise LibraryConflictError(
            "This Zotero item is already linked. Open its library paper, "
            "or explicitly unlink it before importing another attachment. "
            "A source link does not prove that PDF contents are identical."
        )

    api = client or ZoteroLocalApi()
    downloaded = api.download_pdf_attachment(
        details.connection,
        attachment,
        item=details.item,
        approved_root=resolved_settings.zotero_attachment_root,
        max_size_bytes=resolved_settings.pdf_max_size_bytes,
    )
    imported = import_pdf_to_library(
        UploadedFileData(
            name=downloaded.filename,
            content=downloaded.content,
        ),
        settings=resolved_settings,
    )
    try:
        link_zotero_item_to_paper(
            imported.entry.record.id,
            details,
            attachment_key=attachment.item_key,
            confirmed=True,
            settings=resolved_settings,
        )
    except Exception:
        if not imported.duplicate:
            try:
                remove_library_record(
                    imported.entry.record.id,
                    confirmed=True,
                    settings=resolved_settings,
                )
                delete_library_managed_copies(
                    imported.entry.record.id,
                    confirmed=True,
                    settings=resolved_settings,
                )
            except (LibraryError, OSError) as cleanup_error:
                raise LibraryImportError(
                    "Zotero linking and import cleanup failed. "
                    "Review the newly imported record in the local library; "
                    "no Zotero data was changed."
                ) from cleanup_error
        raise
    return imported


def list_library_entries(
    *,
    kind: LibraryItemKind | None = None,
    include_removed: bool = False,
    settings: Settings | None = None,
) -> list[LibraryEntry]:
    """List restart-persistent paper/code entries without exposing paths."""

    repository, _storage = _library_infrastructure(settings)
    return repository.list_entries(
        kind=kind,
        include_removed=include_removed,
    )


def import_pdf_to_library(
    upload: UploadedFileData,
    *,
    record_id: str | None = None,
    settings: Settings | None = None,
) -> LibraryImportResult:
    """Validate and atomically import one browser-uploaded PDF."""

    resolved_settings = settings or load_settings()
    repository, storage = _library_infrastructure(resolved_settings)
    asset_id = uuid4().hex
    staged = storage.stage_pdf(
        upload,
        asset_id=asset_id,
        max_size_bytes=resolved_settings.pdf_max_size_bytes,
    )

    try:
        duplicate = repository.find_by_hash("pdf", staged.sha256)
        if duplicate is not None:
            if duplicate.record.removed_at is not None:
                repository.restore_record(
                    duplicate.record.id,
                    updated_at=_utc_now(),
                )
                duplicate = repository.get_entry(duplicate.record.id)
            return LibraryImportResult(entry=duplicate, duplicate=True)

        opened = pdf_open_pdf(
            staged.staged_path,
            max_size_bytes=resolved_settings.pdf_max_size_bytes,
        )
        moment = _utc_now()
        if record_id is None:
            record = LibraryRecord(
                id=uuid4().hex,
                kind="paper",
                title=opened.document.title,
                created_at=moment,
                updated_at=moment,
            )
            revision = 1
        else:
            existing = repository.get_entry(
                record_id,
                include_removed=True,
            )
            if existing.record.kind != "paper":
                raise LibraryImportError(
                    "A PDF revision can only belong to a paper record."
                )
            record = existing.record
            revision = repository.next_revision(record_id)

        asset = AssetReference(
            id=asset_id,
            record_id=record.id,
            kind="pdf",
            relative_path=staged.relative_path,
            sha256=staged.sha256,
            size_bytes=staged.size_bytes,
            media_type="application/pdf",
            revision=revision,
            managed=True,
            created_at=moment,
        )
        try:
            if record_id is None:
                entry = repository.create_entry(
                    record,
                    asset,
                    finalize=lambda: storage.finalize(staged),
                )
            else:
                entry = repository.add_revision(
                    asset,
                    finalize=lambda: storage.finalize(staged),
                )
        except LibraryDatabaseError:
            storage.discard_final(staged)
            duplicate = repository.find_by_hash("pdf", staged.sha256)
            if duplicate is not None:
                return LibraryImportResult(
                    entry=duplicate,
                    duplicate=True,
                )
            raise
        except Exception:
            storage.discard_final(staged)
            raise
        return LibraryImportResult(entry=entry)
    finally:
        storage.discard_staged(staged)


def import_code_directory_to_library(
    uploads: list[UploadedFileData],
    *,
    project_name: str | None = None,
    record_id: str | None = None,
    settings: Settings | None = None,
) -> LibraryImportResult:
    """Validate and atomically import one browser-selected Python directory."""

    resolved_settings = settings or load_settings()
    repository, storage = _library_infrastructure(resolved_settings)
    asset_id = uuid4().hex
    staged_code = storage.stage_code_directory(
        uploads,
        asset_id=asset_id,
        requested_project_name=project_name,
    )
    staged = staged_code.asset

    try:
        duplicate = repository.find_by_hash(
            "code_directory",
            staged.sha256,
        )
        if duplicate is not None:
            if duplicate.record.removed_at is not None:
                repository.restore_record(
                    duplicate.record.id,
                    updated_at=_utc_now(),
                )
                duplicate = repository.get_entry(duplicate.record.id)
            return LibraryImportResult(entry=duplicate, duplicate=True)

        code_open_code_project(staged.staged_path)
        moment = _utc_now()
        if record_id is None:
            record = LibraryRecord(
                id=uuid4().hex,
                kind="code",
                title=staged_code.project_name,
                created_at=moment,
                updated_at=moment,
            )
            revision = 1
        else:
            existing = repository.get_entry(
                record_id,
                include_removed=True,
            )
            if existing.record.kind != "code":
                raise LibraryImportError(
                    "A code revision can only belong to a code record."
                )
            record = existing.record
            revision = repository.next_revision(record_id)

        asset = AssetReference(
            id=asset_id,
            record_id=record.id,
            kind="code_directory",
            relative_path=staged.relative_path,
            sha256=staged.sha256,
            size_bytes=staged.size_bytes,
            media_type="application/vnd.researchmind.python-directory",
            revision=revision,
            managed=True,
            created_at=moment,
        )
        try:
            if record_id is None:
                entry = repository.create_entry(
                    record,
                    asset,
                    finalize=lambda: storage.finalize(staged),
                )
            else:
                entry = repository.add_revision(
                    asset,
                    finalize=lambda: storage.finalize(staged),
                )
        except LibraryDatabaseError:
            storage.discard_final(staged)
            duplicate = repository.find_by_hash(
                "code_directory",
                staged.sha256,
            )
            if duplicate is not None:
                return LibraryImportResult(
                    entry=duplicate,
                    duplicate=True,
                )
            raise
        except Exception:
            storage.discard_final(staged)
            raise
        return LibraryImportResult(entry=entry)
    finally:
        storage.discard_staged(staged)


def open_library_paper(
    record_id: str,
    *,
    settings: Settings | None = None,
) -> OpenedDocument:
    """Open the latest managed PDF revision after an application restart."""

    resolved_settings = settings or load_settings()
    repository, storage = _library_infrastructure(resolved_settings)
    entry = repository.get_entry(record_id)
    if entry.record.kind != "paper" or entry.asset.kind != "pdf":
        raise LibraryNotFoundError(
            "The selected library entry is not a paper."
        )
    path = storage.resolve_asset(entry.asset)
    return pdf_open_pdf(
        path,
        max_size_bytes=resolved_settings.pdf_max_size_bytes,
    )


def open_library_code_project(
    record_id: str,
    *,
    settings: Settings | None = None,
) -> CodeProject:
    """Open the latest managed Python-directory revision after restart."""

    repository, storage = _library_infrastructure(settings)
    entry = repository.get_entry(record_id)
    if (
        entry.record.kind != "code"
        or entry.asset.kind != "code_directory"
    ):
        raise LibraryNotFoundError(
            "The selected library entry is not a code project."
        )
    opened = code_open_code_project(storage.resolve_asset(entry.asset))
    return CodeProject(
        id=entry.record.id,
        name=entry.record.title,
        root_path=opened.root_path,
        files=opened.files,
        total_source_bytes=opened.total_source_bytes,
        managed_by_researchmind=True,
    )


def remove_library_record(
    record_id: str,
    *,
    confirmed: bool,
    settings: Settings | None = None,
) -> None:
    """Soft-remove one record without deleting any managed file."""

    if not confirmed:
        raise LibraryConfirmationError(
            "Confirm removal from the library before continuing."
        )
    repository, _storage = _library_infrastructure(settings)
    repository.remove_record(record_id, removed_at=_utc_now())


def restore_library_record(
    record_id: str,
    *,
    settings: Settings | None = None,
) -> None:
    """Restore one soft-removed record while its managed asset remains."""

    repository, _storage = _library_infrastructure(settings)
    if not repository.assets_for_record(record_id):
        raise LibraryNotFoundError(
            "The removed record no longer has a managed asset to restore."
        )
    repository.restore_record(record_id, updated_at=_utc_now())


def delete_library_managed_copies(
    record_id: str,
    *,
    confirmed: bool,
    settings: Settings | None = None,
) -> int:
    """Delete only ResearchMind-owned copies after a separate confirmation."""

    if not confirmed:
        raise LibraryConfirmationError(
            "Confirm managed-copy deletion before continuing."
        )
    repository, storage = _library_infrastructure(settings)
    entry = repository.get_entry(record_id, include_removed=True)
    if entry.record.removed_at is None:
        raise LibraryConfirmationError(
            "Remove the library record before deleting its managed copies."
        )
    try:
        repository.get_zotero_link(record_id)
    except LibraryNotFoundError:
        pass
    else:
        raise LibraryConfirmationError(
            "Explicitly unlink the Zotero source before deleting managed copies."
        )
    assets = repository.assets_for_record(record_id)
    if any(not asset.managed for asset in assets):
        raise LibraryConfirmationError(
            "ResearchMind never deletes external source files."
        )

    quarantined = []
    try:
        for asset in assets:
            quarantined.append(storage.quarantine(asset))
        repository.mark_assets_deleted(
            record_id,
            asset_ids=[asset.id for asset in assets],
            deleted_at=_utc_now(),
        )
    except Exception:
        for item in reversed(quarantined):
            storage.restore_quarantine(item)
        raise

    for item in quarantined:
        storage.discard_quarantine(item)
    return len(assets)


def backup_local_library(
    archive_path: Path,
    *,
    settings: Settings | None = None,
) -> LibraryBackupResult:
    """Create one verified non-overwriting local-library backup."""

    resolved_settings = settings or load_settings()
    if resolved_settings.researchmind_data_dir is None:
        raise LibraryBackupError(
            "RESEARCHMIND_DATA_DIR is not configured."
        )
    paths = prepare_library_paths(
        resolved_settings.researchmind_data_dir,
        obsidian_vault_path=resolved_settings.obsidian_vault_path,
    )
    return create_library_backup(paths, archive_path)


def restore_local_library_backup(
    archive_path: Path,
    target_data_dir: Path,
    *,
    settings: Settings | None = None,
) -> LibraryRestoreResult:
    """Restore a verified backup into a separate absent data directory."""

    resolved_settings = settings or load_settings()
    target = Path(target_data_dir).expanduser().resolve(strict=False)
    current_data_dir = resolved_settings.researchmind_data_dir
    if current_data_dir is not None:
        current_root = current_data_dir.expanduser().resolve(strict=False)
        if (
            target == current_root
            or target.is_relative_to(current_root)
            or current_root.is_relative_to(target)
        ):
            raise LibraryBackupError(
                "Restore into a separate new data root, not inside the "
                "current RESEARCHMIND_DATA_DIR."
            )
    vault = resolved_settings.obsidian_vault_path
    if vault is not None:
        vault_root = vault.expanduser().resolve(strict=False)
        if (
            target == vault_root
            or target.is_relative_to(vault_root)
            or vault_root.is_relative_to(target)
        ):
            raise LibraryBackupError(
                "The restored data directory must be separate from "
                "the Obsidian Vault."
            )
    return restore_library_backup(archive_path, target)


def create_note_draft(
    title: str,
    *,
    body_markdown: str = "",
    record_id: str | None = None,
    asset_id: str | None = None,
    settings: Settings | None = None,
) -> NoteDraft:
    """Create one explicit local draft without writing the Obsidian Vault."""

    now = datetime.now(UTC)
    draft = NoteDraft(
        id=f"draft-{uuid4().hex}",
        record_id=record_id,
        asset_id=asset_id,
        title=title.strip(),
        body_markdown=body_markdown,
        status="active",
        revision=1,
        created_at=now,
        updated_at=now,
    )
    validate_note_draft(draft)
    return _note_draft_repository(settings).create_draft(draft)


def get_note_draft(
    draft_id: str,
    *,
    settings: Settings | None = None,
) -> NoteDraft:
    """Load one durable draft by its stable ResearchMind identity."""

    return _note_draft_repository(settings).get_draft(draft_id)


def list_note_drafts(
    *,
    record_id: str | None = None,
    status: NoteDraftStatus | None = None,
    settings: Settings | None = None,
) -> list[NoteDraft]:
    """List durable drafts without loading conversation history."""

    return _note_draft_repository(settings).list_drafts(
        record_id=record_id,
        status=status,
    )


def list_paper_note_drafts(
    document: OpenedDocument,
    *,
    library_entry: LibraryEntry | None = None,
    settings: Settings | None = None,
) -> list[NoteDraft]:
    """List active drafts that belong to the current paper workspace."""

    drafts = list_note_drafts(status="active", settings=settings)
    if library_entry is None:
        return [draft for draft in drafts if draft.record_id is None]
    _validate_opened_paper_entry(document, library_entry)
    return [
        draft
        for draft in drafts
        if draft.record_id == library_entry.record.id
    ]


def update_note_draft(
    draft_id: str,
    *,
    title: str,
    body_markdown: str,
    status: NoteDraftStatus,
    expected_revision: int,
    settings: Settings | None = None,
) -> NoteDraft:
    """Persist an explicit edit with optimistic revision protection."""

    repository = _note_draft_repository(settings)
    current = repository.get_draft(draft_id)
    updated = replace(
        current,
        title=title.strip(),
        body_markdown=body_markdown,
        status=status,
        revision=expected_revision + 1,
        updated_at=datetime.now(UTC),
    )
    validate_note_draft(updated)
    return repository.update_draft(
        updated,
        expected_revision=expected_revision,
    )


def delete_note_draft(
    draft_id: str,
    *,
    expected_revision: int,
    confirmed: bool,
    settings: Settings | None = None,
) -> None:
    """Delete only a ResearchMind draft after explicit confirmation."""

    if not confirmed:
        raise LibraryConfirmationError(
            "Deleting a note draft requires explicit confirmation."
        )
    _note_draft_repository(settings).delete_draft(
        draft_id,
        expected_revision=expected_revision,
    )


def add_note_evidence(
    draft_id: str,
    *,
    kind: EvidenceKind,
    content: str,
    source_label: str,
    origin: EvidenceOrigin,
    expected_draft_revision: int,
    locator: dict[str, object] | None = None,
    source_record_id: str | None = None,
    source_asset_id: str | None = None,
    source_revision: int | None = None,
    source_sha256: str | None = None,
    selection_id: str | None = None,
    included: bool = True,
    settings: Settings | None = None,
) -> tuple[NoteDraft, EvidenceSnapshot]:
    """Persist one user-selected evidence snapshot, never an entire chat."""

    now = datetime.now(UTC)
    snapshot = EvidenceSnapshot(
        id=f"evidence-{uuid4().hex}",
        draft_id=draft_id,
        kind=kind,
        content=content,
        source_label=source_label.strip(),
        locator=dict(locator or {}),
        origin=origin,
        source_record_id=source_record_id,
        source_asset_id=source_asset_id,
        source_revision=source_revision,
        source_sha256=source_sha256,
        selection_id=selection_id,
        included=included,
        sort_order=0,
        created_at=now,
    )
    validate_evidence_snapshot(snapshot)
    return _note_draft_repository(settings).add_evidence(
        snapshot,
        expected_draft_revision=expected_draft_revision,
        updated_at=now,
    )


def list_note_evidence(
    draft_id: str,
    *,
    included_only: bool = False,
    settings: Settings | None = None,
) -> list[EvidenceSnapshot]:
    """Return only explicit evidence stored for one draft."""

    return _note_draft_repository(settings).list_evidence(
        draft_id,
        included_only=included_only,
    )


def set_note_evidence_included(
    draft_id: str,
    evidence_id: str,
    *,
    included: bool,
    expected_draft_revision: int,
    settings: Settings | None = None,
) -> tuple[NoteDraft, EvidenceSnapshot]:
    """Include or exclude one snapshot without rewriting its source content."""

    if not isinstance(included, bool):
        raise ValueError("Evidence included state must be a boolean.")
    return _note_draft_repository(settings).set_evidence_included(
        draft_id,
        evidence_id,
        included=included,
        expected_draft_revision=expected_draft_revision,
        updated_at=datetime.now(UTC),
    )


def reorder_note_evidence(
    draft_id: str,
    evidence_ids: list[str],
    *,
    expected_draft_revision: int,
    settings: Settings | None = None,
) -> tuple[NoteDraft, list[EvidenceSnapshot]]:
    """Persist an exact order containing every current evidence item once."""

    return _note_draft_repository(settings).reorder_evidence(
        draft_id,
        list(evidence_ids),
        expected_draft_revision=expected_draft_revision,
        updated_at=datetime.now(UTC),
    )


def note_evidence_source_state(
    snapshot: EvidenceSnapshot,
    *,
    settings: Settings | None = None,
) -> EvidenceSourceState:
    """Report whether saved provenance still matches the current asset."""

    validate_evidence_snapshot(snapshot)
    return _note_draft_repository(settings).evidence_source_state(snapshot)


def remove_note_evidence(
    draft_id: str,
    evidence_id: str,
    *,
    expected_draft_revision: int,
    settings: Settings | None = None,
) -> NoteDraft:
    """Remove one explicitly chosen snapshot without deleting its source asset."""

    return _note_draft_repository(settings).remove_evidence(
        draft_id,
        evidence_id,
        expected_draft_revision=expected_draft_revision,
        updated_at=datetime.now(UTC),
    )


def preview_note_draft_markdown(
    draft_id: str,
    *,
    expected_revision: int,
    settings: Settings | None = None,
) -> NoteDraftPreview:
    """Build one exact preview from the persisted draft and evidence basket."""

    draft = get_note_draft(draft_id, settings=settings)
    if draft.revision != expected_revision:
        raise LibraryConflictError(
            "The note draft changed before preview. Reload it and try again."
        )
    validate_note_draft(draft)
    evidence = list_note_evidence(
        draft.id,
        included_only=True,
        settings=settings,
    )
    source_states: dict[str, EvidenceSourceState] = {}
    for snapshot in evidence:
        validate_evidence_snapshot(snapshot)
        source_states[snapshot.id] = note_evidence_source_state(
            snapshot,
            settings=settings,
        )
    markdown = render_note_draft_markdown(
        draft,
        evidence,
        source_states,
    )
    return NoteDraftPreview(
        draft_id=draft.id,
        draft_revision=draft.revision,
        title=draft.title,
        markdown=markdown,
        sha256=sha256(markdown.encode("utf-8")).hexdigest(),
        included_evidence_count=len(evidence),
    )


def save_note_draft_to_vault(
    preview: NoteDraftPreview,
    *,
    settings: Settings | None = None,
) -> Path:
    """Write only a still-current, byte-identical draft preview to the Vault."""

    if sha256(preview.markdown.encode("utf-8")).hexdigest() != preview.sha256:
        raise LibraryConflictError(
            "The Markdown preview content changed before saving."
        )
    current = preview_note_draft_markdown(
        preview.draft_id,
        expected_revision=preview.draft_revision,
        settings=settings,
    )
    if current != preview:
        raise LibraryConflictError(
            "The draft, evidence, or source state changed after preview. "
            "Create a new preview before saving."
        )

    resolved_settings = settings or load_settings()
    if resolved_settings.obsidian_vault_path is None:
        raise VaultConfigurationError(
            "OBSIDIAN_VAULT_PATH is not configured. Add it before saving notes."
        )
    draft = get_note_draft(preview.draft_id, settings=resolved_settings)
    return write_markdown_to_vault(
        title=preview.title,
        markdown=preview.markdown,
        created_at=draft.created_at,
        vault_path=resolved_settings.obsidian_vault_path,
        subdirectory=resolved_settings.obsidian_subdirectory,
    )


def create_paper_note_draft(
    document: OpenedDocument,
    *,
    library_entry: LibraryEntry | None = None,
    settings: Settings | None = None,
) -> NoteDraft:
    """Create a draft linked to the exact managed paper revision when available."""

    if library_entry is None:
        return create_note_draft(document.document.title, settings=settings)
    _validate_opened_paper_entry(document, library_entry)
    return create_note_draft(
        document.document.title,
        record_id=library_entry.record.id,
        asset_id=library_entry.asset.id,
        settings=settings,
    )


def capture_reading_selection_evidence(
    draft: NoteDraft,
    selection: ReadingSelection,
    document: OpenedDocument,
    *,
    library_entry: LibraryEntry | None = None,
    settings: Settings | None = None,
) -> tuple[NoteDraft, EvidenceSnapshot]:
    """Capture only the current paper selection after an explicit user action."""

    selection_id = reading_selection_identity(selection)
    _require_new_note_evidence(
        draft.id,
        kind="source_text",
        selection_id=selection_id,
        settings=settings,
    )
    locator = _reading_selection_evidence_locator(selection)
    source = _paper_evidence_source(
        draft,
        document,
        library_entry=library_entry,
    )
    origin: EvidenceOrigin = (
        "browser_selection"
        if str(locator.get("origin", "")).startswith("pdfjs_")
        else "user_entry"
    )
    return add_note_evidence(
        draft.id,
        kind="source_text",
        content=selection.text.strip(),
        source_label=_paper_evidence_label(document, locator),
        origin=origin,
        expected_draft_revision=draft.revision,
        locator=locator,
        source_record_id=source[0],
        source_asset_id=source[1],
        source_revision=source[2],
        source_sha256=source[3],
        selection_id=selection_id,
        settings=settings,
    )


def capture_translation_evidence(
    draft: NoteDraft,
    selection: ReadingSelection,
    translation: Message,
    document: OpenedDocument,
    *,
    library_entry: LibraryEntry | None = None,
    settings: Settings | None = None,
) -> tuple[NoteDraft, EvidenceSnapshot]:
    """Capture one translation already returned for the exact current selection."""

    bound = bind_translation_to_selection(translation, selection)
    assert bound.selection_id is not None
    _require_new_note_evidence(
        draft.id,
        kind="translation",
        selection_id=bound.selection_id,
        settings=settings,
    )
    locator = _reading_selection_evidence_locator(selection)
    source = _paper_evidence_source(
        draft,
        document,
        library_entry=library_entry,
    )
    return add_note_evidence(
        draft.id,
        kind="translation",
        content=bound.content.strip(),
        source_label=f"{_paper_evidence_label(document, locator)} · translation",
        origin="translation_provider",
        expected_draft_revision=draft.revision,
        locator=locator,
        source_record_id=source[0],
        source_asset_id=source[1],
        source_revision=source[2],
        source_sha256=source[3],
        selection_id=bound.selection_id,
        settings=settings,
    )


def detect_formula_regions(
    document: OpenedDocument,
    page_number: int,
) -> tuple[FormulaRegion, ...]:
    """Detect formula regions locally for one exact page revision."""

    return pdf_detect_formula_regions(document, page_number)


def prepare_formula_crop(
    document: OpenedDocument,
    region: FormulaRegion,
) -> FormulaCrop:
    """Render one locally detected formula without contacting a provider."""

    return pdf_render_formula_crop(document, region)


def preview_formula_recognition(
    crop: FormulaCrop,
    *,
    recognizer: FormulaRecognizer | None = None,
    settings: Settings | None = None,
) -> FormulaTransferPreview:
    """Disclose exactly what one recognition action would transfer."""

    _validate_formula_crop(crop)
    resolved_recognizer = recognizer or create_formula_recognizer(
        settings or load_settings()
    )
    recognizer_name, model_revision, execution = _formula_recognizer_metadata(
        resolved_recognizer
    )
    return FormulaTransferPreview(
        region_id=crop.region.id,
        crop_sha256=crop.sha256,
        byte_count=len(crop.png_bytes),
        width_px=crop.width_px,
        height_px=crop.height_px,
        recognizer=recognizer_name,
        model_revision=model_revision,
        execution=execution,
        will_leave_device=execution == "remote",
    )


def recognize_formula_crop(
    crop: FormulaCrop,
    *,
    confirm_external_transfer: bool,
    recognizer: FormulaRecognizer | None = None,
    settings: Settings | None = None,
) -> FormulaRecognitionCandidate:
    """Recognize one crop only after explicit consent for remote execution."""

    _validate_formula_crop(crop)
    resolved_recognizer = recognizer or create_formula_recognizer(
        settings or load_settings()
    )
    recognizer_name, model_revision, execution = _formula_recognizer_metadata(
        resolved_recognizer
    )
    if execution == "remote" and confirm_external_transfer is not True:
        raise ValueError(
            "Formula recognition requires confirmation for this exact crop."
        )
    started = datetime.now(UTC)
    raw_latex_candidate = resolved_recognizer.recognize(crop)
    latex_candidate = (
        None
        if raw_latex_candidate is None
        else parse_latex_response(f"<latex>{raw_latex_candidate}</latex>")
    )
    elapsed_ms = max(
        0,
        int((datetime.now(UTC) - started).total_seconds() * 1_000),
    )
    status = "unreadable" if latex_candidate is None else "recognized"
    payload = json.dumps(
        {
            "region_id": crop.region.id,
            "crop_sha256": crop.sha256,
            "recognizer": recognizer_name,
            "model_revision": model_revision,
            "execution": execution,
            "status": status,
            "latex_candidate": latex_candidate,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return FormulaRecognitionCandidate(
        id=f"formula-candidate-{sha256(payload).hexdigest()[:32]}",
        region=crop.region,
        crop_sha256=crop.sha256,
        recognizer=recognizer_name,
        model_revision=model_revision,
        execution=execution,
        status=status,
        latex_candidate=latex_candidate,
        elapsed_ms=elapsed_ms,
        created_at=datetime.now(UTC),
    )


def accept_formula_candidate(
    candidate: FormulaRecognitionCandidate,
    edited_latex: str,
    document: OpenedDocument,
) -> FormulaRecognitionCandidate:
    """Validate and explicitly accept one editable formula candidate."""

    _validate_formula_candidate(candidate)
    if candidate.status != "recognized" or candidate.latex_candidate is None:
        raise ValueError("An unreadable formula candidate cannot be accepted.")
    if candidate.accepted_latex is not None or candidate.accepted_at is not None:
        raise ValueError("This formula candidate has already been accepted.")
    current_crop = prepare_formula_crop(document, candidate.region)
    if current_crop.sha256 != candidate.crop_sha256:
        raise ValueError("Formula crop changed. Detect and recognize it again.")
    normalized_latex = parse_latex_response(
        f"<latex>{edited_latex.strip()}</latex>"
    )
    return replace(
        candidate,
        accepted_latex=normalized_latex,
        accepted_at=datetime.now(UTC),
    )


def capture_formula_evidence(
    draft: NoteDraft,
    candidate: FormulaRecognitionCandidate,
    document: OpenedDocument,
    *,
    library_entry: LibraryEntry | None = None,
    settings: Settings | None = None,
) -> tuple[NoteDraft, EvidenceSnapshot]:
    """Persist only user-accepted LaTeX plus path-free recognition provenance."""

    _validate_formula_candidate(candidate)
    if candidate.accepted_latex is None or candidate.accepted_at is None:
        raise ValueError("Accept the edited LaTeX before adding formula evidence.")
    current_crop = prepare_formula_crop(document, candidate.region)
    if current_crop.sha256 != candidate.crop_sha256:
        raise ValueError("Formula crop changed. Detect and recognize it again.")
    selection_payload = json.dumps(
        {
            "candidate_id": candidate.id,
            "accepted_latex": candidate.accepted_latex,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    selection_id = f"formula-{sha256(selection_payload).hexdigest()[:32]}"
    _require_new_note_evidence(
        draft.id,
        kind="latex",
        selection_id=selection_id,
        settings=settings,
    )
    source = _paper_evidence_source(
        draft,
        document,
        library_entry=library_entry,
    )
    region = candidate.region
    locator: dict[str, object] = {
        "source_type": "pdf",
        "page_number": region.page_number,
        "bbox": [float(value) for value in region.bbox],
        "document_revision": region.document_revision,
        "region_id": region.id,
        "region_kind": region.kind,
        "source_kind": region.source_kind,
        "detector_origin": region.detector_origin,
        "detector_confidence": region.detector_confidence,
        "detector_signals": list(region.signals),
        "crop_sha256": candidate.crop_sha256,
        "recognizer": candidate.recognizer,
        "model_revision": candidate.model_revision,
        "execution": candidate.execution,
    }
    return add_note_evidence(
        draft.id,
        kind="latex",
        content=candidate.accepted_latex,
        source_label=(
            f"{document.document.title} · page {region.page_number} · formula"
        ),
        origin="latex_conversion",
        expected_draft_revision=draft.revision,
        locator=locator,
        source_record_id=source[0],
        source_asset_id=source[1],
        source_revision=source[2],
        source_sha256=source[3],
        selection_id=selection_id,
        settings=settings,
    )


def _validate_formula_crop(crop: FormulaCrop) -> None:
    _validate_formula_region(crop.region)
    if not crop.png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Formula crop is not a PNG image.")
    if len(crop.png_bytes) > MAX_FORMULA_CROP_BYTES:
        raise ValueError("Formula crop exceeds the byte limit.")
    if (
        not isinstance(crop.sha256, str)
        or len(crop.sha256) != 64
        or any(character not in "0123456789abcdef" for character in crop.sha256)
    ):
        raise ValueError("Formula crop hash is invalid.")
    if sha256(crop.png_bytes).hexdigest() != crop.sha256:
        raise ValueError("Formula crop hash does not match its bytes.")
    if (
        isinstance(crop.width_px, bool)
        or not isinstance(crop.width_px, int)
        or crop.width_px < 1
        or isinstance(crop.height_px, bool)
        or not isinstance(crop.height_px, int)
        or crop.height_px < 1
    ):
        raise ValueError("Formula crop dimensions are invalid.")
    if crop.width_px * crop.height_px > MAX_FORMULA_CROP_PIXELS:
        raise ValueError("Formula crop exceeds the pixel limit.")


def _validate_formula_region(region: FormulaRegion) -> None:
    if (
        not isinstance(region.id, str)
        or not region.id.startswith("formula-region-")
        or len(region.id) > 128
        or "\x00" in region.id
    ):
        raise ValueError("Formula region identity is invalid.")
    if (
        not isinstance(region.document_id, str)
        or not region.document_id
        or len(region.document_id) > 128
        or "\x00" in region.document_id
    ):
        raise ValueError("Formula document identity is invalid.")
    revision = region.document_revision
    if (
        not isinstance(revision, str)
        or not revision.startswith("sha256:")
        or len(revision) != 71
        or any(character not in "0123456789abcdef" for character in revision[7:])
    ):
        raise ValueError("Formula document revision is invalid.")
    if (
        isinstance(region.page_number, bool)
        or not isinstance(region.page_number, int)
        or region.page_number < 1
    ):
        raise ValueError("Formula page number is invalid.")
    if (
        not isinstance(region.bbox, tuple)
        or len(region.bbox) != 4
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            for value in region.bbox
        )
        or region.bbox[0] < 0
        or region.bbox[1] < 0
        or region.bbox[2] <= region.bbox[0]
        or region.bbox[3] <= region.bbox[1]
    ):
        raise ValueError("Formula region geometry is invalid.")
    if region.kind not in {"display", "inline"}:
        raise ValueError("Formula region kind is invalid.")
    if region.source_kind not in {"digital_text", "embedded_image"}:
        raise ValueError("Formula source kind is invalid.")
    if (
        not isinstance(region.detector_origin, str)
        or not region.detector_origin
        or len(region.detector_origin) > 128
        or "\x00" in region.detector_origin
    ):
        raise ValueError("Formula detector identity is invalid.")
    if (
        isinstance(region.detector_confidence, bool)
        or not isinstance(region.detector_confidence, (int, float))
        or not isfinite(float(region.detector_confidence))
        or not 0 <= float(region.detector_confidence) <= 1
    ):
        raise ValueError("Formula detector confidence is invalid.")
    if (
        not isinstance(region.signals, tuple)
        or len(region.signals) > 32
        or any(
            not isinstance(signal, str)
            or not signal
            or len(signal) > 64
            or "\x00" in signal
            for signal in region.signals
        )
    ):
        raise ValueError("Formula detector signals are invalid.")
    if region.source_text is not None and (
        not isinstance(region.source_text, str)
        or len(region.source_text) > 500
        or "\x00" in region.source_text
    ):
        raise ValueError("Formula source text is invalid.")


def _formula_recognizer_metadata(
    recognizer: FormulaRecognizer,
) -> tuple[str, str, Literal["local", "remote"]]:
    name = recognizer.name
    model_revision = recognizer.model_revision
    execution = recognizer.execution
    for value, label in (
        (name, "Formula recognizer identity"),
        (model_revision, "Formula model revision"),
    ):
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 200
            or "\x00" in value
        ):
            raise ValueError(f"{label} is invalid.")
    if execution not in {"local", "remote"}:
        raise ValueError("Formula recognizer execution mode is invalid.")
    return name.strip(), model_revision.strip(), execution


def _validate_formula_candidate(candidate: FormulaRecognitionCandidate) -> None:
    _validate_formula_region(candidate.region)
    if (
        not isinstance(candidate.id, str)
        or not candidate.id.startswith("formula-candidate-")
        or len(candidate.id) > 128
        or "\x00" in candidate.id
    ):
        raise ValueError("Formula candidate identity is invalid.")
    if (
        not isinstance(candidate.crop_sha256, str)
        or len(candidate.crop_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in candidate.crop_sha256
        )
    ):
        raise ValueError("Formula candidate crop hash is invalid.")
    _formula_recognizer_metadata(_CandidateMetadata(candidate))
    if candidate.status not in {"recognized", "unreadable"}:
        raise ValueError("Formula recognition status is invalid.")
    if candidate.status == "recognized":
        if candidate.latex_candidate is None:
            raise ValueError("Recognized formula candidate is missing LaTeX.")
        parse_latex_response(f"<latex>{candidate.latex_candidate}</latex>")
    elif candidate.latex_candidate is not None:
        raise ValueError("Unreadable formula candidate must not contain LaTeX.")
    if (
        isinstance(candidate.elapsed_ms, bool)
        or not isinstance(candidate.elapsed_ms, int)
        or candidate.elapsed_ms < 0
    ):
        raise ValueError("Formula recognition elapsed time is invalid.")
    created_offset = getattr(candidate.created_at, "utcoffset", lambda: None)()
    if created_offset is None:
        raise ValueError("Formula candidate time must include a timezone.")
    if (candidate.accepted_latex is None) != (candidate.accepted_at is None):
        raise ValueError("Formula acceptance fields are inconsistent.")
    if candidate.accepted_latex is not None:
        parse_latex_response(f"<latex>{candidate.accepted_latex}</latex>")
        assert candidate.accepted_at is not None
        accepted_offset = getattr(
            candidate.accepted_at,
            "utcoffset",
            lambda: None,
        )()
        if accepted_offset is None:
            raise ValueError("Formula acceptance time must include a timezone.")


@dataclass(frozen=True)
class _CandidateMetadata:
    candidate: FormulaRecognitionCandidate

    @property
    def name(self) -> str:
        return self.candidate.recognizer

    @property
    def model_revision(self) -> str:
        return self.candidate.model_revision

    @property
    def execution(self) -> Literal["local", "remote"]:
        return self.candidate.execution


def _require_new_note_evidence(
    draft_id: str,
    *,
    kind: EvidenceKind,
    selection_id: str,
    settings: Settings | None,
) -> None:
    if any(
        item.kind == kind and item.selection_id == selection_id
        for item in list_note_evidence(draft_id, settings=settings)
    ):
        raise LibraryConflictError(
            "This selection and evidence type are already in the note basket."
        )


def _reading_selection_evidence_locator(
    selection: ReadingSelection,
) -> dict[str, object]:
    raw = selection.locator or {}
    locator: dict[str, object] = {"source_type": selection.source_type}
    for key in ("page_number", "block_index"):
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Selection locator {key} must be an integer.")
        if (key == "page_number" and value < 1) or (
            key == "block_index" and value < 0
        ):
            raise ValueError(f"Selection locator {key} is out of range.")
        locator[key] = value
    bbox = raw.get("bbox")
    if bbox is not None:
        if (
            not isinstance(bbox, (list, tuple))
            or len(bbox) != 4
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in bbox
            )
            or any(not isfinite(float(value)) for value in bbox)
        ):
            raise ValueError("Selection locator bbox must contain four numbers.")
        locator["bbox"] = [float(value) for value in bbox]
    for key in (
        "document_revision",
        "origin",
        "viewer_engine",
        "locator_status",
    ):
        value = raw.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Selection locator {key} must be non-blank text.")
        locator[key] = value.strip()
    for key in ("geometry_coverage", "geometry_precision"):
        value = raw.get(key)
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise ValueError(f"Selection locator {key} must be between 0 and 1.")
        locator[key] = float(value)
    bboxes = raw.get("bboxes")
    if bboxes is not None:
        locator["bboxes"] = _normalize_locator_rows(
            bboxes,
            width=4,
            numeric_type=float,
            label="bboxes",
        )
    client_ranges = raw.get("client_ranges")
    if client_ranges is not None:
        locator["client_ranges"] = _normalize_locator_rows(
            client_ranges,
            width=3,
            numeric_type=int,
            label="client_ranges",
        )
    return locator


def _normalize_locator_rows(
    value: object,
    *,
    width: int,
    numeric_type: type[float] | type[int],
    label: str,
) -> list[list[float | int]]:
    if not isinstance(value, (list, tuple)) or len(value) > 256:
        raise ValueError(f"Selection locator {label} must be a bounded sequence.")
    normalized: list[list[float | int]] = []
    for row in value:
        if (
            not isinstance(row, (list, tuple))
            or len(row) != width
        ):
            raise ValueError(
                f"Selection locator {label} contains an invalid row."
            )
        if numeric_type is int:
            if any(type(item) is not int for item in row):
                raise ValueError(
                    f"Selection locator {label} contains an invalid row."
                )
            normalized.append([int(item) for item in row])
            continue
        if any(
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not isfinite(float(item))
            for item in row
        ):
            raise ValueError(
                f"Selection locator {label} contains an invalid row."
            )
        normalized.append([float(item) for item in row])
    return normalized


def _validate_opened_paper_entry(
    document: OpenedDocument,
    entry: LibraryEntry,
) -> None:
    if (
        entry.record.kind != "paper"
        or entry.asset.kind != "pdf"
        or entry.record.removed_at is not None
        or entry.asset.deleted_at is not None
    ):
        raise LibraryConflictError(
            "The opened library source is no longer an active paper revision."
        )
    if (
        not document.content_sha256
        or entry.asset.sha256 != document.content_sha256
    ):
        raise LibraryConflictError(
            "The opened PDF no longer matches the selected library revision."
        )


def _paper_evidence_source(
    draft: NoteDraft,
    document: OpenedDocument,
    *,
    library_entry: LibraryEntry | None,
) -> tuple[str | None, str | None, int | None, str | None]:
    if library_entry is None:
        if draft.record_id is not None or draft.asset_id is not None:
            raise LibraryConflictError(
                "The linked draft has lost its managed paper source."
            )
        return None, None, None, None
    _validate_opened_paper_entry(document, library_entry)
    if (
        draft.record_id != library_entry.record.id
        or draft.asset_id != library_entry.asset.id
    ):
        raise LibraryConflictError(
            "The draft belongs to a different managed paper revision."
        )
    return (
        library_entry.record.id,
        library_entry.asset.id,
        library_entry.asset.revision,
        library_entry.asset.sha256,
    )


def _paper_evidence_label(
    document: OpenedDocument,
    locator: dict[str, object],
) -> str:
    title = " ".join(document.document.title.split()) or "Untitled paper"
    page = locator.get("page_number")
    suffix = f" · page {page}" if isinstance(page, int) else ""
    return f"{title[:460]}{suffix}"


def _library_infrastructure(
    settings: Settings | None,
) -> tuple[LibraryRepository, ManagedStorage]:
    resolved_settings = settings or load_settings()
    if resolved_settings.researchmind_data_dir is None:
        raise LibraryImportError(
            "RESEARCHMIND_DATA_DIR is not configured."
        )
    paths = prepare_library_paths(
        resolved_settings.researchmind_data_dir,
        obsidian_vault_path=resolved_settings.obsidian_vault_path,
    )
    database_path = initialize_database(paths.database_path)
    return LibraryRepository(database_path), ManagedStorage(paths)


def _note_draft_repository(
    settings: Settings | None,
) -> NoteDraftRepository:
    repository, _storage = _library_infrastructure(settings)
    return NoteDraftRepository(repository.database_path)


def _require_zotero_enabled(
    settings: Settings | None,
) -> Settings:
    resolved_settings = settings or load_settings()
    if not resolved_settings.zotero_local_api_enabled:
        raise ConfigError(
            "ZOTERO_LOCAL_API_ENABLED is false. Enable it explicitly "
            "before connecting to Zotero."
        )
    return resolved_settings


def _validate_zotero_identity(
    browse_result: ZoteroBrowseResult,
    item_server_id: str,
) -> None:
    if browse_result.connection.api_version != 3:
        raise ValueError("Zotero API version 3 is required.")
    if browse_result.connection.server_id != item_server_id:
        raise ValueError("The Zotero item belongs to a different server.")


def _validate_zotero_details(details: ZoteroItemDetails) -> None:
    _validate_zotero_identity(
        ZoteroBrowseResult(
            connection=details.connection,
            items=(details.item,),
        ),
        details.item.server_id,
    )
    if details.item.library_type != "user":
        raise ValueError(
            "V3-G2 supports the personal Zotero library only."
        )
    if any(
        attachment.parent_item_key != details.item.item_key
        for attachment in details.attachments
    ):
        raise ValueError(
            "A Zotero attachment does not belong to the selected item."
        )


def _selected_zotero_attachment(
    details: ZoteroItemDetails,
    attachment_key: str | None,
) -> ZoteroAttachment | None:
    if attachment_key is None:
        return None
    attachment = next(
        (
            candidate
            for candidate in details.attachments
            if candidate.item_key == attachment_key
        ),
        None,
    )
    if attachment is None:
        raise ValueError(
            "The selected PDF attachment is not in this item result."
        )
    return attachment


def _source_link_from_details(
    record_id: str,
    details: ZoteroItemDetails,
    attachment: ZoteroAttachment | None,
    *,
    linked_at: datetime,
    observed_at: datetime,
) -> ZoteroSourceLink:
    item = details.item
    return ZoteroSourceLink(
        id=uuid4().hex,
        record_id=record_id,
        server_id=item.server_id,
        library_type=item.library_type,
        library_id=item.library_id,
        item_key=item.item_key,
        item_version=item.item_version,
        item_type=item.item_type,
        title=item.title,
        creators=item.creators,
        publication_title=item.publication_title,
        published_date=item.published_date,
        doi=item.doi,
        url=item.url,
        attachment_key=(None if attachment is None else attachment.item_key),
        attachment_version=(
            None if attachment is None else attachment.item_version
        ),
        attachment_filename=(
            None if attachment is None else attachment.filename
        ),
        linked_at=linked_at,
        observed_at=observed_at,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def open_code_project(path: Path) -> CodeProject:
    """Open one local Python folder through the fixed T3 safety limits."""

    return code_open_code_project(path)


def get_code_file(project: CodeProject, relative_path: str) -> CodeFile:
    """Return one indexed code file without exposing reader internals to the UI."""

    return core_get_code_file(project, relative_path)


def get_code_project_summary(project: CodeProject) -> CodeProjectSummary:
    """Return a path-safe static overview without reading new files."""

    return summarize_code_project(project)


def create_code_symbol_selection(
    project: CodeProject,
    relative_path: str,
    *,
    symbol_index: int,
) -> CodeSelection:
    """Create a traceable selection from one statically located symbol."""

    return select_code_symbol(
        project,
        relative_path,
        symbol_index=symbol_index,
    )


def create_code_line_selection(
    project: CodeProject,
    relative_path: str,
    *,
    start_line: int,
    end_line: int,
) -> CodeSelection:
    """Create a traceable selection from an explicit inclusive line range."""

    return select_code_lines(
        project,
        relative_path,
        start_line=start_line,
        end_line=end_line,
    )


def preview_code_context(
    project: CodeProject,
    selection: CodeSelection,
    *,
    question: str,
    settings: Settings | None = None,
) -> CodeContextEvidencePreview:
    """Preview the exact bounded code request without invoking an LLM."""

    resolved_settings = settings or load_settings()
    context = _build_code_explanation_context(
        project,
        selection,
        question=question,
        settings=resolved_settings,
    )
    request_messages = build_code_explanation_prompt(context)
    request_character_count = _request_character_count(request_messages)
    return CodeContextEvidencePreview(
        project_name=context.project_name,
        source_type=context.source,
        relative_path=context.relative_path,
        start_line=context.start_line,
        end_line=context.end_line,
        symbol_kind=context.symbol_kind,
        symbol_name=context.symbol_name,
        extraction_method=context.extraction_method,
        selected_code=context.selected_code,
        surrounding_code=context.surrounding_code,
        user_question=context.user_question,
        request_character_count=request_character_count,
        approximate_request_tokens=_approximate_tokens(
            request_character_count
        ),
    )


def explain_code_selection(
    project: CodeProject,
    selection: CodeSelection,
    *,
    question: str,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Explain one explicit static-code selection without execution authority."""

    resolved_settings = settings or load_settings()
    context = _build_code_explanation_context(
        project,
        selection,
        question=question,
        settings=resolved_settings,
    )
    provider = llm_provider or create_llm_provider(resolved_settings)
    response = provider.complete(build_code_explanation_prompt(context))
    return Message(
        role="assistant",
        task="explain:code",
        content=response,
        selection_id=selection.id,
    )


def propose_code_change(
    project: CodeProject,
    selection: CodeSelection,
    *,
    instruction: str,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> CodeChangeProposal:
    """Request and validate one preview-only selected-range replacement."""

    _require_editable_external_code_project(project)
    resolved_settings = settings or load_settings()
    snapshot = read_code_snapshot(project, selection.relative_path)
    validate_code_change_snapshot(project, selection, snapshot)
    context = _build_code_explanation_context(
        project,
        selection,
        question=instruction,
        settings=resolved_settings,
    )
    provider = llm_provider or create_llm_provider(resolved_settings)
    response = provider.complete(build_code_change_prompt(context))
    replacement = parse_code_replacement(response)
    return build_code_change_proposal(
        project,
        selection,
        snapshot,
        replacement_text=replacement,
    )


def apply_code_change_proposal(
    project: CodeProject,
    proposal: CodeChangeProposal,
    *,
    confirmed: bool,
) -> CodeChangeApplication:
    """Apply exactly one proposal only after explicit per-action confirmation."""

    _require_editable_external_code_project(project)
    if not confirmed:
        raise ValueError("Code change requires explicit confirmation before writing.")
    updated_file = code_file_from_proposal(proposal)
    receipt = code_apply_code_change(project, proposal)
    return CodeChangeApplication(
        project=replace_code_project_file(project, updated_file),
        receipt=receipt,
    )


def rollback_applied_code_change(
    project: CodeProject,
    receipt: CodeChangeReceipt,
    *,
    confirmed: bool,
) -> CodeChangeRollbackApplication:
    """Roll back exactly one applied change after a second explicit consent."""

    _require_editable_external_code_project(project)
    if not confirmed:
        raise ValueError("Code rollback requires explicit confirmation.")
    updated_file = code_file_from_recovery(project, receipt)
    rollback_receipt = code_rollback_code_change(project, receipt)
    return CodeChangeRollbackApplication(
        project=replace_code_project_file(project, updated_file),
        receipt=rollback_receipt,
    )


def _require_editable_external_code_project(project: CodeProject) -> None:
    if project.managed_by_researchmind:
        raise ValueError(
            "Managed library code is read-only. Import a new revision instead "
            "of changing the indexed copy in place."
        )


def create_code_change_audit_event(
    *,
    action: CodeChangeAuditAction,
    status: CodeChangeAuditStatus,
    relative_path: str,
    start_line: int,
    end_line: int,
    before_sha256: str | None = None,
    after_sha256: str | None = None,
    recovery_relative_path: str | None = None,
    error: Exception | None = None,
) -> CodeChangeAuditEvent:
    """Create non-sensitive session metadata for one T5-B1 user action."""

    if not relative_path or relative_path.startswith(("/", "\\")):
        raise ValueError("Code-change audit requires a relative path.")
    if start_line < 1 or end_line < start_line:
        raise ValueError("Code-change audit requires a valid line range.")
    return CodeChangeAuditEvent(
        action=action,
        status=status,
        relative_path=relative_path,
        start_line=start_line,
        end_line=end_line,
        occurred_at=datetime.now(UTC).isoformat(timespec="seconds"),
        before_sha256=before_sha256,
        after_sha256=after_sha256,
        recovery_relative_path=recovery_relative_path,
        error_type=None if error is None else type(error).__name__,
    )


def create_evidence_link(
    document: OpenedDocument,
    reading_selection: ReadingSelection,
    code_project: CodeProject,
    code_selection: CodeSelection,
    *,
    evidence_kind: PaperEvidenceKind,
    relation: EvidenceRelation,
    confidence: float,
    rationale: str | None = None,
) -> EvidenceLink:
    """Create a user-confirmed link without merging paper and code contexts."""

    return create_user_confirmed_evidence_link(
        document.document,
        reading_selection,
        code_project,
        code_selection,
        evidence_kind=evidence_kind,
        relation=relation,
        confidence=confidence,
        rationale=rationale,
    )


def add_evidence_link(
    existing_links: list[EvidenceLink],
    link: EvidenceLink,
) -> list[EvidenceLink]:
    """Add one evidence link while preserving collection immutability."""

    return core_add_evidence_link(existing_links, link)


def open_pdf(path: Path, *, settings: Settings | None = None) -> OpenedDocument:
    """Open and extract a local PDF within the configured size limit."""

    resolved_settings = settings or load_settings()
    return pdf_open_pdf(path, max_size_bytes=resolved_settings.pdf_max_size_bytes)


def load_pdf_text_layer_source(
    path: Path,
    *,
    expected_sha256: str,
    max_size_bytes: int,
) -> PdfViewerSource:
    """Load unchanged bytes for the adopted local browser text-layer viewer."""

    return pdf_load_pdf_viewer_source(
        path,
        expected_sha256=expected_sha256,
        max_size_bytes=max_size_bytes,
        viewer_max_size_bytes=DEFAULT_PDF_VIEWER_MAX_SIZE_BYTES,
    )


def mount_pdf_text_layer(
    source: PdfViewerSource,
    *,
    page: int,
    page_count: int,
    scale: float,
    key: str,
    on_selection: Callable[[], None],
    on_page_turn: Callable[[], None],
) -> None:
    """Mount the adopted viewer while keeping its object inside the PDF boundary."""

    from researchmind.pdf.viewer_component import mount_pdf_viewer

    mount_pdf_viewer(
        source,
        page=page,
        page_count=page_count,
        scale=scale,
        key=key,
        on_selection=on_selection,
        on_page_turn=on_page_turn,
    )


def create_pdf_text_layer_selection(
    source: PdfViewerSource,
    document: OpenedDocument,
    event: object,
    *,
    instance: str,
    last_sequence: int,
) -> tuple[ReadingSelection, int]:
    """Reconcile an untrusted browser event into a current ReadingSelection."""

    from researchmind.pdf.viewer_component import reconcile_selection

    return reconcile_selection(
        source,
        document,
        event,
        instance=instance,
        last_sequence=last_sequence,
    )


def validate_pdf_text_layer_page_turn(
    source: PdfViewerSource,
    event: object,
    *,
    instance: str,
    current_page: int,
    page_count: int,
    last_sequence: int,
) -> tuple[int, int]:
    """Return a trusted adjacent page and accepted browser sequence."""

    from researchmind.pdf.viewer_component import reconcile_page_turn

    turn = reconcile_page_turn(
        source,
        event,
        instance=instance,
        current_page=current_page,
        page_count=page_count,
        last_sequence=last_sequence,
    )
    return turn.target_page, turn.sequence


def mount_ai_panel_shortcut(
    *,
    key: str,
    last_sequence: int,
    on_toggle: Callable[[], None],
) -> None:
    """Mount the input-safe G3 shortcut listener."""

    from researchmind.pdf.viewer_component import mount_workspace_shortcut

    mount_workspace_shortcut(
        key=key,
        last_sequence=last_sequence,
        on_toggle=on_toggle,
    )


def validate_ai_panel_shortcut(
    event: object,
    *,
    last_sequence: int,
) -> int:
    """Validate the fixed shortcut and return its accepted sequence."""

    from researchmind.pdf.viewer_component import reconcile_shortcut

    return reconcile_shortcut(
        event,
        last_sequence=last_sequence,
    ).sequence


def get_page_view(
    document: OpenedDocument,
    page_number: int,
    *,
    zoom: float = 1.0,
) -> PageView:
    """Return the page image and extracted text used by the reader view."""

    page = extract_page(document, page_number)
    return PageView(
        page=page,
        image_png=render_page_image(document, page_number, zoom=zoom),
        zoom=float(zoom),
        figure_images=render_figure_images(document, page_number),
    )


def search_text(document: OpenedDocument, query: str) -> list[TextMatch]:
    """Search extracted PDF text without exposing PDF-library objects."""

    return pdf_search_text(document, query)


def get_document_text_coverage(
    document: OpenedDocument,
) -> DocumentTextCoverage:
    """Summarize how many pages contain extractable text."""

    return DocumentTextCoverage(
        total_pages=len(document.pages),
        pages_with_text=sum(bool(page.text.strip()) for page in document.pages),
    )


def create_selection(
    document: OpenedDocument,
    text: str,
    current_page: int | None,
) -> ReadingSelection:
    """Create a selection, locating it when extracted text permits."""

    return locate_selection(text, document.pages, current_page=current_page)


def create_block_selection(
    document: OpenedDocument,
    page_number: int,
    block_index: int,
) -> ReadingSelection:
    """Create an exact selection from one displayed document text block."""

    page = next(
        (item for item in document.pages if item.page_number == page_number),
        None,
    )
    if page is None:
        raise ValueError(f"Page {page_number} was not found in the opened PDF.")
    return select_text_block(page, block_index=block_index)


def reading_selection_identity(selection: ReadingSelection) -> str:
    """Return a stable, path-free identity for one exact paper selection."""

    source_text = selection.text.strip()
    if not source_text:
        raise ValueError("Selection text must not be blank.")
    locator = _reading_selection_evidence_locator(selection)
    payload = json.dumps(
        {
            "source_type": selection.source_type,
            "text": source_text,
            "locator": locator,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"reading-{sha256(payload).hexdigest()[:32]}"


def preview_selection_translation(
    selection: ReadingSelection,
    *,
    settings: Settings | None = None,
) -> TranslationTransferPreview:
    """Build the local-only preview for one possible translation request."""

    resolved_settings = settings or load_settings()
    request = prepare_translation_request(
        selection.text,
        resolved_settings.target_language,
    )
    return TranslationTransferPreview(
        source_text=request.source_text,
        target_language=request.target_language,
        selection_id=reading_selection_identity(selection),
    )


def bind_translation_to_selection(
    message: Message,
    selection: ReadingSelection,
) -> Message:
    """Bind a successful translation to the selection it actually represents."""

    if message.role != "assistant" or message.task != "translate":
        raise ValueError("Only an assistant translation can be bound to a selection.")
    selection_id = reading_selection_identity(selection)
    if message.selection_id not in (None, selection_id):
        raise ValueError("Translation belongs to a different reading selection.")
    return replace(message, selection_id=selection_id)


def translate_selection(
    selection: ReadingSelection,
    *,
    translation_provider: TranslationProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Translate a selection through the independent translation capability."""

    resolved_settings = settings or load_settings()
    provider = translation_provider
    if provider is None:
        provider = LlmTranslationProvider(create_llm_provider(resolved_settings))
    translated = translate_text(
        selection.text,
        resolved_settings.target_language,
        provider,
    )
    return Message(
        role="assistant",
        task="translate",
        content=translated,
        selection_id=reading_selection_identity(selection),
    )


def explain_selection(
    selection: ReadingSelection,
    mode: ExplainMode,
    *,
    document: OpenedDocument,
    conversation: Conversation | None = None,
    question: str | None = None,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Explain the selection using a freshly assembled ResearchContext."""

    _validate_explain_mode(mode)
    resolved_settings = settings or load_settings()
    context = _build_explanation_context(
        selection,
        mode,
        document=document,
        conversation=conversation,
        question=question,
        settings=resolved_settings,
    )
    provider = llm_provider or create_llm_provider(resolved_settings)
    response = provider.complete(_EXPLANATION_BUILDERS[mode](context))
    return Message(
        role="assistant",
        task=f"explain:{mode}",
        content=response,
    )


def preview_explanation_context(
    selection: ReadingSelection,
    mode: ExplainMode,
    *,
    document: OpenedDocument,
    conversation: Conversation | None = None,
    question: str | None = None,
    settings: Settings | None = None,
) -> ContextEvidencePreview:
    """Preview exactly the evidence used by an explanation without calling an LLM."""

    _validate_explain_mode(mode)
    resolved_settings = settings or load_settings()
    context = _build_explanation_context(
        selection,
        mode,
        document=document,
        conversation=conversation,
        question=question,
        settings=resolved_settings,
    )
    return _context_evidence_preview(
        context,
        _EXPLANATION_BUILDERS[mode](context),
    )


def convert_selection_to_latex(
    selection: ReadingSelection,
    *,
    document: OpenedDocument,
    conversation: Conversation | None = None,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Convert selected mathematical text to one constrained LaTeX expression."""

    resolved_settings = settings or load_settings()
    context = _build_context(
        selection,
        document=document,
        conversation=conversation,
        user_question=_LATEX_QUESTION,
        settings=resolved_settings,
    )
    provider = llm_provider or create_llm_provider(resolved_settings)
    expression = parse_latex_response(
        provider.complete(build_latex_prompt(context))
    )
    return Message(
        role="assistant",
        task="convert:latex",
        content=expression,
    )


def preview_latex_context(
    selection: ReadingSelection,
    *,
    document: OpenedDocument,
    conversation: Conversation | None = None,
    settings: Settings | None = None,
) -> ContextEvidencePreview:
    """Preview exactly what a LaTeX conversion sends without calling an LLM."""

    resolved_settings = settings or load_settings()
    context = _build_context(
        selection,
        document=document,
        conversation=conversation,
        user_question=_LATEX_QUESTION,
        settings=resolved_settings,
    )
    return _context_evidence_preview(context, build_latex_prompt(context))


def ask_followup(
    question: str,
    *,
    document: OpenedDocument,
    selection: ReadingSelection,
    conversation: Conversation,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Answer a follow-up from fresh selection, paper, and history context."""

    normalized_question = _validated_followup_question(question)
    resolved_settings = settings or load_settings()
    context = _build_context(
        selection,
        document=document,
        conversation=conversation,
        user_question=normalized_question,
        settings=resolved_settings,
    )
    provider = llm_provider or create_llm_provider(resolved_settings)
    response = provider.complete(build_followup_prompt(context))
    return Message(role="assistant", task="followup", content=response)


def preview_followup_context(
    question: str,
    *,
    document: OpenedDocument,
    selection: ReadingSelection,
    conversation: Conversation,
    settings: Settings | None = None,
) -> ContextEvidencePreview:
    """Preview exactly the evidence used by a follow-up without calling an LLM."""

    normalized_question = _validated_followup_question(question)
    resolved_settings = settings or load_settings()
    context = _build_context(
        selection,
        document=document,
        conversation=conversation,
        user_question=normalized_question,
        settings=resolved_settings,
    )
    return _context_evidence_preview(context, build_followup_prompt(context))


def get_available_assistant_tools(
    *,
    document: OpenedDocument | None,
    reading_selection: ReadingSelection | None,
    code_project: CodeProject | None,
    code_selection: CodeSelection | None,
    evidence_links: list[EvidenceLink],
) -> tuple[AssistantToolName, ...]:
    """Return the fixed read-only tools backed by current session evidence."""

    available: list[AssistantToolName] = []
    if document is not None and reading_selection is not None:
        available.append("inspect_paper_context")
    if (
        code_project is not None
        and code_selection is not None
        and code_selection.project_id == code_project.id
    ):
        available.append("inspect_code_context")
    if evidence_links:
        available.append("inspect_evidence_links")
    return tuple(available)


def start_read_only_assistant(
    question: str,
    *,
    document: OpenedDocument | None,
    reading_selection: ReadingSelection | None,
    conversation: Conversation | None,
    code_project: CodeProject | None,
    code_selection: CodeSelection | None,
    evidence_links: list[EvidenceLink],
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> ReadOnlyAssistantSession:
    """Start one bounded run and perform exactly one model decision."""

    session = create_read_only_assistant_session(question)
    return _advance_read_only_assistant(
        session,
        document=document,
        reading_selection=reading_selection,
        conversation=conversation,
        code_project=code_project,
        code_selection=code_selection,
        evidence_links=evidence_links,
        llm_provider=llm_provider,
        settings=settings,
    )


def continue_read_only_assistant(
    session: ReadOnlyAssistantSession,
    *,
    document: OpenedDocument | None,
    reading_selection: ReadingSelection | None,
    conversation: Conversation | None,
    code_project: CodeProject | None,
    code_selection: CodeSelection | None,
    evidence_links: list[EvidenceLink],
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> ReadOnlyAssistantSession:
    """Continue only after the user has reviewed the pending tool result."""

    if session.status != "awaiting_user":
        raise ValueError(
            "Only a read-only assistant waiting for user confirmation can continue."
        )
    return _advance_read_only_assistant(
        session,
        document=document,
        reading_selection=reading_selection,
        conversation=conversation,
        code_project=code_project,
        code_selection=code_selection,
        evidence_links=evidence_links,
        llm_provider=llm_provider,
        settings=settings,
    )


def stop_read_only_assistant(
    session: ReadOnlyAssistantSession,
    *,
    reason: str | None = None,
) -> ReadOnlyAssistantSession:
    """Stop a session immediately from an explicit user action."""

    return stop_read_only_assistant_session(
        session,
        stop_reason="user_stopped",
        requested_action="user_stop",
        error_message=(reason or "Stopped by the user.").strip(),
    )


def _advance_read_only_assistant(
    session: ReadOnlyAssistantSession,
    *,
    document: OpenedDocument | None,
    reading_selection: ReadingSelection | None,
    conversation: Conversation | None,
    code_project: CodeProject | None,
    code_selection: CodeSelection | None,
    evidence_links: list[EvidenceLink],
    llm_provider: LlmProvider | None,
    settings: Settings | None,
) -> ReadOnlyAssistantSession:
    if session.llm_call_count >= MAX_ASSISTANT_LLM_CALLS:
        return stop_read_only_assistant_session(
            session,
            stop_reason="llm_budget",
            requested_action="budget_check",
            error_message="The four-call model budget was exhausted.",
        )

    resolved_settings = settings or load_settings()
    available_tools = get_available_assistant_tools(
        document=document,
        reading_selection=reading_selection,
        code_project=code_project,
        code_selection=code_selection,
        evidence_links=evidence_links,
    )
    request_messages = build_read_only_assistant_prompt(
        session.question,
        tool_results=session.tool_results,
        available_tools=available_tools,
        remaining_tool_calls=max(
            0,
            MAX_ASSISTANT_TOOL_CALLS - session.tool_call_count,
        ),
    )
    request_character_count = _request_character_count(request_messages)
    provider = llm_provider or create_llm_provider(resolved_settings)
    try:
        response = provider.complete(request_messages)
    except LlmError as error:
        return stop_read_only_assistant_session(
            session,
            stop_reason="provider_error",
            requested_action="provider_call",
            error_message=str(error),
            request_character_count=request_character_count,
            llm_call_increment=1,
        )

    response_character_count = len(response)
    try:
        action = parse_assistant_action(response)
    except LlmError as error:
        return stop_read_only_assistant_session(
            session,
            stop_reason="invalid_protocol",
            requested_action="invalid_protocol",
            error_message=str(error),
            request_character_count=request_character_count,
            response_character_count=response_character_count,
            llm_call_increment=1,
        )

    if action.action == "final":
        return record_assistant_final_step(
            session,
            action,
            request_character_count=request_character_count,
            response_character_count=response_character_count,
        )

    stop_reason = tool_request_stop_reason(session, action.action)
    if stop_reason is not None:
        return stop_read_only_assistant_session(
            session,
            stop_reason=stop_reason,
            requested_action=action.action,
            error_message="The requested tool is not permitted at this step.",
            request_character_count=request_character_count,
            response_character_count=response_character_count,
            llm_call_increment=1,
        )

    try:
        tool_result = _execute_read_only_assistant_tool(
            action.action,
            question=session.question,
            document=document,
            reading_selection=reading_selection,
            conversation=conversation,
            code_project=code_project,
            code_selection=code_selection,
            evidence_links=evidence_links,
            settings=resolved_settings,
        )
    except ValueError as error:
        return stop_read_only_assistant_session(
            session,
            stop_reason="tool_error",
            requested_action=action.action,
            error_message=str(error),
            request_character_count=request_character_count,
            response_character_count=response_character_count,
            llm_call_increment=1,
        )

    output_stop_reason = tool_output_stop_reason(session, tool_result)
    if output_stop_reason is not None:
        return stop_read_only_assistant_session(
            session,
            stop_reason=output_stop_reason,
            requested_action=action.action,
            error_message="The local tool output exceeded the assistant budget.",
            request_character_count=request_character_count,
            response_character_count=response_character_count,
            llm_call_increment=1,
        )
    return record_assistant_tool_step(
        session,
        action,
        tool_result,
        request_character_count=request_character_count,
        response_character_count=response_character_count,
    )


def _execute_read_only_assistant_tool(
    tool_name: AssistantToolName,
    *,
    question: str,
    document: OpenedDocument | None,
    reading_selection: ReadingSelection | None,
    conversation: Conversation | None,
    code_project: CodeProject | None,
    code_selection: CodeSelection | None,
    evidence_links: list[EvidenceLink],
    settings: Settings,
) -> AssistantToolResult:
    """Dispatch one fixed no-argument read-only tool without reflection."""

    if tool_name == "inspect_paper_context":
        if document is None or reading_selection is None:
            return AssistantToolResult(
                tool_name=tool_name,
                status="unavailable",
                source_summary="No current paper selection",
                content="No paper selection is available in the current session.",
            )
        context = _build_context(
            reading_selection,
            document=document,
            conversation=conversation,
            user_question=question,
            settings=settings,
        )
        return AssistantToolResult(
            tool_name=tool_name,
            status="available",
            source_summary=_paper_source_summary(context),
            content=_serialize_paper_context(context),
        )

    if tool_name == "inspect_code_context":
        if code_project is None or code_selection is None:
            return AssistantToolResult(
                tool_name=tool_name,
                status="unavailable",
                source_summary="No current code selection",
                content="No code selection is available in the current session.",
            )
        context = _build_code_explanation_context(
            code_project,
            code_selection,
            question=question,
            settings=settings,
        )
        return AssistantToolResult(
            tool_name=tool_name,
            status="available",
            source_summary=(
                f"{context.project_name}:"
                f"{context.relative_path}:{context.start_line}-{context.end_line}"
            ),
            content=_serialize_code_context(context),
        )

    if tool_name == "inspect_evidence_links":
        if not evidence_links:
            return AssistantToolResult(
                tool_name=tool_name,
                status="unavailable",
                source_summary="No current evidence links",
                content="No paper-to-code evidence links exist in the current session.",
            )
        return AssistantToolResult(
            tool_name=tool_name,
            status="available",
            source_summary=f"{len(evidence_links)} current evidence link(s)",
            content=_serialize_evidence_links(evidence_links),
        )

    raise ValueError("Unsupported read-only assistant tool.")


def _paper_source_summary(context: ResearchContext) -> str:
    if context.page_number is None:
        return f"{context.document_title}: unlocated selection"
    return f"{context.document_title}: page {context.page_number}"


def _serialize_paper_context(context: ResearchContext) -> str:
    bbox = (
        ""
        if context.bbox is None
        else ", ".join(f"{coordinate:.2f}" for coordinate in context.bbox)
    )
    history = "\n".join(
        f"- {message.role}/{message.task}: {message.content}"
        for message in context.conversation_history
    )
    fields = (
        ("Document", context.document_title),
        ("Author", context.author),
        ("Source type", context.source),
        ("Page", "" if context.page_number is None else str(context.page_number)),
        (
            "Block",
            "" if context.block_index is None else str(context.block_index),
        ),
        ("Bounding box", bbox),
        ("Section", context.section_heading),
        ("Related caption", context.related_caption),
        ("Related formula", context.related_formula),
        ("Surrounding text", context.surrounding_text),
        ("Selected text", context.selected_text),
        ("Budgeted conversation", history or "(none)"),
    )
    return "\n".join(f"{name}: {value}" for name, value in fields)


def _serialize_code_context(context: CodeContext) -> str:
    fields = (
        ("Project", context.project_name),
        ("Source type", context.source),
        ("Relative path", context.relative_path),
        ("Lines", f"{context.start_line}-{context.end_line}"),
        ("Symbol kind", context.symbol_kind or ""),
        ("Symbol name", context.symbol_name or ""),
        ("Extraction method", context.extraction_method),
        ("Surrounding code", context.surrounding_code),
        ("Selected code", context.selected_code),
    )
    return "\n".join(f"{name}: {value}" for name, value in fields)


def _serialize_evidence_links(evidence_links: list[EvidenceLink]) -> str:
    rendered: list[str] = []
    for index, link in enumerate(evidence_links, start=1):
        paper_bbox = (
            ""
            if link.paper.bbox is None
            else ", ".join(
                f"{coordinate:.2f}" for coordinate in link.paper.bbox
            )
        )
        rendered.extend(
            (
                f"[Evidence link {index}]",
                f"Relation: {link.relation}",
                f"Confidence: {link.confidence:.2f}",
                f"Generation method: {link.generation_method}",
                f"Rationale: {link.rationale or ''}",
                f"Paper title: {link.paper.document_title}",
                f"Paper evidence kind: {link.paper.evidence_kind}",
                f"Paper page: {link.paper.page_number}",
                (
                    "Paper block: "
                    + (
                        ""
                        if link.paper.block_index is None
                        else str(link.paper.block_index)
                    )
                ),
                f"Paper bounding box: {paper_bbox}",
                f"Paper excerpt: {link.paper.excerpt}",
                f"Code project: {link.code.project_name}",
                f"Code relative path: {link.code.relative_path}",
                f"Code lines: {link.code.start_line}-{link.code.end_line}",
                f"Code symbol kind: {link.code.symbol_kind or ''}",
                f"Code symbol name: {link.code.symbol_name or ''}",
                f"Code extraction method: {link.code.extraction_method}",
                f"Code excerpt: {link.code.excerpt}",
                "",
            )
        )
    return "\n".join(rendered).rstrip()


def capture_knowledge(
    document: OpenedDocument,
    selection: ReadingSelection | None,
    messages: list[Message],
    user_notes: str,
    tags: list[str],
    *,
    title: str | None = None,
    evidence_links: list[EvidenceLink] | None = None,
) -> KnowledgeNote:
    """Assemble selected reading and conversation content into a KnowledgeNote."""

    return KnowledgeNote(
        title=_knowledge_title(title, document, selection),
        source=document.document.title,
        source_type=(
            document.document.source_type
            if selection is None
            else selection.source_type
        ),
        authors=list(document.document.authors),
        page_number=_selection_page_number(selection),
        block_index=_selection_block_index(selection),
        bbox=_selection_bbox(selection),
        selected_text=_optional_text(None if selection is None else selection.text),
        translation=_joined_message_content(
            messages,
            role="assistant",
            tasks={"translate"},
        ),
        latex=_joined_message_content(
            messages,
            role="assistant",
            tasks={"convert:latex"},
        ),
        question=_joined_message_content(
            messages,
            role="user",
            tasks={
                "explain:concept",
                "explain:math",
                "explain:algorithm",
                "explain:contextual",
                "convert:latex",
                "followup",
            },
        ),
        ai_explanation=_joined_message_content(
            messages,
            role="assistant",
            tasks={
                "explain:concept",
                "explain:math",
                "explain:algorithm",
                "explain:contextual",
                "followup",
            },
        ),
        user_notes=_optional_text(user_notes),
        tags=_normalized_tags(tags),
        evidence_links=list(evidence_links or []),
    )


def capture_code_knowledge(
    project: CodeProject,
    selection: CodeSelection,
    response: Message | None,
    *,
    question: str,
    response_question: str | None = None,
    user_notes: str,
    tags: list[str],
    title: str | None = None,
) -> KnowledgeNote:
    """Assemble one current code selection into a path-safe knowledge note."""

    _validate_code_knowledge_selection(project, selection)
    explanation: str | None = None
    if response is not None:
        if (
            response.role != "assistant"
            or response.task != "explain:code"
            or response.selection_id != selection.id
        ):
            raise ValueError(
                "Code explanation does not belong to the current code selection."
            )
        if _optional_text(response_question) != _optional_text(question):
            raise ValueError(
                "Code explanation does not belong to the current code question."
            )
        explanation = _optional_text(response.content)

    return KnowledgeNote(
        title=_code_knowledge_title(title, project, selection),
        source=project.name,
        source_type="code",
        selected_text=selection.text,
        question=_optional_text(question),
        ai_explanation=explanation,
        user_notes=_optional_text(user_notes),
        tags=_normalized_tags(tags),
        code_selection=selection,
    )


def save_note_to_vault(
    note: KnowledgeNote,
    *,
    settings: Settings | None = None,
) -> Path:
    """Write a note through the sole Obsidian Vault integration boundary."""

    resolved_settings = settings or load_settings()
    if resolved_settings.obsidian_vault_path is None:
        raise VaultConfigurationError(
            "OBSIDIAN_VAULT_PATH is not configured. Add it before saving notes."
        )
    return write_note_to_vault(
        note,
        vault_path=resolved_settings.obsidian_vault_path,
        subdirectory=resolved_settings.obsidian_subdirectory,
    )


def preview_note_markdown(note: KnowledgeNote) -> str:
    """Render a note for UI preview through the application API."""

    return render_markdown(note)


def _build_explanation_context(
    selection: ReadingSelection,
    mode: ExplainMode,
    *,
    document: OpenedDocument,
    conversation: Conversation | None,
    question: str | None,
    settings: Settings,
) -> ResearchContext:
    _validate_explain_mode(mode)
    return _build_context(
        selection,
        document=document,
        conversation=conversation,
        user_question=question or _DEFAULT_QUESTIONS[mode],
        settings=settings,
    )


def _build_context(
    selection: ReadingSelection,
    *,
    document: OpenedDocument,
    conversation: Conversation | None,
    user_question: str,
    settings: Settings,
) -> ResearchContext:
    return build_research_context(
        selection,
        document.document,
        document.pages,
        user_question=user_question,
        conversation=conversation,
        context_token_budget=settings.context_token_budget,
        history_token_budget=settings.history_token_budget,
    )


def _context_evidence_preview(
    context: ResearchContext,
    request_messages: list[ChatMessage],
) -> ContextEvidencePreview:
    request_character_count = _request_character_count(request_messages)
    approximate_request_tokens = _approximate_tokens(
        request_character_count
    )
    return ContextEvidencePreview(
        document_title=context.document_title,
        author=context.author,
        source_type=context.source,
        page_number=context.page_number,
        block_index=context.block_index,
        bbox=context.bbox,
        selected_text=context.selected_text,
        section_heading=context.section_heading,
        related_caption=context.related_caption,
        related_formula=context.related_formula,
        surrounding_text=context.surrounding_text,
        user_question=context.user_question,
        history_message_count=len(context.conversation_history),
        request_character_count=request_character_count,
        approximate_request_tokens=approximate_request_tokens,
    )


def _build_code_explanation_context(
    project: CodeProject,
    selection: CodeSelection,
    *,
    question: str,
    settings: Settings,
) -> CodeContext:
    if selection.project_id != project.id:
        raise ValueError("Code selection does not belong to the opened project.")
    code_file = core_get_code_file(project, selection.relative_path)
    return build_code_context(
        selection,
        code_file,
        user_question=question,
        context_token_budget=settings.context_token_budget,
    )


def _request_character_count(request_messages: list[ChatMessage]) -> int:
    return sum(len(message.content) for message in request_messages)


def _approximate_tokens(character_count: int) -> int:
    return (
        character_count + APPROXIMATE_CHARS_PER_TOKEN - 1
    ) // APPROXIMATE_CHARS_PER_TOKEN


def _validate_explain_mode(mode: ExplainMode) -> None:
    if mode not in _EXPLANATION_BUILDERS:
        allowed = ", ".join(_EXPLANATION_BUILDERS)
        raise ValueError(f"Explain mode must be one of: {allowed}.")


def _validated_followup_question(question: str) -> str:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Follow-up question must not be blank.")
    return normalized_question


def _knowledge_title(
    title: str | None,
    document: OpenedDocument,
    selection: ReadingSelection | None,
) -> str:
    requested_title = _single_line(title)
    if requested_title:
        return requested_title

    if selection is not None:
        selection_title = _single_line(selection.text)
        if selection_title:
            return selection_title[:80].rstrip()
    return _single_line(document.document.title) or "Research note"


def _code_knowledge_title(
    title: str | None,
    project: CodeProject,
    selection: CodeSelection,
) -> str:
    requested_title = _single_line(title)
    if requested_title:
        return requested_title
    if selection.symbol_name:
        return f"{project.name} · {_single_line(selection.symbol_name)}"
    return (
        f"{project.name} · {selection.relative_path}:"
        f"{selection.start_line}-{selection.end_line}"
    )


def _validate_code_knowledge_selection(
    project: CodeProject,
    selection: CodeSelection,
) -> None:
    if (
        selection.project_id != project.id
        or selection.project_name != project.name
    ):
        raise ValueError("Code selection does not belong to the opened project.")
    code_file = core_get_code_file(project, selection.relative_path)
    if selection.relative_path != code_file.relative_path:
        raise ValueError("Code selection must use a normalized relative path.")
    current_lines = select_code_lines(
        project,
        selection.relative_path,
        start_line=selection.start_line,
        end_line=selection.end_line,
    )
    if current_lines.text != selection.text:
        raise ValueError("Code selection no longer matches the indexed source.")
    if selection.extraction_method == "text":
        if selection.symbol_kind is not None or selection.symbol_name is not None:
            raise ValueError("Line-range code selection cannot claim an AST symbol.")
        return
    if selection.extraction_method != "ast":
        raise ValueError("Code selection extraction method is unsupported.")
    if not any(
        symbol.start_line == selection.start_line
        and symbol.end_line == selection.end_line
        and symbol.kind == selection.symbol_kind
        and symbol.qualified_name == selection.symbol_name
        for symbol in code_file.symbols
    ):
        raise ValueError("Code selection no longer matches an indexed AST symbol.")


def _selection_page_number(selection: ReadingSelection | None) -> int | None:
    if selection is None or selection.locator is None:
        return None
    page_number = selection.locator.get("page_number")
    if isinstance(page_number, int) and not isinstance(page_number, bool):
        return page_number
    return None


def _selection_block_index(selection: ReadingSelection | None) -> int | None:
    if selection is None or selection.locator is None:
        return None
    block_index = selection.locator.get("block_index")
    if isinstance(block_index, int) and not isinstance(block_index, bool):
        return block_index
    return None


def _selection_bbox(selection: ReadingSelection | None) -> BoundingBox | None:
    if selection is None or selection.locator is None:
        return None
    value = selection.locator.get("bbox")
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if not all(
        isinstance(coordinate, (int, float))
        and not isinstance(coordinate, bool)
        for coordinate in value
    ):
        return None
    return tuple(float(coordinate) for coordinate in value)


def _joined_message_content(
    messages: list[Message],
    *,
    role: str,
    tasks: set[str],
) -> str | None:
    selected_content = [
        content
        for message in messages
        if message.role == role
        and message.task in tasks
        and (content := message.content.strip())
    ]
    return "\n\n".join(selected_content) or None


def _normalized_tags(tags: list[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = _single_line(tag)
        identity = normalized.casefold()
        if normalized and identity not in seen:
            normalized_tags.append(normalized)
            seen.add(identity)
    return normalized_tags


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _single_line(value: str | None) -> str:
    return "" if value is None else " ".join(value.split())
