"""T6-B verified, non-overwriting backup and restore coverage."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from researchmind.integration.obsidian import (
    VaultBackupError,
    create_markdown_backup,
    restore_markdown_backup,
)


def test_backup_and_restore_markdown_with_manifest_and_no_secrets(
    temporary_vault: Path,
    tmp_path: Path,
) -> None:
    source = temporary_vault / "ResearchMind"
    nested = source / "Reading"
    nested.mkdir(parents=True)
    (source / "note.md").write_text("# Note\n", encoding="utf-8")
    (nested / "formula.md").write_text("$$x^2$$\n", encoding="utf-8")
    (source / ".env").write_text("LLM_API_KEY=secret\n", encoding="utf-8")
    (source / "figure.png").write_bytes(b"not-backed-up")
    archive = tmp_path / "researchmind-backup.zip"

    backup = create_markdown_backup(
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
        archive_path=archive,
    )

    assert backup.archive_path == archive
    assert backup.note_count == 2
    with ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
    assert names == {
        "manifest.json",
        "notes/note.md",
        "notes/Reading/formula.md",
    }
    assert manifest["format_version"] == 1
    assert manifest["note_count"] == 2
    assert "secret" not in archive.read_bytes().decode("latin-1")

    restored = restore_markdown_backup(
        archive_path=archive,
        vault_path=temporary_vault,
        subdirectory="ResearchMind-Recovered",
    )

    assert restored.note_count == 2
    assert restored.output_directory == temporary_vault / "ResearchMind-Recovered"
    assert (restored.output_directory / "note.md").read_text(
        encoding="utf-8"
    ) == "# Note\n"
    assert (restored.output_directory / "Reading" / "formula.md").read_text(
        encoding="utf-8"
    ) == "$$x^2$$\n"
    assert not (restored.output_directory / ".env").exists()


def test_backup_never_overwrites_existing_archive(
    temporary_vault: Path,
    tmp_path: Path,
) -> None:
    source = temporary_vault / "ResearchMind"
    source.mkdir()
    (source / "note.md").write_text("original", encoding="utf-8")
    archive = tmp_path / "existing.zip"
    archive.write_bytes(b"keep-me")

    with pytest.raises(VaultBackupError, match="already exists"):
        create_markdown_backup(
            vault_path=temporary_vault,
            subdirectory="ResearchMind",
            archive_path=archive,
        )

    assert archive.read_bytes() == b"keep-me"


def test_restore_requires_absent_destination_and_preserves_existing_notes(
    temporary_vault: Path,
    tmp_path: Path,
) -> None:
    source = temporary_vault / "ResearchMind"
    source.mkdir()
    (source / "note.md").write_text("source", encoding="utf-8")
    archive = tmp_path / "backup.zip"
    create_markdown_backup(
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
        archive_path=archive,
    )
    existing = temporary_vault / "Existing"
    existing.mkdir()
    existing_note = existing / "note.md"
    existing_note.write_text("do-not-overwrite", encoding="utf-8")

    with pytest.raises(VaultBackupError, match="must not already exist"):
        restore_markdown_backup(
            archive_path=archive,
            vault_path=temporary_vault,
            subdirectory="Existing",
        )

    assert existing_note.read_text(encoding="utf-8") == "do-not-overwrite"


def test_restore_rejects_tampered_note_before_writing(
    temporary_vault: Path,
    tmp_path: Path,
) -> None:
    source = temporary_vault / "ResearchMind"
    source.mkdir()
    (source / "note.md").write_text("trusted", encoding="utf-8")
    original = tmp_path / "original.zip"
    create_markdown_backup(
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
        archive_path=original,
    )
    tampered = tmp_path / "tampered.zip"
    with ZipFile(original) as source_bundle, ZipFile(
        tampered,
        mode="x",
        compression=ZIP_DEFLATED,
    ) as target_bundle:
        target_bundle.writestr(
            "manifest.json",
            source_bundle.read("manifest.json"),
        )
        target_bundle.writestr("notes/note.md", b"changed")

    with pytest.raises(VaultBackupError, match="checksum"):
        restore_markdown_backup(
            archive_path=tampered,
            vault_path=temporary_vault,
            subdirectory="Recovered",
        )

    assert not (temporary_vault / "Recovered").exists()


def test_restore_rejects_path_traversal_archive(
    temporary_vault: Path,
    tmp_path: Path,
) -> None:
    archive = tmp_path / "traversal.zip"
    with ZipFile(archive, mode="x", compression=ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", "{}")
        bundle.writestr("notes/../../outside.md", "unsafe")

    with pytest.raises(VaultBackupError, match="unsafe path"):
        restore_markdown_backup(
            archive_path=archive,
            vault_path=temporary_vault,
            subdirectory="Recovered",
        )

    assert not (tmp_path / "outside.md").exists()
    assert not (temporary_vault / "Recovered").exists()
