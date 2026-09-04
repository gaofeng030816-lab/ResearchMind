"""Tests for V3-G1 SQLite migrations and repository semantics."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from researchmind.database import (
    LATEST_SCHEMA_VERSION,
    LibraryConflictError,
    LibraryMigrationError,
    LibraryRepository,
    LibrarySchemaError,
    LibraryVersionError,
    initialize_database,
)
from researchmind.database import schema as library_schema
from researchmind.database.schema import connection_scope
from researchmind.models import (
    AssetReference,
    LibraryRecord,
    ZoteroSourceLink,
)


def test_new_database_is_migrated_and_validated(tmp_path: Path) -> None:
    database_path = initialize_database(
        tmp_path / "data" / "researchmind.sqlite3"
    )

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert version == LATEST_SCHEMA_VERSION
    assert {
        "library_records",
        "asset_references",
        "zotero_links",
    } <= tables


def test_schema_v1_migrates_to_v2_without_losing_library_records(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "v1.sqlite3"
    with sqlite3.connect(database_path) as connection:
        for statement in library_schema._MIGRATIONS[1]:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 1")
        connection.execute(
            """
            INSERT INTO library_records(
                id, kind, title, created_at, updated_at, removed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "paper-before-g2",
                "paper",
                "Existing paper",
                "2026-09-01T08:00:00+00:00",
                "2026-09-01T08:00:00+00:00",
                None,
            ),
        )

    initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT title FROM library_records WHERE id = ?",
            ("paper-before-g2",),
        ).fetchone()[0] == "Existing paper"
        assert connection.execute(
            "SELECT COUNT(*) FROM zotero_links"
        ).fetchone()[0] == 0


def test_failed_migration_rolls_back_all_new_schema_objects(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "broken.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE library_records(id TEXT)")

    with pytest.raises(LibraryMigrationError, match="rolled back"):
        initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        assets_table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'asset_references'
            """
        ).fetchone()

    assert version == 0
    assert assets_table is None


def test_newer_database_version_is_rejected_without_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 99")

    with pytest.raises(LibraryVersionError, match="newer"):
        initialize_database(database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_declared_current_but_incomplete_schema_is_rejected(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "corrupt.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            f"PRAGMA user_version = {LATEST_SCHEMA_VERSION}"
        )

    with pytest.raises(
        LibrarySchemaError,
        match="missing or inconsistent",
    ):
        initialize_database(database_path)


def test_repository_preserves_revisions_and_soft_removal(
    tmp_path: Path,
) -> None:
    database_path = initialize_database(
        tmp_path / "researchmind.sqlite3"
    )
    repository = LibraryRepository(database_path)
    now = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    record = LibraryRecord(
        id="record-1",
        kind="paper",
        title="A paper",
        created_at=now,
        updated_at=now,
    )
    first = _asset("asset-1", record.id, 1, b"first", now)
    second = _asset(
        "asset-2",
        record.id,
        2,
        b"second",
        now + timedelta(minutes=1),
    )

    repository.create_entry(record, first)
    repository.add_revision(second)

    assert repository.get_entry(record.id).asset.id == second.id
    assert repository.next_revision(record.id) == 3
    assert repository.find_by_hash("pdf", first.sha256) is not None

    repository.remove_record(
        record.id,
        removed_at=now + timedelta(minutes=2),
    )

    assert repository.list_entries() == []
    removed = repository.get_entry(record.id, include_removed=True)
    assert removed.record.removed_at is not None
    assert len(repository.assets_for_record(record.id)) == 2

    repository.restore_record(
        record.id,
        updated_at=now + timedelta(minutes=3),
    )

    assert repository.get_entry(record.id).record.removed_at is None


def test_concurrent_initialization_serializes_schema_migration(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "concurrent.sqlite3"

    with ThreadPoolExecutor(max_workers=4) as executor:
        resolved_paths = list(
            executor.map(
                initialize_database,
                [database_path] * 4,
            )
        )

    assert resolved_paths == [database_path.resolve()] * 4
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            LATEST_SCHEMA_VERSION
        )


def test_repository_connections_enforce_foreign_keys(
    tmp_path: Path,
) -> None:
    database_path = initialize_database(
        tmp_path / "foreign-keys.sqlite3"
    )

    with pytest.raises(sqlite3.IntegrityError):
        with connection_scope(database_path) as connection:
            assert connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0] == 1
            connection.execute(
                """
                INSERT INTO asset_references(
                    id, record_id, kind, relative_path, sha256,
                    size_bytes, media_type, revision, managed,
                    created_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "orphan-asset",
                    "missing-record",
                    "pdf",
                    "papers/orphan.pdf",
                    sha256(b"orphan").hexdigest(),
                    6,
                    "application/pdf",
                    1,
                    1,
                    "2026-09-01T08:00:00+00:00",
                    None,
                ),
            )

    with connection_scope(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM asset_references"
        ).fetchone()[0]
    assert count == 0


def test_repository_partitions_refreshes_and_unlinks_zotero_sources(
    tmp_path: Path,
) -> None:
    database_path = initialize_database(tmp_path / "zotero.sqlite3")
    repository = LibraryRepository(database_path)
    now = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
    first_record = _record("paper-1", now)
    second_record = _record("paper-2", now)
    repository.create_entry(
        first_record,
        _asset("asset-z1", first_record.id, 1, b"first", now),
    )
    repository.create_entry(
        second_record,
        _asset("asset-z2", second_record.id, 1, b"second", now),
    )
    initial = _zotero_link(first_record.id, now)

    stored = repository.upsert_zotero_link(initial)
    refreshed = repository.upsert_zotero_link(
        ZoteroSourceLink(
            **{
                **initial.__dict__,
                "item_version": 12,
                "title": "Updated title",
                "observed_at": now + timedelta(minutes=1),
            }
        )
    )

    assert stored.server_id == "server-A"
    assert refreshed.item_version == 12
    assert refreshed.title == "Updated title"
    assert refreshed.linked_at == initial.linked_at
    assert repository.find_zotero_link(
        server_id="server-A",
        library_type="user",
        library_id="42",
        item_key="ITEM0001",
    ) == refreshed
    assert repository.find_zotero_link(
        server_id="server-B",
        library_type="user",
        library_id="42",
        item_key="ITEM0001",
    ) is None

    with pytest.raises(LibraryConflictError, match="another paper"):
        repository.upsert_zotero_link(
            _zotero_link(second_record.id, now)
        )

    assert repository.unlink_zotero_item(first_record.id) is True
    assert repository.unlink_zotero_item(first_record.id) is False


def _record(record_id: str, created_at: datetime) -> LibraryRecord:
    return LibraryRecord(
        id=record_id,
        kind="paper",
        title=f"Paper {record_id}",
        created_at=created_at,
        updated_at=created_at,
    )


def _zotero_link(
    record_id: str,
    observed_at: datetime,
) -> ZoteroSourceLink:
    return ZoteroSourceLink(
        id=f"zotero-{record_id}",
        record_id=record_id,
        server_id="server-A",
        library_type="user",
        library_id="42",
        item_key="ITEM0001",
        item_version=11,
        item_type="journalArticle",
        title="A linked paper",
        creators=("Ada Lovelace",),
        publication_title="Journal of Tests",
        published_date="2026",
        doi="10.0000/example",
        url="https://example.test/paper",
        attachment_key="PDF00001",
        attachment_version=4,
        attachment_filename="paper.pdf",
        linked_at=observed_at,
        observed_at=observed_at,
    )


def _asset(
    asset_id: str,
    record_id: str,
    revision: int,
    content: bytes,
    created_at: datetime,
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
        created_at=created_at,
    )
