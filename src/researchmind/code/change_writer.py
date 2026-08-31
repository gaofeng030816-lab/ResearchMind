"""Narrow filesystem boundary for confirmed T5-B1 apply and rollback actions."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import os
from pathlib import Path, PurePosixPath
import stat
from uuid import uuid4

from researchmind.code.errors import (
    CodeChangeConflictError,
    CodeChangePathError,
    CodeChangeWriteError,
)
from researchmind.code.python_parser import parse_python_symbols
from researchmind.code.reader import DEFAULT_MAX_FILE_BYTES
from researchmind.models import (
    CodeChangeProposal,
    CodeChangeReceipt,
    CodeChangeRollbackReceipt,
    CodeFile,
    CodeFileSnapshot,
    CodeProject,
)


_UTF8_BOM = b"\xef\xbb\xbf"
_RECOVERY_DIRECTORY = ".researchmind-recovery"


def read_code_snapshot(
    project: CodeProject,
    relative_path: str,
) -> CodeFileSnapshot:
    """Read one indexed file and retain its exact raw hash and BOM state."""

    target = _validated_project_target(project, relative_path)
    raw = _read_bounded_bytes(target, relative_path=relative_path)
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CodeChangePathError(
            "Selected Python file is no longer valid UTF-8."
        ) from exc
    return CodeFileSnapshot(
        project_id=project.id,
        relative_path=relative_path,
        source=source,
        raw_sha256=sha256(raw).hexdigest(),
        size_bytes=len(raw),
        has_utf8_bom=raw.startswith(_UTF8_BOM),
    )


def code_file_from_proposal(proposal: CodeChangeProposal) -> CodeFile:
    """Build the post-apply index model before any disk mutation occurs."""

    raw = proposal.candidate_source.encode("utf-8")
    if proposal.has_utf8_bom:
        raw = _UTF8_BOM + raw
    if sha256(raw).hexdigest() != proposal.candidate_sha256:
        raise CodeChangeWriteError(
            "Code-change proposal failed its internal integrity check."
        )
    return _code_file_from_raw(proposal.relative_path, raw)


def code_file_from_recovery(
    project: CodeProject,
    receipt: CodeChangeReceipt,
) -> CodeFile:
    """Build the post-rollback index model before restoring the recovery copy."""

    recovery = _validated_recovery_file(
        project,
        receipt.recovery_relative_path,
    )
    try:
        raw = recovery.read_bytes()
    except OSError as exc:
        raise CodeChangeWriteError("Could not read the recovery copy.") from exc
    if sha256(raw).hexdigest() != receipt.original_sha256:
        raise CodeChangeConflictError(
            "Recovery copy checksum does not match the original source."
        )
    return _code_file_from_raw(receipt.relative_path, raw)


def apply_code_change(
    project: CodeProject,
    proposal: CodeChangeProposal,
    *,
    now: datetime | None = None,
) -> CodeChangeReceipt:
    """Apply one already validated proposal after an application-layer consent."""

    if proposal.project_id != project.id:
        raise CodeChangePathError(
            "Code-change proposal does not belong to the opened project."
        )
    target = _validated_project_target(project, proposal.relative_path)
    original = _read_bounded_bytes(
        target,
        relative_path=proposal.relative_path,
    )
    if sha256(original).hexdigest() != proposal.original_sha256:
        raise CodeChangeConflictError(
            "Selected Python file changed on disk; reopen it before proposing again."
        )
    candidate = proposal.candidate_source.encode("utf-8")
    if proposal.has_utf8_bom:
        candidate = _UTF8_BOM + candidate
    candidate_hash = sha256(candidate).hexdigest()
    if candidate_hash != proposal.candidate_sha256:
        raise CodeChangeWriteError(
            "Code-change proposal failed its internal integrity check."
        )

    timestamp = _utc_timestamp(now)
    recovery_path = _write_recovery_copy(
        project,
        proposal,
        original,
        timestamp=timestamp,
    )
    try:
        _atomic_replace(target, candidate)
    except OSError as exc:
        raise CodeChangeWriteError(
            "Could not atomically apply the code change; source stayed unchanged "
            "and the recovery copy was kept."
        ) from exc
    return CodeChangeReceipt(
        project_id=project.id,
        proposal_id=proposal.id,
        relative_path=proposal.relative_path,
        start_line=proposal.start_line,
        end_line=proposal.end_line,
        original_sha256=proposal.original_sha256,
        applied_sha256=candidate_hash,
        recovery_relative_path=recovery_path.relative_to(
            project.root_path
        ).as_posix(),
        applied_at=timestamp,
    )


def rollback_code_change(
    project: CodeProject,
    receipt: CodeChangeReceipt,
    *,
    now: datetime | None = None,
) -> CodeChangeRollbackReceipt:
    """Restore one recovery copy only when the applied file is still unchanged."""

    if receipt.project_id != project.id:
        raise CodeChangePathError(
            "Code-change receipt does not belong to the opened project."
        )
    target = _validated_project_target(project, receipt.relative_path)
    current = _read_bounded_bytes(
        target,
        relative_path=receipt.relative_path,
    )
    if sha256(current).hexdigest() != receipt.applied_sha256:
        raise CodeChangeConflictError(
            "Selected Python file changed after it was applied; rollback refused "
            "to protect the external edit."
        )
    recovery = _validated_recovery_file(
        project,
        receipt.recovery_relative_path,
    )
    try:
        original = recovery.read_bytes()
    except OSError as exc:
        raise CodeChangeWriteError("Could not read the recovery copy.") from exc
    if sha256(original).hexdigest() != receipt.original_sha256:
        raise CodeChangeConflictError(
            "Recovery copy checksum does not match the original source."
        )
    try:
        _atomic_replace(target, original)
    except OSError as exc:
        raise CodeChangeWriteError(
            "Could not atomically roll back the code change."
        ) from exc
    return CodeChangeRollbackReceipt(
        project_id=project.id,
        proposal_id=receipt.proposal_id,
        relative_path=receipt.relative_path,
        restored_sha256=receipt.original_sha256,
        recovery_relative_path=receipt.recovery_relative_path,
        rolled_back_at=_utc_timestamp(now),
    )


def _validated_project_target(
    project: CodeProject,
    relative_path: str,
) -> Path:
    indexed_paths = {item.relative_path for item in project.files}
    if relative_path not in indexed_paths or not relative_path.endswith(".py"):
        raise CodeChangePathError(
            "Code change target must be an existing indexed Python file."
        )
    relative = PurePosixPath(relative_path)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
    ):
        raise CodeChangePathError("Code change target path is unsafe.")
    try:
        root = project.root_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CodeChangePathError("Opened code project is no longer available.") from exc
    candidate = root.joinpath(*relative.parts)
    _reject_symlink_components(root, candidate)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CodeChangePathError(
            "Code change target is missing or outside the opened project."
        ) from exc
    if candidate.is_symlink():
        raise CodeChangePathError("Code change target must not be a symbolic link.")
    if not resolved.is_file():
        raise CodeChangePathError("Code change target is not an ordinary file.")
    return resolved


def _reject_symlink_components(root: Path, target: Path) -> None:
    current = root
    for part in target.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise CodeChangePathError(
                "Code change target must not pass through a symbolic link."
            )


def _read_bounded_bytes(path: Path, *, relative_path: str) -> bytes:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CodeChangePathError(
            f"Could not inspect selected Python file: {relative_path}"
        ) from exc
    if size > DEFAULT_MAX_FILE_BYTES:
        raise CodeChangePathError(
            "Selected Python file now exceeds the 1 MiB T5-B1 limit."
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CodeChangePathError(
            f"Could not read selected Python file: {relative_path}"
        ) from exc


def _code_file_from_raw(relative_path: str, raw: bytes) -> CodeFile:
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CodeChangeWriteError(
            "Code-change source is no longer valid UTF-8."
        ) from exc
    line_count = len(source.splitlines())
    try:
        symbols = parse_python_symbols(relative_path, source)
    except SyntaxError as exc:
        line_label = exc.lineno or "unknown"
        return CodeFile(
            relative_path=relative_path,
            source=source,
            size_bytes=len(raw),
            line_count=line_count,
            status="syntax_error",
            extraction_method="text",
            error=(
                "Python syntax error at line "
                f"{line_label}; text selection remains available."
            ),
        )
    return CodeFile(
        relative_path=relative_path,
        source=source,
        size_bytes=len(raw),
        line_count=line_count,
        status="parsed",
        extraction_method="ast",
        symbols=symbols,
    )


def _write_recovery_copy(
    project: CodeProject,
    proposal: CodeChangeProposal,
    original: bytes,
    *,
    timestamp: str,
) -> Path:
    root = project.root_path.resolve(strict=True)
    recovery_root = root / _RECOVERY_DIRECTORY
    try:
        if recovery_root.exists():
            if recovery_root.is_symlink() or not recovery_root.is_dir():
                raise CodeChangePathError(
                    "Recovery location is not a safe ordinary directory."
                )
        else:
            recovery_root.mkdir()
        run_directory = recovery_root / (
            f"{timestamp.replace(':', '').replace('+', '_')}-"
            f"{proposal.id[:12]}"
        )
        run_directory.mkdir()
        relative = PurePosixPath(proposal.relative_path)
        recovery_path = run_directory.joinpath(*relative.parts)
        recovery_path.parent.mkdir(parents=True, exist_ok=True)
        _write_new_file(recovery_path, original)
    except CodeChangePathError:
        raise
    except OSError as exc:
        raise CodeChangeWriteError(
            "Could not create the non-overwriting recovery copy."
        ) from exc
    return recovery_path


def _validated_recovery_file(
    project: CodeProject,
    relative_path: str,
) -> Path:
    relative = PurePosixPath(relative_path)
    if (
        not relative.parts
        or relative.parts[0] != _RECOVERY_DIRECTORY
        or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
    ):
        raise CodeChangePathError("Recovery path is unsafe.")
    root = project.root_path.resolve(strict=True)
    candidate = root.joinpath(*relative.parts)
    _reject_symlink_components(root, candidate)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root / _RECOVERY_DIRECTORY)
    except (OSError, RuntimeError, ValueError) as exc:
        raise CodeChangePathError("Recovery copy is missing or unsafe.") from exc
    if candidate.is_symlink() or not resolved.is_file():
        raise CodeChangePathError("Recovery copy must be an ordinary file.")
    return resolved


def _write_new_file(path: Path, content: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_replace(target: Path, content: bytes) -> None:
    temporary = target.with_name(
        f".{target.name}.researchmind-{uuid4().hex}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        permissions = stat.S_IMODE(target.stat().st_mode)
        os.chmod(temporary, permissions)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _utc_timestamp(now: datetime | None) -> str:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat(timespec="seconds")
