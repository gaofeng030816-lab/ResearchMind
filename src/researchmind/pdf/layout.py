"""Copy-friendly text normalization and geometric PDF reading order.

The recursive whitespace-cut approach is informed by OpenDataLoader PDF's
documented Apache-2.0 XY-Cut++ design. This is a ResearchMind-specific Python
implementation for the existing ``TextBlock`` model and PyMuPDF coordinate
system; it does not bundle upstream source, Java runtime, or hybrid services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from researchmind.models import TextBlock


MIN_GAP_POINTS = 5.0
NARROW_BLOCK_WIDTH_RATIO = 0.10


@dataclass(frozen=True)
class _Cut:
    position: float = 0.0
    gap: float = 0.0


def normalize_block_text(text: str) -> str:
    """Turn visual PDF line wrapping into one copy-friendly paragraph."""

    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    paragraph = lines[0]
    for line in lines[1:]:
        if paragraph.endswith(("-", "\u00ad")) and line[0].islower():
            paragraph = paragraph[:-1] + line
        else:
            paragraph += " " + line
    return paragraph.strip()


def order_text_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    """Return positioned blocks in geometric reading order."""

    positioned = [block for block in blocks if block.bbox is not None]
    unpositioned = [block for block in blocks if block.bbox is None]
    return _recursive_order(positioned) + unpositioned


def _recursive_order(blocks: list[TextBlock]) -> list[TextBlock]:
    if len(blocks) <= 1:
        return list(blocks)

    horizontal_cut = _best_cut(blocks, axis="y")
    vertical_cut = _best_vertical_cut(blocks)
    horizontal_groups = _split(blocks, horizontal_cut, axis="y")
    vertical_groups = _split(blocks, vertical_cut, axis="x")

    has_horizontal = (
        horizontal_cut.gap >= MIN_GAP_POINTS and len(horizontal_groups) == 2
    )
    has_vertical = vertical_cut.gap >= MIN_GAP_POINTS and len(vertical_groups) == 2

    if has_horizontal and (
        not has_vertical or horizontal_cut.gap >= vertical_cut.gap
    ):
        groups = horizontal_groups
    elif has_vertical:
        groups = vertical_groups
    else:
        return _sort_top_to_bottom(blocks)

    if any(len(group) == len(blocks) for group in groups):
        return _sort_top_to_bottom(blocks)

    ordered: list[TextBlock] = []
    for group in groups:
        ordered.extend(_recursive_order(group))
    return ordered


def _best_vertical_cut(blocks: list[TextBlock]) -> _Cut:
    cut = _best_cut(blocks, axis="x")
    if cut.gap >= MIN_GAP_POINTS or len(blocks) < 3:
        return cut

    left = min(_bbox(block)[0] for block in blocks)
    right = max(_bbox(block)[2] for block in blocks)
    region_width = right - left
    minimum_width = region_width * NARROW_BLOCK_WIDTH_RATIO
    filtered = [
        block
        for block in blocks
        if _bbox(block)[2] - _bbox(block)[0] >= minimum_width
    ]
    if len(filtered) < 2 or len(filtered) == len(blocks):
        return cut

    filtered_cut = _best_cut(filtered, axis="x")
    return filtered_cut if filtered_cut.gap > cut.gap else cut


def _best_cut(blocks: list[TextBlock], *, axis: Literal["x", "y"]) -> _Cut:
    if len(blocks) < 2:
        return _Cut()

    if axis == "x":
        intervals = sorted((_bbox(block)[0], _bbox(block)[2]) for block in blocks)
    else:
        intervals = sorted((_bbox(block)[1], _bbox(block)[3]) for block in blocks)

    largest = _Cut()
    previous_end = intervals[0][1]
    for start, end in intervals[1:]:
        if start > previous_end:
            gap = start - previous_end
            if gap > largest.gap:
                largest = _Cut(position=(previous_end + start) / 2.0, gap=gap)
        previous_end = max(previous_end, end)
    return largest


def _split(
    blocks: list[TextBlock],
    cut: _Cut,
    *,
    axis: Literal["x", "y"],
) -> list[list[TextBlock]]:
    if cut.gap < MIN_GAP_POINTS:
        return [list(blocks)]

    first: list[TextBlock] = []
    second: list[TextBlock] = []
    for block in blocks:
        bbox = _bbox(block)
        center = (
            (bbox[0] + bbox[2]) / 2.0
            if axis == "x"
            else (bbox[1] + bbox[3]) / 2.0
        )
        (first if center < cut.position else second).append(block)

    return [group for group in (first, second) if group]


def _sort_top_to_bottom(blocks: list[TextBlock]) -> list[TextBlock]:
    return sorted(blocks, key=lambda block: (_bbox(block)[1], _bbox(block)[0]))


def _bbox(block: TextBlock) -> tuple[float, float, float, float]:
    if block.bbox is None:
        raise ValueError("A positioned text block must have a bounding box.")
    return block.bbox
