"""Project-owned errors for SQLite and managed library storage."""


class LibraryError(Exception):
    """Base class for user-facing local-library failures."""


class LibraryConfigurationError(LibraryError):
    """Raised when the durable data root is absent or unsafe."""


class LibraryDatabaseError(LibraryError):
    """Raised when a database operation cannot be completed safely."""


class LibraryMigrationError(LibraryDatabaseError):
    """Raised when a schema migration is rolled back."""


class LibrarySchemaError(LibraryDatabaseError):
    """Raised when an existing schema does not match its declared version."""


class LibraryVersionError(LibraryDatabaseError):
    """Raised when the database was created by a newer ResearchMind version."""


class LibraryNotFoundError(LibraryError):
    """Raised when a requested record or asset is unavailable."""


class LibraryConflictError(LibraryError):
    """Raised when a durable source identity is already linked elsewhere."""


class LibraryImportError(LibraryError):
    """Raised when uploaded data cannot become a managed asset."""


class LibraryConfirmationError(LibraryError):
    """Raised when a destructive library action lacks explicit consent."""


class LibraryBackupError(LibraryError):
    """Raised when a library backup or restore cannot be verified safely."""
