"""Captured research knowledge model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from researchmind.models.code_selection import CodeSelection
from researchmind.models.text_block import BoundingBox
from researchmind.models.evidence_link import EvidenceLink


@dataclass
class KnowledgeNote:
    """A traceable knowledge entry ready for Markdown rendering."""

    title: str
    source: str
    source_type: str = "pdf"
    authors: list[str] = field(default_factory=list)
    page_number: int | None = None
    block_index: int | None = None
    bbox: BoundingBox | None = None
    selected_text: str | None = None
    translation: str | None = None
    latex: str | None = None
    question: str | None = None
    ai_explanation: str | None = None
    user_notes: str | None = None
    tags: list[str] = field(default_factory=list)
    evidence_links: list[EvidenceLink] = field(default_factory=list)
    code_selection: CodeSelection | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
