"""Verified, non-overwriting backups of ResearchMind Markdown notes."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from researchmind import __version__
from researchmind.integration.obsidian.errors import VaultBackupError
from researchmind.integration.obsidian.vault import validate_vault_destination
from researchmind.models import MarkdownBackupResult, MarkdownRestoreResult


BACKUP_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
NOTES_PREFIX = "notes"
MAX_BACKUP_FILES = 10_000
MAX_BACKUP_TOTAL_BYTES = 500 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024


def create_markdown_backup(
    *,
    vault_path: Path,
    subdirectory: str,
    archive_path: Path,
) -> MarkdownBackupResult:
    """Create one new ZIP containing only Markdown and a checksum manifest."""

    source_directory = validate_vault_destination(vault_path, subdirectory)
    if not source_directory.exists():
        raise VaultBackupError(
            "Configured ResearchMind Vault subdirectory does not exist."
        )
    destination = _validated_new_archive_path(archive_path)
    notes = _read_markdown_notes(source_directory)
    manifest_files = [
        {
            "path": relative_path,
            "size_bytes": len(content),
            "sha256": sha256(content).hexdigest(),
        }
        for relative_path, content in notes
    ]
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "researchmind_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "source_subdirectory": Path(subdirectory).as_posix(),
        "note_count": len(notes),
        "total_bytes": sum(len(content) for _, content in notes),
        "files": manifest_files,
    }
    created_archive = False
    try:
        with ZipFile(
            destination,
            mode="x",
            compression=ZIP_DEFLATED,
        ) as bundle:
            created_archive = True
            bundle.writestr(
                MANIFEST_NAME,
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ).encode("utf-8"),
            )
            for relative_path, content in notes:
                bundle.writestr(
                    f"{NOTES_PREFIX}/{relative_path}",
                    content,
                )
    except FileExistsError:
        raise VaultBackupError("Backup archive already exists.") from None
    except OSError:
        if created_archive:
            destination.unlink(missing_ok=True)
        raise VaultBackupError("Could not create the Markdown backup archive.") from None

    return MarkdownBackupResult(
        archive_path=destination,
        note_count=len(notes),
        total_bytes=manifest["total_bytes"],
    )


def restore_markdown_backup(
    *,
    archive_path: Path,
    vault_path: Path,
    subdirectory: str,
) -> MarkdownRestoreResult:
    """Verify a backup fully, then restore it into one absent Vault subdirectory."""

    destination = validate_vault_destination(vault_path, subdirectory)
    if destination.exists():
        raise VaultBackupError(
            "Restore destination must not already exist; choose a new subdirectory."
        )
    if not destination.parent.exists() or not destination.parent.is_dir():
        raise VaultBackupError(
            "Restore destination parent must already exist inside the Vault."
        )
    notes = _read_verified_archive(archive_path)
    staging_directory: Path | None = None
    try:
        staging_directory = Path(
            tempfile.mkdtemp(
                prefix=".researchmind-restore-",
                dir=destination.parent,
            )
        )
        for relative_path, content in notes:
            candidate = staging_directory.joinpath(
                *PurePosixPath(relative_path).parts
            )
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with candidate.open("xb") as stream:
                stream.write(content)
        staging_directory.replace(destination)
        staging_directory = None
    except OSError:
        raise VaultBackupError(
            "Could not restore the verified Markdown backup."
        ) from None
    finally:
        if staging_directory is not None and staging_directory.exists():
            shutil.rmtree(staging_directory)

    return MarkdownRestoreResult(
        output_directory=destination,
        note_count=len(notes),
        total_bytes=sum(len(content) for _, content in notes),
    )


def _validated_new_archive_path(archive_path: Path) -> Path:
    destination = Path(archive_path).expanduser()
    if destination.suffix.casefold() != ".zip":
        raise VaultBackupError("Backup archive must use the .zip extension.")
    if destination.exists():
        raise VaultBackupError("Backup archive already exists.")
    try:
        parent = destination.parent.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise VaultBackupError(
            "Backup archive parent directory does not exist."
        ) from None
    if not parent.is_dir():
        raise VaultBackupError(
            "Backup archive parent path is not a directory."
        )
    return parent / destination.name


def _read_markdown_notes(
    source_directory: Path,
) -> tuple[tuple[str, bytes], ...]:
    notes: list[tuple[str, bytes]] = []
    total_bytes = 0
    try:
        candidates = sorted(
            source_directory.rglob("*"),
            key=lambda path: path.as_posix().casefold(),
        )
        for candidate in candidates:
            if candidate.is_symlink():
                raise VaultBackupError(
                    "ResearchMind backup does not follow symbolic links."
                )
            if not candidate.is_file() or candidate.suffix.casefold() != ".md":
                continue
            relative_path = candidate.relative_to(source_directory).as_posix()
            content = candidate.read_bytes()
            total_bytes += len(content)
            if len(notes) + 1 > MAX_BACKUP_FILES:
                raise VaultBackupError("Backup contains too many Markdown files.")
            if total_bytes > MAX_BACKUP_TOTAL_BYTES:
                raise VaultBackupError("Backup Markdown size exceeds the safety limit.")
            notes.append((relative_path, content))
    except VaultBackupError:
        raise
    except OSError:
        raise VaultBackupError(
            "Could not read ResearchMind Markdown for backup."
        ) from None
    return tuple(notes)


def _read_verified_archive(
    archive_path: Path,
) -> tuple[tuple[str, bytes], ...]:
    try:
        resolved_archive = Path(archive_path).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise VaultBackupError(
            "Backup archive does not exist or is inaccessible."
        ) from None
    if not resolved_archive.is_file():
        raise VaultBackupError("Backup archive path is not a file.")

    try:
        with ZipFile(resolved_archive) as bundle:
            infos = bundle.infolist()
            _validate_archive_members(infos)
            manifest_info = bundle.getinfo(MANIFEST_NAME)
            if manifest_info.file_size > MAX_MANIFEST_BYTES:
                raise VaultBackupError("Backup manifest exceeds the safety limit.")
            manifest = _parse_manifest(bundle.read(manifest_info))
            note_infos = {
                info.filename.removeprefix(f"{NOTES_PREFIX}/"): info
                for info in infos
                if not info.is_dir()
                and info.filename.startswith(f"{NOTES_PREFIX}/")
            }
            expected = _manifest_entries(manifest)
            if set(note_infos) != set(expected):
                raise VaultBackupError(
                    "Backup manifest does not match the archived Markdown files."
                )
            notes: list[tuple[str, bytes]] = []
            total_bytes = 0
            for relative_path in sorted(
                expected,
                key=str.casefold,
            ):
                info = note_infos[relative_path]
                content = bundle.read(info)
                expected_size, expected_hash = expected[relative_path]
                if len(content) != expected_size:
                    raise VaultBackupError(
                        "Backup Markdown size does not match its manifest."
                    )
                if sha256(content).hexdigest() != expected_hash:
                    raise VaultBackupError(
                        "Backup Markdown checksum does not match its manifest."
                    )
                total_bytes += len(content)
                if total_bytes > MAX_BACKUP_TOTAL_BYTES:
                    raise VaultBackupError(
                        "Backup Markdown size exceeds the safety limit."
                    )
                notes.append((relative_path, content))
    except VaultBackupError:
        raise
    except (BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise VaultBackupError(
            "Backup archive or manifest is invalid."
        ) from None
    except OSError:
        raise VaultBackupError(
            "Could not read the backup archive."
        ) from None
    return tuple(notes)


def _validate_archive_members(infos: list[ZipInfo]) -> None:
    seen: set[str] = set()
    note_count = 0
    total_size = 0
    for info in infos:
        name = info.filename
        if name in seen:
            raise VaultBackupError("Backup archive contains duplicate entries.")
        seen.add(name)
        if info.flag_bits & 0x1:
            raise VaultBackupError("Encrypted backup entries are not supported.")
        file_mode = (info.external_attr >> 16) & 0o170000
        if file_mode == stat.S_IFLNK:
            raise VaultBackupError("Backup archive cannot contain symbolic links.")
        if info.is_dir():
            continue
        if not _is_safe_archive_name(name):
            raise VaultBackupError("Backup archive contains an unsafe path.")
        if name == MANIFEST_NAME:
            continue
        if not name.startswith(f"{NOTES_PREFIX}/") or not name.casefold().endswith(
            ".md"
        ):
            raise VaultBackupError(
                "Backup archive contains an unsupported file."
            )
        note_count += 1
        total_size += info.file_size
        if note_count > MAX_BACKUP_FILES:
            raise VaultBackupError("Backup contains too many Markdown files.")
        if total_size > MAX_BACKUP_TOTAL_BYTES:
            raise VaultBackupError("Backup Markdown size exceeds the safety limit.")
    if MANIFEST_NAME not in seen:
        raise VaultBackupError("Backup archive has no manifest.")


def _is_safe_archive_name(name: str) -> bool:
    if not name or "\\" in name:
        return False
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _parse_manifest(raw_manifest: bytes) -> dict[str, object]:
    parsed = json.loads(raw_manifest.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise VaultBackupError("Backup manifest must be a JSON object.")
    if parsed.get("format_version") != BACKUP_FORMAT_VERSION:
        raise VaultBackupError("Backup format version is not supported.")
    return parsed


def _manifest_entries(
    manifest: dict[str, object],
) -> dict[str, tuple[int, str]]:
    raw_files = manifest.get("files")
    note_count = manifest.get("note_count")
    if not isinstance(raw_files, list) or note_count != len(raw_files):
        raise VaultBackupError("Backup manifest note count is invalid.")
    entries: dict[str, tuple[int, str]] = {}
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            raise VaultBackupError("Backup manifest file entry is invalid.")
        path = raw_entry.get("path")
        size_bytes = raw_entry.get("size_bytes")
        checksum = raw_entry.get("sha256")
        if (
            not isinstance(path, str)
            or not _is_safe_archive_name(path)
            or not path.casefold().endswith(".md")
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
            or not isinstance(checksum, str)
            or len(checksum) != 64
        ):
            raise VaultBackupError("Backup manifest file entry is invalid.")
        if path in entries:
            raise VaultBackupError("Backup manifest contains duplicate files.")
        entries[path] = (size_bytes, checksum)
    return entries
