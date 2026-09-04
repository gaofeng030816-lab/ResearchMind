"""Durable, framework-independent models for the V3 local library."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


LibraryItemKind = Literal["paper", "code"]
AssetKind = Literal["pdf", "code_directory"]


@dataclass(frozen=True)
class LibraryRecord:
    """Stable ResearchMind identity for one paper or code workspace."""

    id: str
    kind: LibraryItemKind
    title: str
    created_at: datetime
    updated_at: datetime
    removed_at: datetime | None = None


@dataclass(frozen=True)
class AssetReference:
    """One immutable managed-file revision owned by a library record."""

    id: str
    record_id: str
    kind: AssetKind
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str
    revision: int
    managed: bool
    created_at: datetime
    deleted_at: datetime | None = None


@dataclass(frozen=True)
class LibraryEntry:
    """A record paired with its latest available asset revision."""

    record: LibraryRecord
    asset: AssetReference


@dataclass(frozen=True)
class UploadedFileData:
    """Browser-uploaded name and bytes after leaving the Streamlit boundary."""

    name: str
    content: bytes = field(repr=False)


@dataclass(frozen=True)
class LibraryImportResult:
    """Result of an idempotent managed-file import."""

    entry: LibraryEntry
    duplicate: bool = False


@dataclass(frozen=True)
class LibraryBackupResult:
    """Verified backup metadata for one local-library archive."""

    archive_path: Path
    entry_count: int
    total_bytes: int


@dataclass(frozen=True)
class LibraryRestoreResult:
    """Verified restore metadata for one newly created data directory."""

    data_dir: Path
    entry_count: int
    total_bytes: int
