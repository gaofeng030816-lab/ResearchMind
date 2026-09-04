"""Per-document conversation model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from researchmind.models.message import Message


@dataclass
class Conversation:
    """An in-memory conversation about one document."""

    document_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
