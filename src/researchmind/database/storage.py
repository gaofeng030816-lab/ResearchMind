"""Managed file staging, resolution, and compensation for the local library."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import shutil

from researchmind.code.languages import language_for_relative_path
from researchmind.database.errors import (
    LibraryConfigurationError,
    LibraryImportError,
)
from researchmind.models.library import AssetReference, UploadedFileData


DATABASE_FILENAME = "researchmind.sqlite3"
PDF_MAGIC = b"%PDF-"
_MAX_CODE_UPLOAD_FILES = 2_000
_MAX_CODE_UPLOAD_TOTAL_BYTES = 20 * 1024 * 1024
_MAX_CODE_UPLOAD_FILE_BYTES = 1 * 1024 * 1024
_EXCLUDED_CODE_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "build",
        "dist",
        "site-packages",
        "node_modules",
        "vendor",
    }
)
_SENSITIVE_CODE_FILENAMES = frozenset(
    {
        "secrets",
        "credentials",
        "local_settings",
    }
)
_SENSITIVE_CODE_SUFFIXES = (
    "_secrets",
    "_credentials",
    "_tokens",
    "_apikeys",
)


@dataclass(frozen=True)
class LibraryPaths:
    """Resolved private paths below one explicitly configured data root."""

    data_root: Path
    database_path: Path
    assets_root: Path
    staging_root: Path


@dataclass(frozen=True)
class StagedAsset:
    """One validated upload awaiting an atomic move to managed storage."""

    staged_path: Path
    final_path: Path
    relative_path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class QuarantinedAsset:
    """One managed asset moved aside while database deletion is committed."""

    original_path: Path
    quarantine_path: Path


@dataclass(frozen=True)
class StagedCodeAsset:
    """A staged static-code directory plus its safe display metadata."""

    asset: StagedAsset
    project_name: str
    file_count: int


def prepare_library_paths(
    data_dir: Path,
    *,
    obsidian_vault_path: Path | None = None,
) -> LibraryPaths:
    """Validate and create the explicit data root and private children."""

    candidate = Path(data_dir).expanduser()
    try:
        data_root = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise LibraryConfigurationError(
            "RESEARCHMIND_DATA_DIR cannot be resolved."
        ) from exc

    if obsidian_vault_path is not None:
        try:
            vault_root = Path(obsidian_vault_path).expanduser().resolve(
                strict=False
            )
        except (OSError, RuntimeError) as exc:
            raise LibraryConfigurationError(
                "The configured Obsidian Vault path cannot be resolved."
            ) from exc
        if (
            data_root == vault_root
            or data_root.is_relative_to(vault_root)
            or vault_root.is_relative_to(data_root)
        ):
            raise LibraryConfigurationError(
                "RESEARCHMIND_DATA_DIR must be separate from the Obsidian Vault."
            )

    assets_root = data_root / "assets"
    staging_root = data_root / ".staging"
    try:
        data_root.mkdir(parents=True, exist_ok=True)
        if not data_root.is_dir():
            raise LibraryConfigurationError(
                "RESEARCHMIND_DATA_DIR must identify a directory."
            )
        assets_root.mkdir(exist_ok=True)
        staging_root.mkdir(exist_ok=True)
    except LibraryConfigurationError:
        raise
    except OSError as exc:
        raise LibraryConfigurationError(
            "ResearchMind could not create its configured data directory."
        ) from exc

    return LibraryPaths(
        data_root=data_root,
        database_path=data_root / DATABASE_FILENAME,
        assets_root=assets_root,
        staging_root=staging_root,
    )


class ManagedStorage:
    """Own atomic moves and safe compensation below the assets directory."""

    def __init__(self, paths: LibraryPaths) -> None:
        self.paths = paths

    def stage_pdf(
        self,
        upload: UploadedFileData,
        *,
        asset_id: str,
        max_size_bytes: int,
    ) -> StagedAsset:
        if not upload.name.strip().lower().endswith(".pdf"):
            raise LibraryImportError("Only .pdf files can be imported as papers.")
        if max_size_bytes <= 0 or len(upload.content) > max_size_bytes:
            raise LibraryImportError(
                "The uploaded PDF exceeds the configured size limit."
            )
        if not upload.content.startswith(PDF_MAGIC):
            raise LibraryImportError(
                "The uploaded file does not have a valid PDF signature."
            )

        content_hash = sha256(upload.content).hexdigest()
        relative_path = f"papers/{asset_id}.pdf"
        staged_path = self.paths.staging_root / f"{asset_id}.pdf"
        final_path = self.resolve_relative_path(relative_path)
        try:
            with staged_path.open("xb") as stream:
                stream.write(upload.content)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as exc:
            raise LibraryImportError(
                "A temporary import with this identity already exists."
            ) from exc
        except OSError as exc:
            raise LibraryImportError(
                "ResearchMind could not stage the uploaded PDF."
            ) from exc

        return StagedAsset(
            staged_path=staged_path,
            final_path=final_path,
            relative_path=relative_path,
            sha256=content_hash,
            size_bytes=len(upload.content),
        )

    def stage_code_directory(
        self,
        uploads: list[UploadedFileData],
        *,
        asset_id: str,
        requested_project_name: str | None = None,
        max_files: int = _MAX_CODE_UPLOAD_FILES,
        max_total_bytes: int = _MAX_CODE_UPLOAD_TOTAL_BYTES,
        max_file_bytes: int = _MAX_CODE_UPLOAD_FILE_BYTES,
    ) -> StagedCodeAsset:
        """Validate and stage one browser-selected static-code directory."""

        if not uploads:
            raise LibraryImportError(
                "Choose a code directory containing at least one supported file."
            )
        if len(uploads) > max_files:
            raise LibraryImportError(
                "The selected directory exceeds the code file limit."
            )
        if sum(len(upload.content) for upload in uploads) > max_total_bytes:
            raise LibraryImportError(
                "The selected directory exceeds the total code size limit."
            )

        normalized = [
            (_normalized_upload_path(upload.name), upload)
            for upload in uploads
        ]
        project_name, normalized = _strip_uploaded_root(
            normalized,
            requested_project_name=requested_project_name,
        )
        eligible: list[tuple[PurePosixPath, UploadedFileData]] = []
        identities: set[str] = set()
        for relative_path, upload in normalized:
            if _is_excluded_code_path(relative_path):
                continue
            if language_for_relative_path(relative_path.as_posix()) is None:
                raise LibraryImportError(
                    "Code-directory import accepts .py, .c, .h, .java, .jl, "
                    "and .r files only."
                )
            if len(upload.content) > max_file_bytes:
                raise LibraryImportError(
                    f"Uploaded code file exceeds the per-file limit: {relative_path.name}"
                )
            try:
                upload.content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise LibraryImportError(
                    f"Uploaded code file is not valid UTF-8: {relative_path.name}"
                ) from exc
            identity = relative_path.as_posix().casefold()
            if identity in identities:
                raise LibraryImportError(
                    "The uploaded directory contains duplicate relative paths."
                )
            identities.add(identity)
            eligible.append((relative_path, upload))

        if not eligible:
            raise LibraryImportError(
                "The selected directory has no eligible UTF-8 source files."
            )

        content_hash = _code_directory_hash(eligible)
        relative_root = f"code/{asset_id}"
        staged_root = self.paths.staging_root / asset_id
        final_root = self.resolve_relative_path(relative_root)
        try:
            staged_root.mkdir()
            for relative_path, upload in eligible:
                output_path = staged_root.joinpath(*relative_path.parts)
                self._require_within(output_path, staged_root)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with output_path.open("xb") as stream:
                    stream.write(upload.content)
                    stream.flush()
                    os.fsync(stream.fileno())
        except (FileExistsError, OSError) as exc:
            self._delete_path(
                staged_root,
                allowed_root=self.paths.staging_root,
            )
            raise LibraryImportError(
                "ResearchMind could not stage the uploaded code directory."
            ) from exc

        return StagedCodeAsset(
            asset=StagedAsset(
                staged_path=staged_root,
                final_path=final_root,
                relative_path=relative_root,
                sha256=content_hash,
                size_bytes=sum(
                    len(upload.content) for _path, upload in eligible
                ),
            ),
            project_name=project_name,
            file_count=len(eligible),
        )

    def finalize(self, staged: StagedAsset) -> Path:
        """Atomically move one staged asset into its unique final path."""

        self._require_within(staged.staged_path, self.paths.staging_root)
        self._require_within(staged.final_path, self.paths.assets_root)
        try:
            staged.final_path.parent.mkdir(parents=True, exist_ok=True)
            if staged.final_path.exists():
                raise LibraryImportError(
                    "A managed asset already exists at the generated path."
                )
            staged.staged_path.replace(staged.final_path)
        except LibraryImportError:
            raise
        except OSError as exc:
            raise LibraryImportError(
                "ResearchMind could not finalize the managed asset."
            ) from exc
        return staged.final_path

    def discard_staged(self, staged: StagedAsset) -> None:
        self._delete_path(
            staged.staged_path,
            allowed_root=self.paths.staging_root,
        )

    def discard_final(self, staged: StagedAsset) -> None:
        self._delete_path(
            staged.final_path,
            allowed_root=self.paths.assets_root,
        )

    def resolve_asset(self, asset: AssetReference) -> Path:
        if not asset.managed:
            raise LibraryImportError(
                "External assets are not owned by ResearchMind."
            )
        resolved = self.resolve_relative_path(asset.relative_path)
        if not resolved.exists():
            raise LibraryImportError(
                "The managed library asset is missing from local storage."
            )
        return resolved

    def resolve_relative_path(self, relative_path: str) -> Path:
        pure_path = PurePosixPath(relative_path)
        if (
            pure_path.is_absolute()
            or not pure_path.parts
            or any(part in {"", ".", ".."} for part in pure_path.parts)
        ):
            raise LibraryImportError(
                "Managed asset metadata contains an unsafe relative path."
            )
        resolved = self.paths.assets_root.joinpath(*pure_path.parts).resolve(
            strict=False
        )
        self._require_within(resolved, self.paths.assets_root)
        return resolved

    def quarantine(
        self,
        asset: AssetReference,
    ) -> QuarantinedAsset:
        original_path = self.resolve_asset(asset)
        quarantine_path = (
            self.paths.staging_root / f"delete-{asset.id}"
        ).resolve(strict=False)
        self._require_within(quarantine_path, self.paths.staging_root)
        try:
            if quarantine_path.exists():
                raise LibraryImportError(
                    "A deletion recovery path already exists."
                )
            original_path.replace(quarantine_path)
        except LibraryImportError:
            raise
        except OSError as exc:
            raise LibraryImportError(
                "ResearchMind could not stage the managed asset for deletion."
            ) from exc
        return QuarantinedAsset(
            original_path=original_path,
            quarantine_path=quarantine_path,
        )

    def restore_quarantine(self, quarantined: QuarantinedAsset) -> None:
        self._require_within(
            quarantined.quarantine_path,
            self.paths.staging_root,
        )
        self._require_within(
            quarantined.original_path,
            self.paths.assets_root,
        )
        try:
            quarantined.original_path.parent.mkdir(parents=True, exist_ok=True)
            quarantined.quarantine_path.replace(quarantined.original_path)
        except OSError as exc:
            raise LibraryImportError(
                "ResearchMind could not restore a quarantined managed asset."
            ) from exc

    def discard_quarantine(self, quarantined: QuarantinedAsset) -> None:
        self._delete_path(
            quarantined.quarantine_path,
            allowed_root=self.paths.staging_root,
        )

    @staticmethod
    def _require_within(path: Path, allowed_root: Path) -> None:
        candidate = path.resolve(strict=False)
        root = allowed_root.resolve(strict=False)
        if candidate == root or not candidate.is_relative_to(root):
            raise LibraryImportError(
                "Managed file operation escaped its private storage root."
            )

    def _delete_path(self, path: Path, *, allowed_root: Path) -> None:
        self._require_within(path, allowed_root)
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError as exc:
            raise LibraryImportError(
                "ResearchMind could not clean up a managed temporary asset."
            ) from exc


def _normalized_upload_path(name: str) -> PurePosixPath:
    normalized_name = name.strip().replace("\\", "/")
    path = PurePosixPath(normalized_name)
    if (
        not normalized_name
        or path.is_absolute()
        or not path.parts
        or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise LibraryImportError(
            "The uploaded directory contains an unsafe relative path."
        )
    return path


def _strip_uploaded_root(
    uploads: list[tuple[PurePosixPath, UploadedFileData]],
    *,
    requested_project_name: str | None,
) -> tuple[str, list[tuple[PurePosixPath, UploadedFileData]]]:
    first_parts = {path.parts[0] for path, _upload in uploads}
    has_shared_root = (
        len(first_parts) == 1
        and all(len(path.parts) > 1 for path, _upload in uploads)
    )
    inferred_name = next(iter(first_parts)) if has_shared_root else "Code project"
    safe_name = " ".join((requested_project_name or inferred_name).split())
    project_name = safe_name[:120] or "Code project"
    if not has_shared_root:
        return project_name, uploads
    return (
        project_name,
        [
            (PurePosixPath(*path.parts[1:]), upload)
            for path, upload in uploads
        ],
    )


def _is_excluded_code_path(path: PurePosixPath) -> bool:
    directory_parts = path.parts[:-1]
    if any(
        part.startswith(".")
        or part.casefold() in _EXCLUDED_CODE_DIRECTORIES
        for part in directory_parts
    ):
        return True
    filename = path.name.casefold()
    stem = path.stem.casefold()
    return (
        filename.startswith(".")
        or stem in _SENSITIVE_CODE_FILENAMES
        or stem.endswith(_SENSITIVE_CODE_SUFFIXES)
    )


def _code_directory_hash(
    uploads: list[tuple[PurePosixPath, UploadedFileData]],
) -> str:
    digest = sha256()
    for relative_path, upload in sorted(
        uploads,
        key=lambda item: item[0].as_posix().casefold(),
    ):
        digest.update(relative_path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(upload.content).digest())
        digest.update(b"\0")
    return digest.hexdigest()
