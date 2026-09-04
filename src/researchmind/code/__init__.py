"""Local code-project infrastructure with one narrow T5-B1 writer."""

from researchmind.code.change_writer import (
    apply_code_change,
    code_file_from_proposal,
    code_file_from_recovery,
    read_code_snapshot,
    rollback_code_change,
)

from researchmind.code.errors import (
    CodeChangeConflictError,
    CodeChangeError,
    CodeChangePathError,
    CodeChangeWriteError,
    CodeProjectError,
    CodeProjectLimitError,
    CodeProjectPathError,
    CodeProjectReadError,
)
from researchmind.code.reader import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOTAL_BYTES,
    open_code_project,
)

__all__ = [
    "CodeChangeConflictError",
    "CodeChangeError",
    "CodeChangePathError",
    "CodeChangeWriteError",
    "CodeProjectError",
    "CodeProjectLimitError",
    "CodeProjectPathError",
    "CodeProjectReadError",
    "DEFAULT_MAX_FILE_BYTES",
    "DEFAULT_MAX_FILES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "apply_code_change",
    "code_file_from_proposal",
    "code_file_from_recovery",
    "open_code_project",
    "read_code_snapshot",
    "rollback_code_change",
]
