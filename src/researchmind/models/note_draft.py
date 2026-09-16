"""Durable, framework-independent note draft models for V3-G4."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


NoteDraftStatus = Literal["active", "archived"]
EvidenceKind = Literal[
    "source_text",
    "translation",
    "latex",
    "question",
    "answer",
    "code",
]
EvidenceOrigin = Literal[
    "browser_selection",
    "translation_provider",
    "latex_conversion",
    "user_question",
    "assistant_response",
    "code_selection",
    "user_entry",
]
EvidenceSourceState = Literal["current", "stale", "detached"]


@dataclass(frozen=True)
class NoteDraft:
    """One editable Markdown draft stored in the ResearchMind library."""

    id: str
    title: str
    body_markdown: str
    status: NoteDraftStatus
    revision: int
    created_at: datetime
    updated_at: datetime
    record_id: str | None = None
    asset_id: str | None = None


@dataclass(frozen=True)
class EvidenceSnapshot:
    """One explicitly captured evidence item with immutable source content."""

    id: str
    draft_id: str
    kind: EvidenceKind
    content: str
    source_label: str
    origin: EvidenceOrigin
    included: bool
    sort_order: int
    created_at: datetime
    locator: dict[str, object] = field(default_factory=dict)
    source_record_id: str | None = None
    source_asset_id: str | None = None
    source_revision: int | None = None
    source_sha256: str | None = None
    selection_id: str | None = None


@dataclass(frozen=True)
class NoteDraftPreview:
    """One exact, revision-bound Markdown preview awaiting explicit export."""

    draft_id: str
    draft_revision: int
    title: str
    markdown: str
    sha256: str
    included_evidence_count: int
