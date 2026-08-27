"""Reading selection model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ReadingSelection:
    """User-selected reading content with source-specific location data."""

    text: str
    source_type: str = "pdf"
    locator: dict[str, object] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
