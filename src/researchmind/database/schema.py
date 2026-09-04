"""Versioned SQLite schema creation and validation for ResearchMind V3."""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import closing, contextmanager
from collections.abc import Iterator
from pathlib import Path
import sqlite3

from researchmind.database.errors import (
    LibraryDatabaseError,
    LibraryMigrationError,
    LibrarySchemaError,
    LibraryVersionError,
)


LATEST_SCHEMA_VERSION = 2

_MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        """
        CREATE TABLE library_records (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL CHECK (kind IN ('paper', 'code')),
            title TEXT NOT NULL CHECK (length(trim(title)) > 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            removed_at TEXT
        )
        """,
        """
        CREATE TABLE asset_references (
            id TEXT PRIMARY KEY,
            record_id TEXT NOT NULL REFERENCES library_records(id)
                ON DELETE RESTRICT,
            kind TEXT NOT NULL CHECK (kind IN ('pdf', 'code_directory')),
            relative_path TEXT NOT NULL UNIQUE,
            sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            media_type TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            managed INTEGER NOT NULL CHECK (managed IN (0, 1)),
            created_at TEXT NOT NULL,
            deleted_at TEXT,
            UNIQUE (record_id, revision)
        )
        """,
        """
        CREATE UNIQUE INDEX asset_references_live_hash
        ON asset_references(kind, sha256)
        WHERE deleted_at IS NULL
        """,
        """
        CREATE INDEX asset_references_record_revision
        ON asset_references(record_id, revision DESC)
        """,
    ),
    2: (
        """
        CREATE TABLE zotero_links (
            id TEXT PRIMARY KEY,
            record_id TEXT NOT NULL UNIQUE REFERENCES library_records(id)
                ON DELETE RESTRICT,
            server_id TEXT NOT NULL
                CHECK (length(trim(server_id)) BETWEEN 1 AND 128),
            library_type TEXT NOT NULL
                CHECK (library_type IN ('user', 'group')),
            library_id TEXT NOT NULL CHECK (length(trim(library_id)) > 0),
            item_key TEXT NOT NULL CHECK (length(item_key) = 8),
            item_version INTEGER NOT NULL CHECK (item_version >= 0),
            item_type TEXT NOT NULL CHECK (length(trim(item_type)) > 0),
            title TEXT NOT NULL,
            creators_json TEXT NOT NULL,
            publication_title TEXT,
            published_date TEXT,
            doi TEXT,
            url TEXT,
            attachment_key TEXT,
            attachment_version INTEGER,
            attachment_filename TEXT,
            linked_at TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            UNIQUE (
                server_id, library_type, library_id, item_key
            ),
            CHECK (
                attachment_version IS NULL
                OR attachment_version >= 0
            ),
            CHECK (
                (
                    attachment_key IS NULL
                    AND attachment_version IS NULL
                    AND attachment_filename IS NULL
                )
                OR
                (
                    length(attachment_key) = 8
                    AND attachment_version IS NOT NULL
                    AND length(trim(attachment_filename)) > 0
                )
            )
        )
        """,
        """
        CREATE INDEX zotero_links_source_identity
        ON zotero_links(server_id, library_type, library_id, item_key)
        """,
    ),
}

_EXPECTED_COLUMNS = {
    "library_records": {
        "id",
        "kind",
        "title",
        "created_at",
        "updated_at",
        "removed_at",
    },
    "asset_references": {
        "id",
        "record_id",
        "kind",
        "relative_path",
        "sha256",
        "size_bytes",
        "media_type",
        "revision",
        "managed",
        "created_at",
        "deleted_at",
    },
    "zotero_links": {
        "id",
        "record_id",
        "server_id",
        "library_type",
        "library_id",
        "item_key",
        "item_version",
        "item_type",
        "title",
        "creators_json",
        "publication_title",
        "published_date",
        "doi",
        "url",
        "attachment_key",
        "attachment_version",
        "attachment_filename",
        "linked_at",
        "observed_at",
    },
}


def initialize_database(database_path: Path) -> Path:
    """Create, migrate, and validate one local SQLite database."""

    candidate = Path(database_path).expanduser()
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(candidate)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            migrate_connection(connection)
    except (LibraryDatabaseError, OSError):
        raise
    except sqlite3.Error as exc:
        raise LibraryDatabaseError(
            "Could not initialize the ResearchMind database."
        ) from exc
    return candidate.resolve()


def migrate_connection(connection: sqlite3.Connection) -> None:
    """Apply pending migrations atomically and reject unknown schemas."""

    migration_started = False
    try:
        connection.execute("BEGIN IMMEDIATE")
        current_version = _schema_version(connection)
        if current_version > LATEST_SCHEMA_VERSION:
            raise LibraryVersionError(
                "The ResearchMind database was created by a newer "
                "application version."
            )

        for target_version in range(
            current_version + 1,
            LATEST_SCHEMA_VERSION + 1,
        ):
            migration_started = True
            _apply_migration(
                connection,
                target_version,
                _MIGRATIONS[target_version],
            )

        _validate_schema(connection)
        connection.commit()
    except LibraryVersionError:
        connection.rollback()
        raise
    except LibrarySchemaError as exc:
        connection.rollback()
        if migration_started:
            raise LibraryMigrationError(
                "ResearchMind database migration was rolled back."
            ) from exc
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise LibraryMigrationError(
            "ResearchMind database migration was rolled back."
        ) from exc


def open_connection(database_path: Path) -> sqlite3.Connection:
    """Open a model-row SQLite connection for repository operations."""

    try:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
    except sqlite3.Error as exc:
        raise LibraryDatabaseError(
            "Could not open the ResearchMind database."
        ) from exc


@contextmanager
def connection_scope(
    database_path: Path,
) -> Iterator[sqlite3.Connection]:
    """Commit or roll back one repository operation, then always close."""

    connection = open_connection(database_path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _apply_migration(
    connection: sqlite3.Connection,
    target_version: int,
    statements: Iterable[str],
) -> None:
    for statement in statements:
        connection.execute(statement)
    connection.execute(f"PRAGMA user_version = {target_version}")


def _schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _validate_schema(connection: sqlite3.Connection) -> None:
    for table_name, expected_columns in _EXPECTED_COLUMNS.items():
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        actual_columns = {str(row[1]) for row in rows}
        if actual_columns != expected_columns:
            raise LibrarySchemaError(
                "The ResearchMind database schema is missing or inconsistent."
            )
