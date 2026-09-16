"""Safe, non-overwriting Markdown writes into an Obsidian Vault."""

from __future__ import annotations

from datetime import datetime
from itertools import count
from pathlib import Path
import re
import unicodedata

from researchmind.integration.obsidian.errors import (
    MarkdownRenderError,
    VaultConfigurationError,
    VaultWriteError,
)
from researchmind.integration.obsidian.markdown import (
    MAX_DRAFT_EXPORT_CHARACTERS,
    render_markdown,
)
from researchmind.models import KnowledgeNote


MAX_FILENAME_STEM_LENGTH = 100
_INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_REPEATED_DASHES = re.compile(r"-{2,}")
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def write_note_to_vault(
    note: KnowledgeNote,
    *,
    vault_path: Path,
    subdirectory: str,
) -> Path:
    """Render and exclusively create one Markdown file inside the Vault."""

    markdown = render_markdown(note)
    return write_markdown_to_vault(
        title=note.title,
        markdown=markdown,
        created_at=note.created_at,
        vault_path=vault_path,
        subdirectory=subdirectory,
    )


def write_markdown_to_vault(
    *,
    title: str,
    markdown: str,
    created_at: datetime,
    vault_path: Path,
    subdirectory: str,
) -> Path:
    """Exclusively create one already-previewed Markdown document."""

    if (
        not isinstance(markdown, str)
        or not markdown.strip()
        or "\x00" in markdown
        or len(markdown) > MAX_DRAFT_EXPORT_CHARACTERS
    ):
        raise MarkdownRenderError("Markdown export content is invalid or too large.")
    output_directory = _prepare_output_directory(vault_path, subdirectory)
    filename_stem = (
        f"{created_at.date().isoformat()}-{sanitize_filename(title)}"
    )

    for collision_index in count(1):
        suffix = "" if collision_index == 1 else f"-{collision_index}"
        candidate = output_directory / f"{filename_stem}{suffix}.md"
        try:
            with candidate.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(markdown)
        except FileExistsError:
            continue
        except OSError:
            raise VaultWriteError("Could not write the Markdown note to the Vault.") from None
        return candidate

    raise VaultWriteError("Could not allocate a unique Markdown filename.")


def sanitize_filename(title: str) -> str:
    """Convert a note title to one safe cross-platform filename component."""

    normalized = unicodedata.normalize("NFKC", " ".join(title.split()))
    sanitized = _INVALID_FILENAME_CHARACTERS.sub("-", normalized)
    sanitized = _REPEATED_DASHES.sub("-", sanitized).strip(" .-")
    if not sanitized:
        raise MarkdownRenderError("Knowledge note title cannot form a filename.")

    sanitized = sanitized[:MAX_FILENAME_STEM_LENGTH].rstrip(" .-")
    if sanitized.split(".", maxsplit=1)[0].upper() in _WINDOWS_RESERVED_NAMES:
        sanitized = f"note-{sanitized}"
    if not sanitized:
        raise MarkdownRenderError("Knowledge note title cannot form a filename.")
    return sanitized


def _prepare_output_directory(vault_path: Path, subdirectory: str) -> Path:
    candidate = validate_vault_destination(vault_path, subdirectory)
    resolved_vault = Path(vault_path).expanduser().resolve(strict=True)

    try:
        candidate.mkdir(parents=True, exist_ok=True)
        resolved_output = candidate.resolve(strict=True)
    except OSError:
        raise VaultWriteError("Could not create the configured Vault subdirectory.") from None

    if not resolved_output.is_relative_to(resolved_vault):
        raise VaultConfigurationError("Obsidian subdirectory resolves outside the Vault.")
    if not resolved_output.is_dir():
        raise VaultConfigurationError("Configured Obsidian output path is not a directory.")
    return resolved_output


def validate_vault_destination(vault_path: Path, subdirectory: str) -> Path:
    """Validate a Vault destination without creating or modifying directories."""

    try:
        resolved_vault = Path(vault_path).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise VaultConfigurationError(
            "Configured Obsidian Vault path does not exist or is inaccessible."
        ) from None
    if not resolved_vault.is_dir():
        raise VaultConfigurationError("Configured Obsidian Vault path is not a directory.")

    relative_directory = _validated_relative_directory(subdirectory)
    candidate = (resolved_vault / relative_directory).resolve(strict=False)
    if not candidate.is_relative_to(resolved_vault):
        raise VaultConfigurationError("Obsidian subdirectory must stay inside the Vault.")
    if candidate.exists() and not candidate.is_dir():
        raise VaultConfigurationError("Configured Obsidian output path is not a directory.")
    return candidate


def _validated_relative_directory(subdirectory: str) -> Path:
    normalized = subdirectory.strip()
    if not normalized or normalized in {".", ".."}:
        raise VaultConfigurationError("Obsidian subdirectory must not be blank or relative-dot.")

    relative_directory = Path(normalized)
    if relative_directory.is_absolute() or relative_directory.drive:
        raise VaultConfigurationError("Obsidian subdirectory must be a relative path.")
    if any(part in {".", ".."} for part in relative_directory.parts):
        raise VaultConfigurationError("Obsidian subdirectory cannot contain path traversal.")
    return relative_directory
