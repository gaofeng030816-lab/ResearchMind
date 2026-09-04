"""SQLite repository converting rows to ResearchMind library models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sqlite3
from collections.abc import Callable

from researchmind.database.errors import (
    LibraryConflictError,
    LibraryDatabaseError,
    LibraryNotFoundError,
)
from researchmind.database.schema import connection_scope
from researchmind.models.library import (
    AssetKind,
    AssetReference,
    LibraryEntry,
    LibraryItemKind,
    LibraryRecord,
)
from researchmind.models.zotero import ZoteroSourceLink


_ENTRY_SELECT = """
SELECT
    r.id AS record_id,
    r.kind AS record_kind,
    r.title,
    r.created_at AS record_created_at,
    r.updated_at,
    r.removed_at,
    a.id AS asset_id,
    a.kind AS asset_kind,
    a.relative_path,
    a.sha256,
    a.size_bytes,
    a.media_type,
    a.revision,
    a.managed,
    a.created_at AS asset_created_at,
    a.deleted_at
FROM library_records AS r
JOIN asset_references AS a ON a.record_id = r.id
"""

_ZOTERO_SELECT = """
SELECT
    id, record_id, server_id, library_type, library_id,
    item_key, item_version, item_type, title, creators_json,
    publication_title, published_date, doi, url,
    attachment_key, attachment_version, attachment_filename,
    linked_at, observed_at
FROM zotero_links
"""


class LibraryRepository:
    """Small repository for stable records and immutable asset revisions."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def create_entry(
        self,
        record: LibraryRecord,
        asset: AssetReference,
        *,
        finalize: Callable[[], object] | None = None,
    ) -> LibraryEntry:
        if asset.record_id != record.id:
            raise ValueError(
                "Asset record identity does not match the library record."
            )
        try:
            with connection_scope(self.database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO library_records(
                        id, kind, title, created_at, updated_at, removed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    _record_values(record),
                )
                _insert_asset(connection, asset)
                if finalize is not None:
                    finalize()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not create the library entry."
            ) from exc
        return LibraryEntry(record=record, asset=asset)

    def add_revision(
        self,
        asset: AssetReference,
        *,
        finalize: Callable[[], object] | None = None,
    ) -> LibraryEntry:
        try:
            with connection_scope(self.database_path) as connection:
                record_row = connection.execute(
                    "SELECT 1 FROM library_records WHERE id = ?",
                    (asset.record_id,),
                ).fetchone()
                if record_row is None:
                    raise LibraryNotFoundError(
                        "Library record does not exist."
                    )
                _insert_asset(connection, asset)
                if finalize is not None:
                    finalize()
                connection.execute(
                    "UPDATE library_records SET updated_at = ? WHERE id = ?",
                    (_to_text(asset.created_at), asset.record_id),
                )
        except LibraryNotFoundError:
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not add the library asset revision."
            ) from exc
        return self.get_entry(asset.record_id, include_removed=True)

    def list_entries(
        self,
        *,
        kind: LibraryItemKind | None = None,
        include_removed: bool = False,
    ) -> list[LibraryEntry]:
        filters = [
            "a.deleted_at IS NULL",
            "a.revision = ("
            "SELECT MAX(a2.revision) FROM asset_references AS a2 "
            "WHERE a2.record_id = r.id AND a2.deleted_at IS NULL)",
        ]
        values: list[object] = []
        if not include_removed:
            filters.append("r.removed_at IS NULL")
        if kind is not None:
            filters.append("r.kind = ?")
            values.append(kind)
        query = _ENTRY_SELECT + " WHERE " + " AND ".join(filters)
        query += " ORDER BY r.updated_at DESC, r.id"
        try:
            with connection_scope(self.database_path) as connection:
                rows = connection.execute(query, values).fetchall()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not list the local library."
            ) from exc
        return [_entry_from_row(row) for row in rows]

    def get_entry(
        self,
        record_id: str,
        *,
        include_removed: bool = False,
    ) -> LibraryEntry:
        filters = [
            "r.id = ?",
            "a.deleted_at IS NULL",
        ]
        if not include_removed:
            filters.append("r.removed_at IS NULL")
        query = _ENTRY_SELECT + " WHERE " + " AND ".join(filters)
        query += " ORDER BY a.revision DESC LIMIT 1"
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(query, (record_id,)).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not read the library entry."
            ) from exc
        if row is None:
            raise LibraryNotFoundError("Library entry is unavailable.")
        return _entry_from_row(row)

    def find_by_hash(
        self,
        kind: AssetKind,
        sha256: str,
    ) -> LibraryEntry | None:
        query = _ENTRY_SELECT + " WHERE a.kind = ? AND a.sha256 = ? "
        query += (
            "AND a.deleted_at IS NULL ORDER BY a.created_at DESC LIMIT 1"
        )
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(query, (kind, sha256)).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not check for a duplicate asset."
            ) from exc
        return None if row is None else _entry_from_row(row)

    def assets_for_record(self, record_id: str) -> list[AssetReference]:
        try:
            with connection_scope(self.database_path) as connection:
                rows = connection.execute(
                    """
                    SELECT id, record_id, kind, relative_path, sha256,
                           size_bytes, media_type, revision, managed,
                           created_at, deleted_at
                    FROM asset_references
                    WHERE record_id = ? AND deleted_at IS NULL
                    ORDER BY revision DESC
                    """,
                    (record_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not list managed assets."
            ) from exc
        return [_asset_from_row(row) for row in rows]

    def next_revision(self, record_id: str) -> int:
        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    """
                    SELECT MAX(revision)
                    FROM asset_references
                    WHERE record_id = ?
                    """,
                    (record_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not determine the next revision."
            ) from exc
        if row is None or row[0] is None:
            raise LibraryNotFoundError("Library record does not exist.")
        return int(row[0]) + 1

    def remove_record(
        self,
        record_id: str,
        *,
        removed_at: datetime,
    ) -> None:
        self._set_removed_at(record_id, removed_at)

    def restore_record(
        self,
        record_id: str,
        *,
        updated_at: datetime,
    ) -> None:
        self._set_removed_at(
            record_id,
            None,
            updated_at=updated_at,
        )

    def mark_assets_deleted(
        self,
        record_id: str,
        *,
        asset_ids: list[str],
        deleted_at: datetime,
    ) -> None:
        if not asset_ids:
            return
        placeholders = ", ".join("?" for _ in asset_ids)
        values: list[object] = [
            _to_text(deleted_at),
            record_id,
            *asset_ids,
        ]
        try:
            with connection_scope(self.database_path) as connection:
                cursor = connection.execute(
                    f"""
                    UPDATE asset_references SET deleted_at = ?
                    WHERE record_id = ? AND id IN ({placeholders})
                      AND deleted_at IS NULL
                    """,
                    values,
                )
                if cursor.rowcount != len(asset_ids):
                    raise LibraryNotFoundError(
                        "One or more managed assets are unavailable."
                    )
        except LibraryNotFoundError:
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not update managed asset metadata."
            ) from exc

    def upsert_zotero_link(
        self,
        link: ZoteroSourceLink,
    ) -> ZoteroSourceLink:
        """Create or refresh one paper's stable Zotero source snapshot."""

        try:
            with connection_scope(self.database_path) as connection:
                record = connection.execute(
                    """
                    SELECT kind, removed_at FROM library_records
                    WHERE id = ?
                    """,
                    (link.record_id,),
                ).fetchone()
                if record is None:
                    raise LibraryNotFoundError(
                        "Library record does not exist."
                    )
                if record["kind"] != "paper" or record["removed_at"]:
                    raise LibraryConflictError(
                        "Only an active paper can have a Zotero source link."
                    )

                source_row = connection.execute(
                    """
                    SELECT record_id FROM zotero_links
                    WHERE server_id = ? AND library_type = ?
                      AND library_id = ? AND item_key = ?
                    """,
                    _zotero_identity(link),
                ).fetchone()
                if (
                    source_row is not None
                    and source_row["record_id"] != link.record_id
                ):
                    raise LibraryConflictError(
                        "This Zotero item is already linked to another paper."
                    )

                existing = connection.execute(
                    _ZOTERO_SELECT + " WHERE record_id = ?",
                    (link.record_id,),
                ).fetchone()
                if existing is not None:
                    if _zotero_row_identity(existing) != _zotero_identity(
                        link
                    ):
                        raise LibraryConflictError(
                            "This paper is already linked to a different "
                            "Zotero item."
                        )
                    connection.execute(
                        """
                        UPDATE zotero_links SET
                            item_version = ?, item_type = ?, title = ?,
                            creators_json = ?, publication_title = ?,
                            published_date = ?, doi = ?, url = ?,
                            attachment_key = ?, attachment_version = ?,
                            attachment_filename = ?, observed_at = ?
                        WHERE record_id = ?
                        """,
                        _zotero_refresh_values(link),
                    )
                else:
                    connection.execute(
                        """
                        INSERT INTO zotero_links(
                            id, record_id, server_id, library_type,
                            library_id, item_key, item_version, item_type,
                            title, creators_json, publication_title,
                            published_date, doi, url, attachment_key,
                            attachment_version, attachment_filename,
                            linked_at, observed_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?
                        )
                        """,
                        _zotero_insert_values(link),
                    )
        except (LibraryConflictError, LibraryNotFoundError):
            raise
        except sqlite3.IntegrityError as exc:
            raise LibraryConflictError(
                "The Zotero source link conflicts with existing data."
            ) from exc
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not save the Zotero source link."
            ) from exc
        return self.get_zotero_link(link.record_id)

    def get_zotero_link(self, record_id: str) -> ZoteroSourceLink:
        """Return one durable source snapshot by ResearchMind record."""

        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    _ZOTERO_SELECT + " WHERE record_id = ?",
                    (record_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not read the Zotero source link."
            ) from exc
        if row is None:
            raise LibraryNotFoundError(
                "This paper does not have a Zotero source link."
            )
        return _zotero_from_row(row)

    def find_zotero_link(
        self,
        *,
        server_id: str,
        library_type: str,
        library_id: str,
        item_key: str,
    ) -> ZoteroSourceLink | None:
        """Find a source link inside one explicitly partitioned server."""

        try:
            with connection_scope(self.database_path) as connection:
                row = connection.execute(
                    _ZOTERO_SELECT
                    + " WHERE server_id = ? AND library_type = ? "
                    + "AND library_id = ? AND item_key = ?",
                    (
                        server_id,
                        library_type,
                        library_id,
                        item_key,
                    ),
                ).fetchone()
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not look up the Zotero source link."
            ) from exc
        return None if row is None else _zotero_from_row(row)

    def unlink_zotero_item(self, record_id: str) -> bool:
        """Delete only ResearchMind's source link, never Zotero data."""

        try:
            with connection_scope(self.database_path) as connection:
                cursor = connection.execute(
                    "DELETE FROM zotero_links WHERE record_id = ?",
                    (record_id,),
                )
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not remove the Zotero source link."
            ) from exc
        return cursor.rowcount == 1

    def _set_removed_at(
        self,
        record_id: str,
        removed_at: datetime | None,
        *,
        updated_at: datetime | None = None,
    ) -> None:
        moment = updated_at or removed_at
        if moment is None:
            raise ValueError(
                "An update time is required when restoring a record."
            )
        try:
            with connection_scope(self.database_path) as connection:
                cursor = connection.execute(
                    """
                    UPDATE library_records
                    SET removed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        (
                            None
                            if removed_at is None
                            else _to_text(removed_at)
                        ),
                        _to_text(moment),
                        record_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise LibraryNotFoundError(
                        "Library record does not exist."
                    )
        except LibraryNotFoundError:
            raise
        except sqlite3.Error as exc:
            raise LibraryDatabaseError(
                "Could not update the library record."
            ) from exc


def _insert_asset(
    connection: sqlite3.Connection,
    asset: AssetReference,
) -> None:
    connection.execute(
        """
        INSERT INTO asset_references(
            id, record_id, kind, relative_path, sha256, size_bytes,
            media_type, revision, managed, created_at, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset.id,
            asset.record_id,
            asset.kind,
            asset.relative_path,
            asset.sha256,
            asset.size_bytes,
            asset.media_type,
            asset.revision,
            int(asset.managed),
            _to_text(asset.created_at),
            (
                None
                if asset.deleted_at is None
                else _to_text(asset.deleted_at)
            ),
        ),
    )


def _record_values(record: LibraryRecord) -> tuple[object, ...]:
    return (
        record.id,
        record.kind,
        record.title,
        _to_text(record.created_at),
        _to_text(record.updated_at),
        (
            None
            if record.removed_at is None
            else _to_text(record.removed_at)
        ),
    )


def _entry_from_row(row: sqlite3.Row) -> LibraryEntry:
    record = LibraryRecord(
        id=str(row["record_id"]),
        kind=str(row["record_kind"]),
        title=str(row["title"]),
        created_at=_from_text(row["record_created_at"]),
        updated_at=_from_text(row["updated_at"]),
        removed_at=_optional_datetime(row["removed_at"]),
    )
    asset = AssetReference(
        id=str(row["asset_id"]),
        record_id=record.id,
        kind=str(row["asset_kind"]),
        relative_path=str(row["relative_path"]),
        sha256=str(row["sha256"]),
        size_bytes=int(row["size_bytes"]),
        media_type=str(row["media_type"]),
        revision=int(row["revision"]),
        managed=bool(row["managed"]),
        created_at=_from_text(row["asset_created_at"]),
        deleted_at=_optional_datetime(row["deleted_at"]),
    )
    return LibraryEntry(record=record, asset=asset)


def _asset_from_row(row: sqlite3.Row) -> AssetReference:
    return AssetReference(
        id=str(row["id"]),
        record_id=str(row["record_id"]),
        kind=str(row["kind"]),
        relative_path=str(row["relative_path"]),
        sha256=str(row["sha256"]),
        size_bytes=int(row["size_bytes"]),
        media_type=str(row["media_type"]),
        revision=int(row["revision"]),
        managed=bool(row["managed"]),
        created_at=_from_text(row["created_at"]),
        deleted_at=_optional_datetime(row["deleted_at"]),
    )


def _zotero_identity(link: ZoteroSourceLink) -> tuple[object, ...]:
    return (
        link.server_id,
        link.library_type,
        link.library_id,
        link.item_key,
    )


def _zotero_row_identity(row: sqlite3.Row) -> tuple[object, ...]:
    return (
        str(row["server_id"]),
        str(row["library_type"]),
        str(row["library_id"]),
        str(row["item_key"]),
    )


def _zotero_insert_values(link: ZoteroSourceLink) -> tuple[object, ...]:
    return (
        link.id,
        link.record_id,
        *_zotero_identity(link),
        link.item_version,
        link.item_type,
        link.title,
        _creators_to_json(link.creators),
        link.publication_title,
        link.published_date,
        link.doi,
        link.url,
        link.attachment_key,
        link.attachment_version,
        link.attachment_filename,
        _to_text(link.linked_at),
        _to_text(link.observed_at),
    )


def _zotero_refresh_values(link: ZoteroSourceLink) -> tuple[object, ...]:
    return (
        link.item_version,
        link.item_type,
        link.title,
        _creators_to_json(link.creators),
        link.publication_title,
        link.published_date,
        link.doi,
        link.url,
        link.attachment_key,
        link.attachment_version,
        link.attachment_filename,
        _to_text(link.observed_at),
        link.record_id,
    )


def _creators_to_json(creators: tuple[str, ...]) -> str:
    return json.dumps(
        list(creators),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _zotero_from_row(row: sqlite3.Row) -> ZoteroSourceLink:
    try:
        raw_creators = json.loads(str(row["creators_json"]))
        if not isinstance(raw_creators, list) or not all(
            isinstance(value, str) for value in raw_creators
        ):
            raise ValueError("Invalid creators payload")
        library_type = str(row["library_type"])
        if library_type not in {"user", "group"}:
            raise ValueError("Invalid library type")
        return ZoteroSourceLink(
            id=str(row["id"]),
            record_id=str(row["record_id"]),
            server_id=str(row["server_id"]),
            library_type=library_type,
            library_id=str(row["library_id"]),
            item_key=str(row["item_key"]),
            item_version=int(row["item_version"]),
            item_type=str(row["item_type"]),
            title=str(row["title"]),
            creators=tuple(raw_creators),
            publication_title=_optional_text(row["publication_title"]),
            published_date=_optional_text(row["published_date"]),
            doi=_optional_text(row["doi"]),
            url=_optional_text(row["url"]),
            attachment_key=_optional_text(row["attachment_key"]),
            attachment_version=(
                None
                if row["attachment_version"] is None
                else int(row["attachment_version"])
            ),
            attachment_filename=_optional_text(
                row["attachment_filename"]
            ),
            linked_at=_from_text(row["linked_at"]),
            observed_at=_from_text(row["observed_at"]),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LibraryDatabaseError(
            "The stored Zotero source link is invalid."
        ) from exc


def _to_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Library timestamps must include a timezone.")
    return value.isoformat()


def _from_text(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _from_text(value)


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)
