"""Filesystem safety tests for the T5-B1 single-file writer."""

from datetime import UTC, datetime
import os
from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    create_code_line_selection,
    open_code_project,
)
from researchmind.code import (
    CodeChangeConflictError,
    CodeChangePathError,
    CodeChangeWriteError,
    apply_code_change,
    read_code_snapshot,
    rollback_code_change,
)
from researchmind.core.code_changes import build_code_change_proposal
import researchmind.code.change_writer as change_writer


NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def _proposal(root: Path, replacement: str = "value = 2") -> tuple[object, object]:
    project = open_code_project(root)
    selection = create_code_line_selection(
        project,
        "model.py",
        start_line=1,
        end_line=1,
    )
    snapshot = read_code_snapshot(project, "model.py")
    proposal = build_code_change_proposal(
        project,
        selection,
        snapshot,
        replacement_text=replacement,
    )
    return project, proposal


def test_apply_creates_non_overwriting_recovery_and_rollback_restores(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "model.py"
    source.write_text("value = 1\n", encoding="utf-8")
    project, proposal = _proposal(root)

    receipt = apply_code_change(project, proposal, now=NOW)

    assert source.read_text(encoding="utf-8") == "value = 2\n"
    recovery = root / Path(receipt.recovery_relative_path)
    assert recovery.read_text(encoding="utf-8") == "value = 1\n"
    assert receipt.original_sha256 != receipt.applied_sha256

    rollback = rollback_code_change(project, receipt, now=NOW)

    assert source.read_text(encoding="utf-8") == "value = 1\n"
    assert rollback.restored_sha256 == receipt.original_sha256
    assert recovery.exists()


def test_apply_and_rollback_reject_external_edits(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "model.py"
    source.write_text("value = 1\n", encoding="utf-8")
    project, proposal = _proposal(root)
    source.write_text("value = 9\n", encoding="utf-8")

    with pytest.raises(CodeChangeConflictError, match="changed on disk"):
        apply_code_change(project, proposal, now=NOW)
    assert not (root / ".researchmind-recovery").exists()

    source.write_text("value = 1\n", encoding="utf-8")
    project, proposal = _proposal(root)
    receipt = apply_code_change(project, proposal, now=NOW)
    source.write_text("value = 7\n", encoding="utf-8")

    with pytest.raises(CodeChangeConflictError, match="after it was applied"):
        rollback_code_change(project, receipt, now=NOW)
    assert source.read_text(encoding="utf-8") == "value = 7\n"


def test_write_failure_leaves_source_unchanged_and_recovery_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source = root / "model.py"
    source.write_text("value = 1\n", encoding="utf-8")
    project, proposal = _proposal(root)

    def fail_replace(source_path: object, target_path: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(change_writer.os, "replace", fail_replace)

    with pytest.raises(CodeChangeWriteError, match="atomically apply"):
        apply_code_change(project, proposal, now=NOW)

    assert source.read_text(encoding="utf-8") == "value = 1\n"
    recoveries = list((root / ".researchmind-recovery").rglob("model.py"))
    assert len(recoveries) == 1
    assert recoveries[0].read_text(encoding="utf-8") == "value = 1\n"


def test_writer_rejects_symlink_target_when_platform_allows_it(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = root / "model.py"
    target.write_text("value = 1\n", encoding="utf-8")
    project, proposal = _proposal(root)
    outside = tmp_path / "outside.py"
    outside.write_text("outside = 1\n", encoding="utf-8")
    target.unlink()
    try:
        os.symlink(outside, target)
    except OSError:
        pytest.skip("Creating symlinks is unavailable on this Windows host.")

    with pytest.raises(CodeChangePathError, match="symbolic link"):
        apply_code_change(project, proposal, now=NOW)
    assert outside.read_text(encoding="utf-8") == "outside = 1\n"
