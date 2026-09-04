"""Project errors for local code reading and approved T5-B1 writes."""


class CodeProjectError(Exception):
    """Base error safe to surface for local code-project operations."""


class CodeProjectPathError(CodeProjectError):
    """Raised when the requested project folder is unavailable or invalid."""


class CodeProjectLimitError(CodeProjectError):
    """Raised when a project exceeds an approved T3 resource limit."""


class CodeProjectReadError(CodeProjectError):
    """Raised when project metadata or source bytes cannot be read safely."""


class CodeChangeError(CodeProjectError):
    """Base error safe to surface for the narrow T5-B1 write boundary."""


class CodeChangePathError(CodeChangeError):
    """Raised when a write or recovery target is missing or unsafe."""


class CodeChangeConflictError(CodeChangeError):
    """Raised when a source or recovery hash no longer matches."""


class CodeChangeWriteError(CodeChangeError):
    """Raised when recovery or atomic replacement cannot complete safely."""
