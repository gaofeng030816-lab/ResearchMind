"""G3-A candidate event contract; deliberately not imported by production code.

Offsets are Unicode code points, not JavaScript UTF-16 units. A future browser
adapter must convert explicitly. Spans and boxes come from a trusted page snapshot;
client text/geometry never become authoritative provenance.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PageSnapshot:
    revision: str
    instance: str
    page: int
    spans: tuple[Span, ...]


@dataclass(frozen=True)
class Selection:
    revision: str
    page: int
    sequence: int
    text: str
    ranges: tuple[tuple[int, int, int], ...]
    span_boxes: tuple[tuple[float, float, float, float], ...]


def validate_selection(
    event: object, snapshot: PageSnapshot, *, last_sequence: int = 0
) -> Selection:
    """Reject malformed/stale events; caller advances sequence only on success.

    This first slice supports one page with ordered non-overlapping span ranges.
    Newlines between ranges are explicit canonical separators, not a claim about
    PDF reading order. Full-span boxes are coarse, not selected-glyph geometry.
    Instance matching prevents accidental cross-mount events, not malicious JS.
    """
    keys = {"version", "revision", "instance", "page", "sequence", "ranges", "text"}
    if not isinstance(event, dict) or set(event) != keys:
        raise ValueError("Invalid selection envelope")
    if type(event["version"]) is not int or event["version"] != 1:
        raise ValueError("Unsupported selection version")
    if event["revision"] != snapshot.revision or event["instance"] != snapshot.instance:
        raise ValueError("Stale document or component instance")
    if type(event["page"]) is not int or event["page"] != snapshot.page:
        raise ValueError("Wrong page")
    sequence = event["sequence"]
    if type(sequence) is not int or not last_sequence < sequence <= 2**53 - 1:
        raise ValueError("Stale or invalid sequence")
    ranges = event["ranges"]
    text = event["text"]
    if not isinstance(text, str) or not 0 < len(text) <= 8000:
        raise ValueError("Invalid text budget")
    if not isinstance(ranges, list) or not 0 < len(ranges) <= 128:
        raise ValueError("Invalid range budget")
    parts: list[str] = []
    checked: list[tuple[int, int, int]] = []
    boxes: list[tuple[float, float, float, float]] = []
    previous_span, previous_end = -1, 0
    for item in ranges:
        if not isinstance(item, list) or len(item) != 3 or any(type(n) is not int for n in item):
            raise ValueError("Invalid range")
        index, start, end = item
        if not 0 <= index < len(snapshot.spans):
            raise ValueError("Unknown span")
        span = snapshot.spans[index]
        if not 0 <= start < end <= len(span.text):
            raise ValueError("Invalid character offsets")
        if index < previous_span or (index == previous_span and start < previous_end):
            raise ValueError("Unordered or overlapping ranges")
        previous_span, previous_end = index, end
        parts.append(span.text[start:end])
        checked.append((index, start, end))
        boxes.append(span.bbox)
    canonical = "\n".join(parts)
    if canonical != text:
        raise ValueError("Selection text differs from snapshot")
    return Selection(snapshot.revision, snapshot.page, sequence, canonical, tuple(checked), tuple(boxes))
