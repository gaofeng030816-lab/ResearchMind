"""Tests for safe non-overwriting Obsidian Vault writes."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from researchmind.integration.obsidian import (
    MarkdownRenderError,
    VaultConfigurationError,
    VaultWriteError,
    sanitize_filename,
    validate_vault_destination,
    write_markdown_to_vault,
    write_note_to_vault,
)
from researchmind.models import KnowledgeNote


def test_write_note_creates_configured_subdirectory_and_utf8_markdown(
    temporary_vault: Path,
) -> None:
    note = _note(title="Concept: momentum / update")

    output_path = write_note_to_vault(
        note,
        vault_path=temporary_vault,
        subdirectory="ResearchMind/Reading",
    )

    assert output_path.parent == temporary_vault / "ResearchMind" / "Reading"
    assert output_path.name.startswith("2026-08-27-")
    assert output_path.suffix == ".md"
    assert ":" not in output_path.name
    assert "/" not in output_path.name
    assert "中文理解" in output_path.read_text(encoding="utf-8")


def test_collision_adds_sequence_without_overwriting_existing_note(
    temporary_vault: Path,
) -> None:
    first = write_note_to_vault(
        _note(),
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
    )
    original_content = first.read_text(encoding="utf-8")

    second = write_note_to_vault(
        _note(user_notes="different content"),
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
    )

    assert first.name == "2026-08-27-Test note.md"
    assert second.name == "2026-08-27-Test note-2.md"
    assert first.read_text(encoding="utf-8") == original_content
    assert "different content" in second.read_text(encoding="utf-8")


def test_filename_sanitization_blocks_traversal_illegal_and_reserved_names() -> None:
    sanitized = sanitize_filename("../unsafe\\name:<value>?*")

    assert ".." not in sanitized
    assert not any(character in sanitized for character in '<>:"/\\|?*')
    assert sanitize_filename("CON") == "note-CON"
    assert sanitize_filename("CON.txt") == "note-CON.txt"

    with pytest.raises(MarkdownRenderError):
        sanitize_filename("...   ")


@pytest.mark.parametrize("subdirectory", ("../outside", ".", "C:\\outside"))
def test_subdirectory_rejects_traversal_and_non_relative_paths(
    temporary_vault: Path,
    subdirectory: str,
) -> None:
    with pytest.raises(VaultConfigurationError):
        write_note_to_vault(
            _note(),
            vault_path=temporary_vault,
            subdirectory=subdirectory,
        )


def test_invalid_vault_root_is_reported(tmp_path: Path) -> None:
    with pytest.raises(VaultConfigurationError, match="does not exist"):
        write_note_to_vault(
            _note(),
            vault_path=tmp_path / "missing-vault",
            subdirectory="ResearchMind",
        )

    file_path = tmp_path / "not-a-directory"
    file_path.write_text("content", encoding="utf-8")
    with pytest.raises(VaultConfigurationError, match="not a directory"):
        write_note_to_vault(
            _note(),
            vault_path=file_path,
            subdirectory="ResearchMind",
        )


def test_existing_file_cannot_be_used_as_output_subdirectory(
    temporary_vault: Path,
) -> None:
    output_file = temporary_vault / "ResearchMind"
    output_file.write_text("not a directory", encoding="utf-8")

    with pytest.raises(VaultConfigurationError, match="not a directory"):
        write_note_to_vault(
            _note(),
            vault_path=temporary_vault,
            subdirectory="ResearchMind",
        )


def test_vault_destination_rejects_resolved_path_outside_vault(
    temporary_vault: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    linked_directory = temporary_vault / "Linked"
    linked_directory.mkdir()
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    path_type = type(temporary_vault)
    original_resolve = path_type.resolve

    def resolve_candidate(
        self: Path,
        strict: bool = False,
    ) -> Path:
        if self == linked_directory:
            return outside_directory
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(path_type, "resolve", resolve_candidate)

    with pytest.raises(VaultConfigurationError, match="stay inside the Vault"):
        validate_vault_destination(temporary_vault, "Linked")


def test_write_failure_is_exposed_as_project_error(
    temporary_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path_type = type(temporary_vault)

    def fail_open(self: Path, *args: object, **kwargs: object) -> object:
        raise PermissionError("simulated permission failure")

    monkeypatch.setattr(path_type, "open", fail_open)

    with pytest.raises(VaultWriteError, match="Could not write") as error:
        write_note_to_vault(
            _note(),
            vault_path=temporary_vault,
            subdirectory="ResearchMind",
        )

    assert error.value.__cause__ is None


def test_pre_rendered_markdown_is_written_byte_for_byte_without_overwrite(
    temporary_vault: Path,
) -> None:
    created_at = datetime(2026, 9, 8, 10, 0, tzinfo=UTC)
    markdown = "# 精确预览\n\n正文。\n"

    first = write_markdown_to_vault(
        title="精确预览",
        markdown=markdown,
        created_at=created_at,
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
    )
    second = write_markdown_to_vault(
        title="精确预览",
        markdown=markdown,
        created_at=created_at,
        vault_path=temporary_vault,
        subdirectory="ResearchMind",
    )

    assert first.name == "2026-09-08-精确预览.md"
    assert second.name == "2026-09-08-精确预览-2.md"
    assert first.read_bytes() == markdown.encode("utf-8")
    assert second.read_bytes() == markdown.encode("utf-8")


def _note(
    *,
    title: str = "Test note",
    user_notes: str = "中文理解",
) -> KnowledgeNote:
    return KnowledgeNote(
        title=title,
        source="Fixture Paper",
        selected_text="source quote",
        user_notes=user_notes,
        created_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
    )
