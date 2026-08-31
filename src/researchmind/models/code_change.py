"""Project-owned data models for one approved T5-B1 source replacement."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4


@dataclass(frozen=True)
class CodeFileSnapshot:
    """One current on-disk UTF-8 source snapshot used for conflict checks."""

    project_id: str
    relative_path: str
    source: str = field(repr=False)
    raw_sha256: str
    size_bytes: int
    has_utf8_bom: bool


@dataclass(frozen=True)
class CodeChangeProposal:
    """A validated, preview-only replacement that has no write authority."""

    project_id: str
    selection_id: str
    relative_path: str
    start_line: int
    end_line: int
    original_sha256: str
    candidate_sha256: str
    replacement_text: str = field(repr=False)
    candidate_source: str = field(repr=False)
    unified_diff: str
    replacement_character_count: int
    changed_line_count: int
    syntax_valid: bool
    has_utf8_bom: bool
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass(frozen=True)
class CodeChangeReceipt:
    """Non-sensitive metadata proving one confirmed replacement was applied."""

    project_id: str
    proposal_id: str
    relative_path: str
    start_line: int
    end_line: int
    original_sha256: str
    applied_sha256: str
    recovery_relative_path: str
    applied_at: str


@dataclass(frozen=True)
class CodeChangeRollbackReceipt:
    """Non-sensitive metadata proving one confirmed rollback was applied."""

    project_id: str
    proposal_id: str
    relative_path: str
    restored_sha256: str
    recovery_relative_path: str
    rolled_back_at: str


CodeChangeAuditAction = Literal["propose", "apply", "cancel", "rollback"]
CodeChangeAuditStatus = Literal["success", "failed", "canceled"]


@dataclass(frozen=True)
class CodeChangeAuditEvent:
    """Session-only metadata audit that never stores source or prompt content."""

    action: CodeChangeAuditAction
    status: CodeChangeAuditStatus
    relative_path: str
    start_line: int
    end_line: int
    occurred_at: str
    before_sha256: str | None = None
    after_sha256: str | None = None
    recovery_relative_path: str | None = None
    error_type: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
