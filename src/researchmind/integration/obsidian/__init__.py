"""Public Obsidian Markdown and Vault integration API."""

from researchmind.integration.obsidian.errors import (
    MarkdownRenderError,
    ObsidianError,
    VaultConfigurationError,
    VaultBackupError,
    VaultWriteError,
)
from researchmind.integration.obsidian.backup import (
    create_markdown_backup,
    restore_markdown_backup,
)
from researchmind.integration.obsidian.markdown import render_markdown
from researchmind.integration.obsidian.vault import (
    sanitize_filename,
    validate_vault_destination,
    write_note_to_vault,
)

__all__ = [
    "MarkdownRenderError",
    "ObsidianError",
    "VaultConfigurationError",
    "VaultBackupError",
    "VaultWriteError",
    "create_markdown_backup",
    "render_markdown",
    "sanitize_filename",
    "restore_markdown_backup",
    "validate_vault_destination",
    "write_note_to_vault",
]
