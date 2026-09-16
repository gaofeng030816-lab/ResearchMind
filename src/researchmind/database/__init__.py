"""Public SQLite and managed-library infrastructure API."""

from researchmind.database.errors import (
    LibraryBackupError,
    LibraryConfirmationError,
    LibraryConfigurationError,
    LibraryConflictError,
    LibraryDatabaseError,
    LibraryError,
    LibraryImportError,
    LibraryMigrationError,
    LibraryNotFoundError,
    LibrarySchemaError,
    LibraryVersionError,
)
from researchmind.database.backup import (
    BACKUP_FORMAT,
    create_library_backup,
    restore_library_backup,
)
from researchmind.database.repository import LibraryRepository
from researchmind.database.note_draft_repository import NoteDraftRepository
from researchmind.database.schema import (
    LATEST_SCHEMA_VERSION,
    initialize_database,
    migrate_connection,
)
from researchmind.database.storage import (
    DATABASE_FILENAME,
    LibraryPaths,
    ManagedStorage,
    QuarantinedAsset,
    StagedCodeAsset,
    StagedAsset,
    prepare_library_paths,
)

__all__ = [
    "LATEST_SCHEMA_VERSION",
    "DATABASE_FILENAME",
    "BACKUP_FORMAT",
    "LibraryPaths",
    "LibraryConfirmationError",
    "LibraryBackupError",
    "LibraryConfigurationError",
    "LibraryConflictError",
    "LibraryDatabaseError",
    "LibraryError",
    "LibraryImportError",
    "LibraryMigrationError",
    "LibraryNotFoundError",
    "LibraryRepository",
    "NoteDraftRepository",
    "LibrarySchemaError",
    "LibraryVersionError",
    "ManagedStorage",
    "QuarantinedAsset",
    "StagedCodeAsset",
    "StagedAsset",
    "initialize_database",
    "create_library_backup",
    "migrate_connection",
    "prepare_library_paths",
    "restore_library_backup",
]
