"""Extracted text block model."""

from dataclasses import dataclass
from typing import Literal


BoundingBox = tuple[float, float, float, float]
TextBlockRole = Literal["body", "heading", "caption"]


@dataclass
class TextBlock:
    """A text block extracted from one document page."""

    block_index: int
    text: str
    bbox: BoundingBox | None = None
    role: TextBlockRole = "body"
