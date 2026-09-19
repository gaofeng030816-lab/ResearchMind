"""Read one explicitly selected local code folder within fixed safety limits."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import os
from pathlib import Path

from researchmind.code.errors import (
    CodeProjectLimitError,
    CodeProjectPathError,
    CodeProjectReadError,
)
from researchmind.code.languages import language_for_relative_path
from researchmind.code.parsers import parse_code_symbols
from researchmind.models import CodeFile, CodeProject


DEFAULT_MAX_FILES = 2_000
DEFAULT_MAX_TOTAL_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_FILE_BYTES = 1 * 1024 * 1024
_MAX_READ_WORKERS = 8

_EXCLUDED_DIRECTORIES = frozenset(
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
_SENSITIVE_FILENAMES = frozenset(
    {
        "secrets",
        "credentials",
        "local_settings",
    }
)
_SENSITIVE_SUFFIXES = (
    "_secrets",
    "_credentials",
    "_tokens",
    "_apikeys",
)


def open_code_project(
    path: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> CodeProject:
    """Index eligible source files without importing or executing any source."""

    _validate_limits(max_files, max_total_bytes, max_file_bytes)
    root = _validated_root(path)
    candidates = _candidate_code_files(root)
    if len(candidates) > max_files:
        raise CodeProjectLimitError(
            f"Code file limit exceeded: {len(candidates)} found, "
            f"maximum {max_files}. Choose a smaller folder."
        )

    file_sizes = _validated_file_sizes(
        candidates,
        root=root,
        max_total_bytes=max_total_bytes,
        max_file_bytes=max_file_bytes,
    )
    files = _read_code_files(
        candidates,
        root=root,
        file_sizes=file_sizes,
    )
    identity = sha256(str(root).casefold().encode("utf-8")).hexdigest()[:20]
    return CodeProject(
        id=identity,
        name=root.name or str(root),
        root_path=root,
        files=files,
        total_source_bytes=sum(file_sizes.values()),
    )


def _read_code_files(
    candidates: list[Path],
    *,
    root: Path,
    file_sizes: dict[Path, int],
) -> tuple[CodeFile, ...]:
    """Read independent files concurrently while preserving candidate order."""

    if not candidates:
        return ()

    worker_count = min(_MAX_READ_WORKERS, len(candidates))

    def read_candidate(candidate: Path) -> CodeFile:
        return _read_code_file(
            candidate,
            root=root,
            size_bytes=file_sizes[candidate],
        )

    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="researchmind-code-reader",
    ) as executor:
        return tuple(executor.map(read_candidate, candidates))


def _validated_root(path: Path) -> Path:
    path_text = str(path).strip()
    if not path_text:
        raise CodeProjectPathError("Choose a local code folder.")
    try:
        root = Path(path_text).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CodeProjectPathError(
            f"Code folder does not exist or cannot be resolved: {path_text}"
        ) from exc
    if not root.is_dir():
        raise CodeProjectPathError(f"Code project path is not a folder: {root}")
    return root


def _candidate_code_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    try:
        for current_root, directory_names, file_names in os.walk(
            root,
            topdown=True,
            onerror=_raise_walk_error,
            followlinks=False,
        ):
            directory_names[:] = sorted(
                name
                for name in directory_names
                if not _excluded_directory(name)
                and not (Path(current_root) / name).is_symlink()
            )
            for file_name in sorted(file_names):
                if _excluded_file(file_name):
                    continue
                candidate = Path(current_root) / file_name
                if candidate.is_symlink():
                    continue
                try:
                    resolved = candidate.resolve(strict=True)
                    resolved.relative_to(root)
                except (OSError, RuntimeError, ValueError):
                    continue
                candidates.append(resolved)
    except OSError as exc:
        raise CodeProjectReadError(
            f"Could not enumerate code folder: {root}"
        ) from exc
    return sorted(
        candidates,
        key=lambda item: item.relative_to(root).as_posix().casefold(),
    )


def _raise_walk_error(error: OSError) -> None:
    raise error


def _excluded_directory(name: str) -> bool:
    normalized = name.casefold()
    return normalized.startswith(".") or normalized in _EXCLUDED_DIRECTORIES


def _excluded_file(name: str) -> bool:
    normalized = name.casefold()
    if normalized.startswith(".") or language_for_relative_path(normalized) is None:
        return True
    stem = Path(normalized).stem
    return (
        stem in _SENSITIVE_FILENAMES
        or stem.endswith(_SENSITIVE_SUFFIXES)
    )


def _validated_file_sizes(
    candidates: list[Path],
    *,
    root: Path,
    max_total_bytes: int,
    max_file_bytes: int,
) -> dict[Path, int]:
    sizes: dict[Path, int] = {}
    total = 0
    for candidate in candidates:
        try:
            size = candidate.stat().st_size
        except OSError as exc:
            relative_path = candidate.relative_to(root).as_posix()
            raise CodeProjectReadError(
                f"Could not inspect source file: {relative_path}"
            ) from exc
        if size > max_file_bytes:
            relative_path = candidate.relative_to(root).as_posix()
            raise CodeProjectLimitError(
                f"Code per-file size limit exceeded by {relative_path}: "
                f"{size} bytes, maximum {max_file_bytes}. "
                "Choose a smaller file or folder."
            )
        sizes[candidate] = size
        total += size
        if total > max_total_bytes:
            raise CodeProjectLimitError(
                f"Code total source-size limit exceeded: {total} bytes, "
                f"maximum {max_total_bytes}. Choose a smaller folder."
            )
    return sizes


def _read_code_file(
    path: Path,
    *,
    root: Path,
    size_bytes: int,
) -> CodeFile:
    relative_path = path.relative_to(root).as_posix()
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise CodeProjectReadError(
            f"Could not read source file: {relative_path}"
        ) from exc
    language = language_for_relative_path(relative_path)
    if language is None:
        raise CodeProjectReadError(f"Unsupported source file: {relative_path}")
    try:
        source = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return CodeFile(
            relative_path=relative_path,
            source="",
            size_bytes=size_bytes,
            line_count=0,
            status="unreadable",
            extraction_method="text",
            language=language,
            error="File is not valid UTF-8 and was not indexed.",
        )

    line_count = len(source.splitlines())
    try:
        symbols, extraction_method = parse_code_symbols(
            language, relative_path, source
        )
    except SyntaxError as exc:
        line_label = exc.lineno or "unknown"
        return CodeFile(
            relative_path=relative_path,
            source=source,
            size_bytes=size_bytes,
            line_count=line_count,
            status="syntax_error",
            extraction_method="text",
            language=language,
            error=(
                f"Source syntax error at line {line_label}; "
                "text selection remains available."
            ),
        )
    return CodeFile(
        relative_path=relative_path,
        source=source,
        size_bytes=size_bytes,
        line_count=line_count,
        status="parsed",
        extraction_method=extraction_method,
        language=language,
        symbols=symbols,
    )


def _validate_limits(
    max_files: int,
    max_total_bytes: int,
    max_file_bytes: int,
) -> None:
    if max_files <= 0 or max_total_bytes <= 0 or max_file_bytes <= 0:
        raise ValueError("Code project limits must be positive.")
