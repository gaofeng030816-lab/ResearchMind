"""Captured research knowledge model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class KnowledgeNote:
    """A traceable knowledge entry ready for Markdown rendering."""

    title: str
    source: str
    authors: list[str] = field(default_factory=list)
    page_number: int | None = None
    selected_text: str | None = None
    translation: str | None = None
    question: str | None = None
    ai_explanation: str | None = None
    user_notes: str | None = None
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
