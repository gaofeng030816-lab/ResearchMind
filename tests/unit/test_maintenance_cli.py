"""T6-B maintenance CLI smoke coverage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from researchmind.maintenance import main
from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.models import UploadedFileData


def test_diagnose_cli_emits_safe_json(
    tmp_path: Path,
    clean_config_environment: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "LLM_BASE_URL=https://example.test/v1",
                "LLM_API_KEY=cli-secret",
                "LLM_MODEL=test-model",
                f"OBSIDIAN_VAULT_PATH={vault}",
                "OBSIDIAN_SUBDIRECTORY=ResearchMind",
            )
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "diagnose",
            "--env-file",
            str(env_file),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["has_errors"] is False
    assert "cli-secret" not in captured.out
    assert captured.err == ""


def test_backup_and_restore_cli_round_trip(
    temporary_vault: Path,
    tmp_path: Path,
    clean_config_environment: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = temporary_vault / "ResearchMind"
    source.mkdir()
    (source / "note.md").write_text("# durable\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                f"OBSIDIAN_VAULT_PATH={temporary_vault}",
                "OBSIDIAN_SUBDIRECTORY=ResearchMind",
            )
        ),
        encoding="utf-8",
    )
    archive = tmp_path / "backup.zip"

    backup_exit = main(
        [
            "backup",
            "--env-file",
            str(env_file),
            "--output",
            str(archive),
        ]
    )
    restore_exit = main(
        [
            "restore",
            "--archive",
            str(archive),
            "--vault",
            str(temporary_vault),
            "--subdirectory",
            "Recovered",
        ]
    )

    captured = capsys.readouterr()
    assert backup_exit == 0
    assert restore_exit == 0
    assert (temporary_vault / "Recovered" / "note.md").read_text(
        encoding="utf-8"
    ) == "# durable\n"
    assert "1 Markdown" in captured.out


def test_library_backup_and_restore_cli_round_trip(
    tmp_path: Path,
    clean_config_environment: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "library"
    settings = Settings(researchmind_data_dir=data_dir)
    imported = use_cases.import_code_directory_to_library(
        [
            UploadedFileData(
                name="demo/main.py",
                content=b"value = 42\n",
            )
        ],
        settings=settings,
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"RESEARCHMIND_DATA_DIR={data_dir}\n",
        encoding="utf-8",
    )
    archive = tmp_path / "library-backup.zip"
    restored_dir = tmp_path / "restored-library"

    backup_exit = main(
        [
            "library-backup",
            "--env-file",
            str(env_file),
            "--output",
            str(archive),
        ]
    )
    restore_exit = main(
        [
            "library-restore",
            "--archive",
            str(archive),
            "--data-dir",
            str(restored_dir),
            "--env-file",
            str(env_file),
        ]
    )

    restored = use_cases.list_library_entries(
        settings=Settings(researchmind_data_dir=restored_dir)
    )
    captured = capsys.readouterr()
    assert backup_exit == 0
    assert restore_exit == 0
    assert restored[0].record.id == imported.entry.record.id
    assert "library backup" in captured.out
