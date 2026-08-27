"""Extracted text block model."""

from dataclasses import dataclass


BoundingBox = tuple[float, float, float, float]


@dataclass
class TextBlock:
    """A text block extracted from one document page."""

    block_index: int
    text: str
    bbox: BoundingBox | None = None
