"""Recovery and tamper tests for V3-G1 local-library archives."""

from pathlib import Path
from hashlib import sha256
import json
import sqlite3
import zipfile

import pytest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.database import LibraryBackupError
from researchmind.database import LATEST_SCHEMA_VERSION
from researchmind.database import schema as library_schema
from researchmind.models import UploadedFileData


def test_library_backup_refuses_overwrite_and_restore_existing_target(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    use_cases.import_code_directory_to_library(
        [
            UploadedFileData(
                name="demo/main.py",
                content=b"value = 1\n",
            )
        ],
        settings=settings,
    )
    archive = tmp_path / "library.zip"
    use_cases.backup_local_library(archive, settings=settings)

    with pytest.raises(LibraryBackupError, match="overwrite"):
        use_cases.backup_local_library(archive, settings=settings)

    existing_target = tmp_path / "existing"
    existing_target.mkdir()
    with pytest.raises(LibraryBackupError, match="does not exist"):
        use_cases.restore_local_library_backup(
            archive,
            existing_target,
            settings=settings,
        )


def test_tampered_backup_is_rejected_before_restore_writes(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    use_cases.import_code_directory_to_library(
        [
            UploadedFileData(
                name="demo/main.py",
                content=b"value = 1\n",
            )
        ],
        settings=settings,
    )
    original = tmp_path / "original.zip"
    use_cases.backup_local_library(original, settings=settings)
    tampered = tmp_path / "tampered.zip"

    with zipfile.ZipFile(original) as source:
        with zipfile.ZipFile(tampered, "x") as destination:
            for info in source.infolist():
                content = source.read(info.filename)
                if info.filename.endswith("main.py"):
                    content = b"value = 999\n"
                destination.writestr(info, content)

    target = tmp_path / "restored"
    with pytest.raises(LibraryBackupError, match="size|checksum"):
        use_cases.restore_local_library_backup(
            tampered,
            target,
            settings=settings,
        )

    assert target.exists() is False
    assert not list(tmp_path.glob(".restored-restore-*"))


def test_traversal_backup_is_rejected_without_creating_target(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "traversal.zip"
    database_content = b"not needed because traversal fails first"
    manifest = {
        "format": "researchmind-library-backup-v1",
        "schema_version": 1,
        "entries": [
            {
                "path": "researchmind.sqlite3",
                "size_bytes": len(database_content),
                "sha256": "0" * 64,
            }
        ],
    }
    with zipfile.ZipFile(archive, "x") as destination:
        destination.writestr(
            "manifest.json",
            json.dumps(manifest).encode("utf-8"),
        )
        destination.writestr("researchmind.sqlite3", database_content)
        destination.writestr("../escape.py", b"escape")

    target = tmp_path / "restored"
    with pytest.raises(LibraryBackupError, match="unsafe relative path"):
        use_cases.restore_local_library_backup(
            archive,
            target,
            settings=Settings(),
        )

    assert target.exists() is False
    assert not (tmp_path.parent / "escape.py").exists()


def test_schema_v1_backup_restores_then_migrates_to_current_version(
    tmp_path: Path,
) -> None:
    v1_database = tmp_path / "v1.sqlite3"
    with sqlite3.connect(v1_database) as connection:
        for statement in library_schema._MIGRATIONS[1]:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 1")
    database_content = v1_database.read_bytes()
    archive = tmp_path / "v1-backup.zip"
    manifest = {
        "format": "researchmind-library-backup-v1",
        "schema_version": 1,
        "entries": [
            {
                "path": "researchmind.sqlite3",
                "size_bytes": len(database_content),
                "sha256": sha256(database_content).hexdigest(),
            }
        ],
    }
    with zipfile.ZipFile(archive, "x") as destination:
        destination.writestr(
            "manifest.json",
            json.dumps(manifest).encode("utf-8"),
        )
        destination.writestr("researchmind.sqlite3", database_content)

    target = tmp_path / "restored-v1"
    use_cases.restore_local_library_backup(
        archive,
        target,
        settings=Settings(),
    )

    with sqlite3.connect(target / "researchmind.sqlite3") as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == (
            LATEST_SCHEMA_VERSION
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM zotero_links"
        ).fetchone()[0] == 0


def test_backup_and_restore_preserve_explicit_note_draft(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    draft = use_cases.create_note_draft(
        "Durable draft",
        body_markdown="## Editable\n",
        settings=settings,
    )
    draft, evidence = use_cases.add_note_evidence(
        draft.id,
        kind="question",
        content="Why does this converge?",
        source_label="User question",
        origin="user_question",
        expected_draft_revision=1,
        settings=settings,
    )
    archive = tmp_path / "draft-library.zip"
    use_cases.backup_local_library(archive, settings=settings)
    restored_root = tmp_path / "restored-draft-library"

    use_cases.restore_local_library_backup(
        archive,
        restored_root,
        settings=settings,
    )
    restored = Settings(researchmind_data_dir=restored_root)

    assert use_cases.get_note_draft(draft.id, settings=restored) == draft
    assert use_cases.list_note_evidence(
        draft.id,
        settings=restored,
    ) == [evidence]
