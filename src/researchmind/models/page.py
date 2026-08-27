"""Extracted document page model."""

from dataclasses import dataclass, field

from researchmind.models.text_block import TextBlock


@dataclass
class Page:
    """Text and blocks extracted from a page."""

    page_number: int
    text: str
    blocks: list[TextBlock] = field(default_factory=list)
