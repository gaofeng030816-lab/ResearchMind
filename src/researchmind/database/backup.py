"""Bounded, checksummed backup and new-directory restore for V3-G1."""

from __future__ import annotations

from hashlib import sha256
from contextlib import closing
import json
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
from uuid import uuid4
import zipfile

from researchmind.database.errors import LibraryBackupError
from researchmind.database.schema import (
    LATEST_SCHEMA_VERSION,
    initialize_database,
)
from researchmind.database.storage import (
    DATABASE_FILENAME,
    LibraryPaths,
)
from researchmind.models.library import (
    LibraryBackupResult,
    LibraryRestoreResult,
)


BACKUP_FORMAT = "researchmind-library-backup-v1"
MANIFEST_NAME = "manifest.json"
MAX_BACKUP_FILES = 10_000
MAX_BACKUP_BYTES = 2 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 1 * 1024 * 1024


def create_library_backup(
    paths: LibraryPaths,
    archive_path: Path,
) -> LibraryBackupResult:
    """Create and verify a non-overwriting SQLite plus assets archive."""

    initialize_database(paths.database_path)
    destination = _validated_archive_destination(
        archive_path,
        data_root=paths.data_root,
    )
    snapshot_path = (
        paths.staging_root / f"backup-{uuid4().hex}.sqlite3"
    )
    try:
        _snapshot_database(paths.database_path, snapshot_path)
        entries = [(DATABASE_FILENAME, snapshot_path)]
        entries.extend(_asset_files(paths))
        manifest = _build_manifest(entries)
        with zipfile.ZipFile(
            destination,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr(
                MANIFEST_NAME,
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
            for relative_path, source_path in entries:
                archive.write(source_path, arcname=relative_path)
        verified = _validated_archive(destination)
    except LibraryBackupError:
        if destination.exists():
            destination.unlink()
        raise
    except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        if destination.exists():
            destination.unlink()
        raise LibraryBackupError(
            "ResearchMind could not create the library backup."
        ) from exc
    finally:
        if snapshot_path.exists():
            snapshot_path.unlink()

    return LibraryBackupResult(
        archive_path=destination,
        entry_count=len(verified),
        total_bytes=sum(entry["size_bytes"] for entry in verified.values()),
    )


def restore_library_backup(
    archive_path: Path,
    target_data_dir: Path,
) -> LibraryRestoreResult:
    """Restore a verified archive into an absent data directory."""

    source = Path(archive_path).expanduser()
    try:
        source = source.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LibraryBackupError(
            "The library backup archive does not exist."
        ) from exc
    target = Path(target_data_dir).expanduser().resolve(strict=False)
    if target.exists():
        raise LibraryBackupError(
            "Library restore requires a data directory that does not exist."
        )
    if not target.parent.is_dir():
        raise LibraryBackupError(
            "Library restore requires an existing parent directory."
        )
    staging = target.parent / f".{target.name}-restore-{uuid4().hex}"
    entries = _validated_archive(source)

    try:
        staging.mkdir()
        with zipfile.ZipFile(source) as archive:
            for relative_path, expected in entries.items():
                destination = staging.joinpath(
                    *PurePosixPath(relative_path).parts
                )
                _require_within(destination, staging)
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = sha256()
                written = 0
                with archive.open(relative_path) as source_stream:
                    with destination.open("xb") as output_stream:
                        while chunk := source_stream.read(1024 * 1024):
                            output_stream.write(chunk)
                            digest.update(chunk)
                            written += len(chunk)
                if (
                    written != expected["size_bytes"]
                    or digest.hexdigest() != expected["sha256"]
                ):
                    raise LibraryBackupError(
                        "Library backup content failed checksum verification."
                    )
        initialize_database(staging / DATABASE_FILENAME)
        staging.replace(target)
    except LibraryBackupError:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        if staging.exists():
            shutil.rmtree(staging)
        raise LibraryBackupError(
            "ResearchMind could not restore the library backup."
        ) from exc

    return LibraryRestoreResult(
        data_dir=target,
        entry_count=len(entries),
        total_bytes=sum(entry["size_bytes"] for entry in entries.values()),
    )


def _snapshot_database(source_path: Path, snapshot_path: Path) -> None:
    with closing(sqlite3.connect(source_path)) as source:
        with closing(sqlite3.connect(snapshot_path)) as destination:
            source.backup(destination)


def _asset_files(paths: LibraryPaths) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    if not paths.assets_root.exists():
        return entries
    for source_path in sorted(paths.assets_root.rglob("*")):
        if source_path.is_symlink():
            raise LibraryBackupError(
                "Library backup refuses symbolic links in managed storage."
            )
        if not source_path.is_file():
            continue
        relative_path = source_path.relative_to(paths.data_root).as_posix()
        entries.append((relative_path, source_path))
    return entries


def _build_manifest(
    entries: list[tuple[str, Path]],
) -> dict[str, object]:
    if len(entries) > MAX_BACKUP_FILES:
        raise LibraryBackupError("Library backup exceeds the file-count limit.")
    rendered_entries = []
    total_bytes = 0
    for relative_path, source_path in entries:
        size_bytes = source_path.stat().st_size
        total_bytes += size_bytes
        if total_bytes > MAX_BACKUP_BYTES:
            raise LibraryBackupError("Library backup exceeds the size limit.")
        rendered_entries.append(
            {
                "path": relative_path,
                "size_bytes": size_bytes,
                "sha256": _file_sha256(source_path),
            }
        )
    return {
        "format": BACKUP_FORMAT,
        "schema_version": LATEST_SCHEMA_VERSION,
        "entries": rendered_entries,
    }


def _validated_archive(
    archive_path: Path,
) -> dict[str, dict[str, object]]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise LibraryBackupError(
                    "Library backup contains duplicate archive paths."
                )
            if MANIFEST_NAME not in names:
                raise LibraryBackupError(
                    "Library backup manifest is missing."
                )
            manifest_info = archive.getinfo(MANIFEST_NAME)
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise LibraryBackupError(
                    "Library backup manifest exceeds the size limit."
                )
            for info in infos:
                _validate_zip_info(info)
            manifest = json.loads(
                archive.read(MANIFEST_NAME).decode("utf-8")
            )
            expected = _validated_manifest(manifest)
            content_names = set(names) - {MANIFEST_NAME}
            if content_names != set(expected):
                raise LibraryBackupError(
                    "Library backup manifest does not match archive contents."
                )
            total_bytes = sum(
                archive.getinfo(name).file_size for name in content_names
            )
            if (
                len(content_names) > MAX_BACKUP_FILES
                or total_bytes > MAX_BACKUP_BYTES
            ):
                raise LibraryBackupError(
                    "Library backup exceeds restore resource limits."
                )
            for name, entry in expected.items():
                info = archive.getinfo(name)
                if info.file_size != entry["size_bytes"]:
                    raise LibraryBackupError(
                        "Library backup entry size does not match its manifest."
                    )
                if _zip_entry_sha256(archive, name) != entry["sha256"]:
                    raise LibraryBackupError(
                        "Library backup entry failed checksum verification."
                    )
            return expected
    except LibraryBackupError:
        raise
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
        zipfile.BadZipFile,
    ) as exc:
        raise LibraryBackupError(
            "Library backup is invalid or unreadable."
        ) from exc


def _validated_manifest(
    manifest: object,
) -> dict[str, dict[str, object]]:
    if not isinstance(manifest, dict):
        raise LibraryBackupError("Library backup manifest is invalid.")
    if manifest.get("format") != BACKUP_FORMAT:
        raise LibraryBackupError("Library backup format is unsupported.")
    schema_version = manifest.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
        or schema_version > LATEST_SCHEMA_VERSION
    ):
        raise LibraryBackupError(
            "Library backup schema version is unsupported."
        )
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise LibraryBackupError("Library backup entries are invalid.")
    expected: dict[str, dict[str, object]] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise LibraryBackupError("Library backup entry is invalid.")
        path = raw_entry.get("path")
        size_bytes = raw_entry.get("size_bytes")
        content_hash = raw_entry.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
            or not isinstance(content_hash, str)
            or len(content_hash) != 64
        ):
            raise LibraryBackupError(
                "Library backup entry metadata is invalid."
            )
        _validate_relative_archive_path(path)
        if path in expected or path == MANIFEST_NAME:
            raise LibraryBackupError(
                "Library backup contains duplicate manifest paths."
            )
        if path != DATABASE_FILENAME and not path.startswith("assets/"):
            raise LibraryBackupError(
                "Library backup contains an unsupported path."
            )
        expected[path] = {
            "size_bytes": size_bytes,
            "sha256": content_hash,
        }
    if DATABASE_FILENAME not in expected:
        raise LibraryBackupError(
            "Library backup does not contain its SQLite database."
        )
    return expected


def _validate_zip_info(info: zipfile.ZipInfo) -> None:
    _validate_relative_archive_path(info.filename)
    if info.flag_bits & 0x1:
        raise LibraryBackupError(
            "Encrypted library backup entries are not supported."
        )
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if unix_mode and stat.S_ISLNK(unix_mode):
        raise LibraryBackupError(
            "Symbolic links are not supported in library backups."
        )


def _validate_relative_archive_path(path_text: str) -> None:
    path = PurePosixPath(path_text)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or ":" in path.parts[0]
    ):
        raise LibraryBackupError(
            "Library backup contains an unsafe relative path."
        )


def _validated_archive_destination(
    archive_path: Path,
    *,
    data_root: Path,
) -> Path:
    candidate = Path(archive_path).expanduser().resolve(strict=False)
    if candidate.exists():
        raise LibraryBackupError(
            "Library backup will not overwrite an existing file."
        )
    if not candidate.parent.is_dir():
        raise LibraryBackupError(
            "Library backup requires an existing output directory."
        )
    if candidate.is_relative_to(data_root.resolve(strict=False)):
        raise LibraryBackupError(
            "Store the library backup outside RESEARCHMIND_DATA_DIR."
        )
    return candidate


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_entry_sha256(
    archive: zipfile.ZipFile,
    name: str,
) -> str:
    digest = sha256()
    with archive.open(name) as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_within(path: Path, root: Path) -> None:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    if resolved_path == resolved_root or not resolved_path.is_relative_to(
        resolved_root
    ):
        raise LibraryBackupError(
            "Library restore escaped its staging directory."
        )
