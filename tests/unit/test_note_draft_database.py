"""G4-B repository tests for durable drafts and evidence snapshots."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest

from researchmind.database import (
    LibraryConflictError,
    LibraryNotFoundError,
    LibraryRepository,
    NoteDraftRepository,
    initialize_database,
)
from researchmind.database.schema import connection_scope
from researchmind.models import (
    AssetReference,
    EvidenceSnapshot,
    LibraryRecord,
    NoteDraft,
)


NOW = datetime(2026, 9, 8, 8, 0, tzinfo=UTC)


def test_draft_and_evidence_survive_repository_restart(
    tmp_path: Path,
) -> None:
    database_path, record, asset = _database_with_source(tmp_path)
    repository = NoteDraftRepository(database_path)
    draft = _draft(record.id, asset.id)
    repository.create_draft(draft)

    draft, first = repository.add_evidence(
        _evidence(draft.id, record.id, asset),
        expected_draft_revision=1,
        updated_at=NOW + timedelta(minutes=1),
    )
    draft, second = repository.add_evidence(
        replace(
            _evidence(draft.id, record.id, asset),
            id="evidence-2",
            kind="translation",
            content="梯度指向上升方向。",
            origin="translation_provider",
        ),
        expected_draft_revision=2,
        updated_at=NOW + timedelta(minutes=2),
    )

    reopened = NoteDraftRepository(database_path)

    assert reopened.get_draft(draft.id).revision == 3
    assert reopened.list_drafts(record_id=record.id) == [draft]
    assert reopened.list_evidence(draft.id) == [first, second]
    assert reopened.evidence_source_state(first) == "current"


def test_edits_inclusion_and_order_use_optimistic_revision(
    tmp_path: Path,
) -> None:
    database_path, record, asset = _database_with_source(tmp_path)
    repository = NoteDraftRepository(database_path)
    draft = repository.create_draft(_draft(record.id, asset.id))
    draft, first = repository.add_evidence(
        _evidence(draft.id, record.id, asset),
        expected_draft_revision=1,
        updated_at=NOW + timedelta(minutes=1),
    )
    draft, second = repository.add_evidence(
        replace(_evidence(draft.id, record.id, asset), id="evidence-2"),
        expected_draft_revision=2,
        updated_at=NOW + timedelta(minutes=2),
    )

    draft, excluded = repository.set_evidence_included(
        draft.id,
        first.id,
        included=False,
        expected_draft_revision=3,
        updated_at=NOW + timedelta(minutes=3),
    )
    draft, ordered = repository.reorder_evidence(
        draft.id,
        [second.id, first.id],
        expected_draft_revision=4,
        updated_at=NOW + timedelta(minutes=4),
    )
    edited = replace(
        draft,
        title="Edited",
        body_markdown="# Edited\n",
        revision=6,
        updated_at=NOW + timedelta(minutes=5),
    )
    stored = repository.update_draft(edited, expected_revision=5)

    assert excluded.content == first.content
    assert [item.id for item in ordered] == [second.id, first.id]
    assert repository.list_evidence(draft.id, included_only=True) == [
        ordered[0]
    ]
    assert stored.title == "Edited"
    assert stored.revision == 6
    with pytest.raises(LibraryConflictError, match="changed"):
        repository.update_draft(
            replace(stored, revision=5),
            expected_revision=4,
        )


def test_failed_evidence_insert_rolls_back_draft_revision(
    tmp_path: Path,
) -> None:
    database_path, first_record, first_asset = _database_with_source(tmp_path)
    library = LibraryRepository(database_path)
    second_record = _record("record-2")
    second_asset = _asset("asset-2", second_record.id, 1, b"second")
    library.create_entry(second_record, second_asset)
    repository = NoteDraftRepository(database_path)
    draft = repository.create_draft(_draft(first_record.id, first_asset.id))
    mismatched = replace(
        _evidence(draft.id, first_record.id, first_asset),
        source_asset_id=second_asset.id,
    )

    with pytest.raises(LibraryConflictError, match="conflicts"):
        repository.add_evidence(
            mismatched,
            expected_draft_revision=1,
            updated_at=NOW + timedelta(minutes=1),
        )

    assert repository.get_draft(draft.id).revision == 1
    assert repository.list_evidence(draft.id) == []


def test_reorder_requires_exact_current_set_and_rolls_back(
    tmp_path: Path,
) -> None:
    database_path, record, asset = _database_with_source(tmp_path)
    repository = NoteDraftRepository(database_path)
    draft = repository.create_draft(_draft(record.id, asset.id))
    draft, evidence = repository.add_evidence(
        _evidence(draft.id, record.id, asset),
        expected_draft_revision=1,
        updated_at=NOW + timedelta(minutes=1),
    )

    with pytest.raises(LibraryConflictError, match="every current"):
        repository.reorder_evidence(
            draft.id,
            [],
            expected_draft_revision=2,
            updated_at=NOW + timedelta(minutes=2),
        )

    assert repository.get_draft(draft.id).revision == 2
    assert repository.list_evidence(draft.id) == [evidence]


def test_source_becomes_stale_after_new_asset_revision(
    tmp_path: Path,
) -> None:
    database_path, record, asset = _database_with_source(tmp_path)
    drafts = NoteDraftRepository(database_path)
    draft = drafts.create_draft(_draft(record.id, asset.id))
    _draft_after, evidence = drafts.add_evidence(
        _evidence(draft.id, record.id, asset),
        expected_draft_revision=1,
        updated_at=NOW + timedelta(minutes=1),
    )
    LibraryRepository(database_path).add_revision(
        _asset("asset-2", record.id, 2, b"revision two")
    )
    detached = replace(
        evidence,
        id="evidence-detached",
        source_record_id=None,
        source_asset_id=None,
        source_revision=None,
        source_sha256=None,
    )

    assert drafts.evidence_source_state(evidence) == "stale"
    assert drafts.evidence_source_state(detached) == "detached"


def test_deleting_draft_cascades_only_internal_evidence(
    tmp_path: Path,
) -> None:
    database_path, record, asset = _database_with_source(tmp_path)
    drafts = NoteDraftRepository(database_path)
    draft = drafts.create_draft(_draft(record.id, asset.id))
    draft, _evidence_item = drafts.add_evidence(
        _evidence(draft.id, record.id, asset),
        expected_draft_revision=1,
        updated_at=NOW + timedelta(minutes=1),
    )

    drafts.delete_draft(draft.id, expected_revision=2)

    with pytest.raises(LibraryNotFoundError):
        drafts.get_draft(draft.id)
    with connection_scope(database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence_snapshots"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM asset_references"
        ).fetchone()[0] == 1


def test_corrupt_stored_locator_is_reported_as_database_error(
    tmp_path: Path,
) -> None:
    database_path, record, asset = _database_with_source(tmp_path)
    drafts = NoteDraftRepository(database_path)
    draft = drafts.create_draft(_draft(record.id, asset.id))
    draft, evidence = drafts.add_evidence(
        _evidence(draft.id, record.id, asset),
        expected_draft_revision=1,
        updated_at=NOW + timedelta(minutes=1),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE evidence_snapshots SET locator_json = ? WHERE id = ?",
            ("not-json", evidence.id),
        )

    from researchmind.database import LibraryDatabaseError

    with pytest.raises(LibraryDatabaseError, match="stored note evidence"):
        drafts.list_evidence(draft.id)


def _database_with_source(
    tmp_path: Path,
) -> tuple[Path, LibraryRecord, AssetReference]:
    database_path = initialize_database(tmp_path / "researchmind.sqlite3")
    record = _record("record-1")
    asset = _asset("asset-1", record.id, 1, b"first")
    LibraryRepository(database_path).create_entry(record, asset)
    return database_path, record, asset


def _record(record_id: str) -> LibraryRecord:
    return LibraryRecord(
        id=record_id,
        kind="paper",
        title=f"Paper {record_id}",
        created_at=NOW,
        updated_at=NOW,
    )


def _asset(
    asset_id: str,
    record_id: str,
    revision: int,
    content: bytes,
) -> AssetReference:
    return AssetReference(
        id=asset_id,
        record_id=record_id,
        kind="pdf",
        relative_path=f"papers/{asset_id}.pdf",
        sha256=sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type="application/pdf",
        revision=revision,
        managed=True,
        created_at=NOW + timedelta(minutes=revision),
    )


def _draft(record_id: str, asset_id: str) -> NoteDraft:
    return NoteDraft(
        id="draft-1",
        record_id=record_id,
        asset_id=asset_id,
        title="A draft",
        body_markdown="## Notes\n",
        status="active",
        revision=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _evidence(
    draft_id: str,
    record_id: str,
    asset: AssetReference,
) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        id="evidence-1",
        draft_id=draft_id,
        kind="source_text",
        content="Selected text",
        source_label="Paper · page 1",
        locator={"page_number": 1},
        origin="browser_selection",
        source_record_id=record_id,
        source_asset_id=asset.id,
        source_revision=asset.revision,
        source_sha256=asset.sha256,
        selection_id="selection-1",
        included=True,
        sort_order=0,
        created_at=NOW,
    )
