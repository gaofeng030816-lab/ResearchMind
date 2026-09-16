"""SQLite repository for durable note drafts and explicit evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from researchmind.database.errors import (
    LibraryConflictError,
    LibraryDatabaseError,
    LibraryNotFoundError,
)
from researchmind.database.schema import connection_scope
from researchmind.models import (
    EvidenceSnapshot,
    EvidenceSourceState,
    NoteDraft,
    NoteDraftStatus,
)


_DRAFT_SELECT = """
SELECT id, record_id, asset_id, title, body_markdown, status, revision,
       created_at, updated_at
FROM note_drafts
"""

_EVIDENCE_SELECT = """
SELECT id, draft_id, kind, content, source_label, locator_json, origin,
       source_record_id, source_asset_id, source_revision, source_sha256,
       selection_id, included, sort_order, created_at
FROM evidence_snapshots
"""

_MAX_EVIDENCE_ITEMS_PER_DRAFT = 200


class NoteDraftRepository:
    """Persist editable drafts separately from immutable evidence content."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def create_draft(self, draft: NoteDraft) -> NoteDraft:
        try:
            with connection_scope(self.database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO note_drafts(
                        id, record_id, asset_id, title, body_markdown,
                        status, revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _draft_values(draft),
                )
        except sqlite3.IntegrityError as exc:
            raise LibraryConflictError(
                "The note draft conflicts with existing library data."
            ) from exc
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not create the note draft."
            ) from exc
        return self.get_draft(draft.id)

    def get_draft(self, draft_id: str) -> NoteDraft:
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    _DRAFT_SELECT + " WHERE id = ?",
                    (draft_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not read the note draft."
            ) from exc
        if row is None:
            raise LibraryNotFoundError("Note draft does not exist.")
        return _draft_from_row(row)

    def list_drafts(
        self,
        *,
        record_id: str | None = None,
        status: NoteDraftStatus | None = None,
    ) -> list[NoteDraft]:
        filters: list[str] = []
        values: list[object] = []
        if record_id is not None:
            filters.append("record_id = ?")
            values.append(record_id)
        if status is not None:
            filters.append("status = ?")
            values.append(status)
        query = _DRAFT_SELECT
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY updated_at DESC, id"
        try:
            with connection_scope(self.database_path) as connection:
                rows = connection.execute(query, values).fetchall()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not list note drafts."
            ) from exc
        return [_draft_from_row(row) for row in rows]

    def update_draft(
        self,
        draft: NoteDraft,
        *,
        expected_revision: int,
    ) -> NoteDraft:
        if draft.revision != expected_revision + 1:
            raise ValueError(
                "The updated draft revision must follow the expected revision."
            )
        try:
            with connection_scope(self.database_path) as connection:
                cursor = connection.execute(
                    """
                    UPDATE note_drafts
                    SET record_id = ?, asset_id = ?, title = ?,
                        body_markdown = ?, status = ?, revision = ?,
                        updated_at = ?
                    WHERE id = ? AND revision = ?
                    """,
                    (
                        draft.record_id,
                        draft.asset_id,
                        draft.title,
                        draft.body_markdown,
                        draft.status,
                        draft.revision,
                        _to_text(draft.updated_at),
                        draft.id,
                        expected_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    _raise_missing_or_conflict(
                        connection,
                        draft.id,
                    )
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.IntegrityError as exc:
            raise LibraryConflictError(
                "The updated draft conflicts with library data."
            ) from exc
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not update the note draft."
            ) from exc
        return self.get_draft(draft.id)

    def delete_draft(
        self,
        draft_id: str,
        *,
        expected_revision: int,
    ) -> None:
        try:
            with connection_scope(self.database_path) as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM note_drafts
                    WHERE id = ? AND revision = ?
                    """,
                    (draft_id, expected_revision),
                )
                if cursor.rowcount != 1:
                    _raise_missing_or_conflict(connection, draft_id)
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not delete the note draft."
            ) from exc

    def add_evidence(
        self,
        snapshot: EvidenceSnapshot,
        *,
        expected_draft_revision: int,
        updated_at: datetime,
    ) -> tuple[NoteDraft, EvidenceSnapshot]:
        try:
            with connection_scope(self.database_path) as connection:
                draft = _bump_draft(
                    connection,
                    snapshot.draft_id,
                    expected_revision=expected_draft_revision,
                    updated_at=updated_at,
                )
                row = connection.execute(
                    """
                    SELECT COUNT(*), COALESCE(MAX(sort_order) + 1, 0)
                    FROM evidence_snapshots WHERE draft_id = ?
                    """,
                    (snapshot.draft_id,),
                ).fetchone()
                if int(row[0]) >= _MAX_EVIDENCE_ITEMS_PER_DRAFT:
                    raise LibraryConflictError(
                        "The note draft evidence limit has been reached."
                    )
                stored = replace(snapshot, sort_order=int(row[1]))
                connection.execute(
                    """
                    INSERT INTO evidence_snapshots(
                        id, draft_id, kind, content, source_label,
                        locator_json, origin, source_record_id,
                        source_asset_id, source_revision, source_sha256,
                        selection_id, included, sort_order, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _evidence_values(stored),
                )
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.IntegrityError as exc:
            raise LibraryConflictError(
                "The evidence conflicts with existing draft data."
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ValueError("Evidence locator is not valid JSON data.") from exc
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not add evidence to the note draft."
            ) from exc
        return draft, stored

    def get_evidence(
        self,
        draft_id: str,
        evidence_id: str,
    ) -> EvidenceSnapshot:
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    _EVIDENCE_SELECT + " WHERE draft_id = ? AND id = ?",
                    (draft_id, evidence_id),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not read note evidence."
            ) from exc
        if row is None:
            raise LibraryNotFoundError("Note evidence does not exist.")
        return _evidence_from_row(row)

    def list_evidence(
        self,
        draft_id: str,
        *,
        included_only: bool = False,
    ) -> list[EvidenceSnapshot]:
        query = _EVIDENCE_SELECT + " WHERE draft_id = ?"
        if included_only:
            query += " AND included = 1"
        query += " ORDER BY sort_order, id"
        try:
            with connection_scope(self.database_path) as connection:
                draft_exists = connection.execute(
                    "SELECT 1 FROM note_drafts WHERE id = ?",
                    (draft_id,),
                ).fetchone()
                if draft_exists is None:
                    raise LibraryNotFoundError(
                        "Note draft does not exist."
                    )
                rows = connection.execute(query, (draft_id,)).fetchall()
        except LibraryNotFoundError:
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not list note evidence."
            ) from exc
        return [_evidence_from_row(row) for row in rows]

    def set_evidence_included(
        self,
        draft_id: str,
        evidence_id: str,
        *,
        included: bool,
        expected_draft_revision: int,
        updated_at: datetime,
    ) -> tuple[NoteDraft, EvidenceSnapshot]:
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    _EVIDENCE_SELECT + " WHERE draft_id = ? AND id = ?",
                    (draft_id, evidence_id),
                ).fetchone()
                if row is None:
                    raise LibraryNotFoundError(
                        "Note evidence does not exist."
                    )
                current = _evidence_from_row(row)
                _require_draft_revision(
                    connection,
                    draft_id,
                    expected_draft_revision,
                )
                if current.included == included:
                    return (
                        _draft_from_connection(connection, draft_id),
                        current,
                    )
                draft = _bump_draft(
                    connection,
                    draft_id,
                    expected_revision=expected_draft_revision,
                    updated_at=updated_at,
                )
                connection.execute(
                    """
                    UPDATE evidence_snapshots SET included = ?
                    WHERE draft_id = ? AND id = ?
                    """,
                    (int(included), draft_id, evidence_id),
                )
                stored = replace(current, included=included)
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not update note evidence."
            ) from exc
        return draft, stored

    def reorder_evidence(
        self,
        draft_id: str,
        evidence_ids: list[str],
        *,
        expected_draft_revision: int,
        updated_at: datetime,
    ) -> tuple[NoteDraft, list[EvidenceSnapshot]]:
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence order contains duplicate identities.")
        try:
            with connection_scope(self.database_path) as connection:
                rows = connection.execute(
                    _EVIDENCE_SELECT
                    + " WHERE draft_id = ? ORDER BY sort_order, id",
                    (draft_id,),
                ).fetchall()
                current = [_evidence_from_row(row) for row in rows]
                current_ids = [item.id for item in current]
                _require_draft_revision(
                    connection,
                    draft_id,
                    expected_draft_revision,
                )
                if set(current_ids) != set(evidence_ids):
                    raise LibraryConflictError(
                        "Evidence order must contain every current item once."
                    )
                if current_ids == evidence_ids:
                    return _draft_from_connection(connection, draft_id), current
                draft = _bump_draft(
                    connection,
                    draft_id,
                    expected_revision=expected_draft_revision,
                    updated_at=updated_at,
                )
                shift = len(evidence_ids) + 1
                connection.execute(
                    """
                    UPDATE evidence_snapshots
                    SET sort_order = sort_order + ?
                    WHERE draft_id = ?
                    """,
                    (shift, draft_id),
                )
                for sort_order, evidence_id in enumerate(evidence_ids):
                    connection.execute(
                        """
                        UPDATE evidence_snapshots SET sort_order = ?
                        WHERE draft_id = ? AND id = ?
                        """,
                        (sort_order, draft_id, evidence_id),
                    )
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not reorder note evidence."
            ) from exc
        return draft, self.list_evidence(draft_id)

    def remove_evidence(
        self,
        draft_id: str,
        evidence_id: str,
        *,
        expected_draft_revision: int,
        updated_at: datetime,
    ) -> NoteDraft:
        try:
            with connection_scope(self.database_path) as connection:
                draft = _bump_draft(
                    connection,
                    draft_id,
                    expected_revision=expected_draft_revision,
                    updated_at=updated_at,
                )
                row = connection.execute(
                    """
                    SELECT sort_order FROM evidence_snapshots
                    WHERE draft_id = ? AND id = ?
                    """,
                    (draft_id, evidence_id),
                ).fetchone()
                if row is None:
                    raise LibraryNotFoundError(
                        "Note evidence does not exist."
                    )
                removed_order = int(row[0])
                connection.execute(
                    """
                    DELETE FROM evidence_snapshots
                    WHERE draft_id = ? AND id = ?
                    """,
                    (draft_id, evidence_id),
                )
                connection.execute(
                    """
                    UPDATE evidence_snapshots
                    SET sort_order = sort_order - 1
                    WHERE draft_id = ? AND sort_order > ?
                    """,
                    (draft_id, removed_order),
                )
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not remove note evidence."
            ) from exc
        return draft

    def evidence_source_state(
        self,
        snapshot: EvidenceSnapshot,
    ) -> EvidenceSourceState:
        """Compare saved source provenance with the current live asset revision."""

        if snapshot.source_asset_id is None:
            return "detached"
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    """
                    SELECT a.id, a.record_id, a.revision, a.sha256,
                           a.deleted_at, r.removed_at
                    FROM asset_references AS a
                    JOIN library_records AS r ON r.id = a.record_id
                    WHERE a.id = ?
                    """,
                    (snapshot.source_asset_id,),
                ).fetchone()
                latest = connection.execute(
                    """
                    SELECT id FROM asset_references
                    WHERE record_id = ? AND deleted_at IS NULL
                    ORDER BY revision DESC LIMIT 1
                    """,
                    (snapshot.source_record_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not check note evidence provenance."
            ) from exc
        if (
            row is None
            or latest is None
            or row["deleted_at"] is not None
            or row["removed_at"] is not None
        ):
            return "stale"
        if str(row["record_id"]) != snapshot.source_record_id:
            return "stale"
        if (
            snapshot.source_revision is not None
            and int(row["revision"]) != snapshot.source_revision
        ):
            return "stale"
        if (
            snapshot.source_sha256 is not None
            and str(row["sha256"]) != snapshot.source_sha256
        ):
            return "stale"
        if str(latest["id"]) != snapshot.source_asset_id:
            return "stale"
        return "current"


def _bump_draft(
    connection: sqlite3.Connection,
    draft_id: str,
    *,
    expected_revision: int,
    updated_at: datetime,
) -> NoteDraft:
    current = _require_draft_revision(
        connection,
        draft_id,
        expected_revision,
    )
    if updated_at < current.created_at:
        raise ValueError("Draft updated time precedes its creation time.")
    next_revision = expected_revision + 1
    connection.execute(
        """
        UPDATE note_drafts SET revision = ?, updated_at = ?
        WHERE id = ? AND revision = ?
        """,
        (
            next_revision,
            _to_text(updated_at),
            draft_id,
            expected_revision,
        ),
    )
    return replace(
        current,
        revision=next_revision,
        updated_at=updated_at,
    )


def _require_draft_revision(
    connection: sqlite3.Connection,
    draft_id: str,
    expected_revision: int,
) -> NoteDraft:
    row = connection.execute(
        _DRAFT_SELECT + " WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if row is None:
        raise LibraryNotFoundError("Note draft does not exist.")
    draft = _draft_from_row(row)
    if draft.revision != expected_revision:
        raise LibraryConflictError(
            "The note draft changed after it was opened. Reload it first."
        )
    return draft


def _raise_missing_or_conflict(
    connection: sqlite3.Connection,
    draft_id: str,
) -> None:
    row = connection.execute(
        "SELECT 1 FROM note_drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if row is None:
        raise LibraryNotFoundError("Note draft does not exist.")
    raise LibraryConflictError(
        "The note draft changed after it was opened. Reload it first."
    )


def _draft_from_connection(
    connection: sqlite3.Connection,
    draft_id: str,
) -> NoteDraft:
    row = connection.execute(
        _DRAFT_SELECT + " WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if row is None:
        raise LibraryNotFoundError("Note draft does not exist.")
    return _draft_from_row(row)


def _draft_values(draft: NoteDraft) -> tuple[object, ...]:
    return (
        draft.id,
        draft.record_id,
        draft.asset_id,
        draft.title,
        draft.body_markdown,
        draft.status,
        draft.revision,
        _to_text(draft.created_at),
        _to_text(draft.updated_at),
    )


def _evidence_values(snapshot: EvidenceSnapshot) -> tuple[object, ...]:
    return (
        snapshot.id,
        snapshot.draft_id,
        snapshot.kind,
        snapshot.content,
        snapshot.source_label,
        json.dumps(
            snapshot.locator,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        snapshot.origin,
        snapshot.source_record_id,
        snapshot.source_asset_id,
        snapshot.source_revision,
        snapshot.source_sha256,
        snapshot.selection_id,
        int(snapshot.included),
        snapshot.sort_order,
        _to_text(snapshot.created_at),
    )


def _draft_from_row(row: sqlite3.Row) -> NoteDraft:
    return NoteDraft(
        id=str(row["id"]),
        record_id=_optional_text(row["record_id"]),
        asset_id=_optional_text(row["asset_id"]),
        title=str(row["title"]),
        body_markdown=str(row["body_markdown"]),
        status=str(row["status"]),
        revision=int(row["revision"]),
        created_at=_from_text(row["created_at"]),
        updated_at=_from_text(row["updated_at"]),
    )


def _evidence_from_row(row: sqlite3.Row) -> EvidenceSnapshot:
    try:
        locator = json.loads(str(row["locator_json"]))
        if not isinstance(locator, dict):
            raise ValueError("Stored locator is not an object.")
        return EvidenceSnapshot(
            id=str(row["id"]),
            draft_id=str(row["draft_id"]),
            kind=str(row["kind"]),
            content=str(row["content"]),
            source_label=str(row["source_label"]),
            locator=locator,
            origin=str(row["origin"]),
            source_record_id=_optional_text(row["source_record_id"]),
            source_asset_id=_optional_text(row["source_asset_id"]),
            source_revision=(
                None
                if row["source_revision"] is None
                else int(row["source_revision"])
            ),
            source_sha256=_optional_text(row["source_sha256"]),
            selection_id=_optional_text(row["selection_id"]),
            included=bool(row["included"]),
            sort_order=int(row["sort_order"]),
            created_at=_from_text(row["created_at"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LibraryDatabaseError(
            "The stored note evidence is invalid."
        ) from exc


def _to_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Note draft timestamps must include a timezone.")
    return value.isoformat()


def _from_text(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
