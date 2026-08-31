"""Project-defined errors for Obsidian Markdown and Vault operations."""


class ObsidianError(Exception):
    """Base class for failures at the Obsidian integration boundary."""


class MarkdownRenderError(ObsidianError):
    """Raised when a KnowledgeNote cannot be rendered safely."""


class VaultConfigurationError(ObsidianError):
    """Raised when the configured Vault or subdirectory is invalid."""


class VaultWriteError(ObsidianError):
    """Raised when a Markdown note cannot be written to the Vault."""


class VaultBackupError(ObsidianError):
    """Raised when a Markdown backup or restore cannot be completed safely."""
