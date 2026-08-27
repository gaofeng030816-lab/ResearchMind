"""Detected figure or embedded-image region model."""

from dataclasses import dataclass

from researchmind.models.text_block import BoundingBox


@dataclass(frozen=True)
class FigureRegion:
    """A page region containing one embedded figure or image."""

    figure_index: int
    bbox: BoundingBox
