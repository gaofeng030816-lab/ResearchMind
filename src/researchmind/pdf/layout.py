"""Copy-friendly text normalization and geometric PDF reading order.

The recursive whitespace-cut approach is informed by OpenDataLoader PDF's
documented Apache-2.0 XY-Cut++ design. This is a ResearchMind-specific Python
implementation for the existing ``TextBlock`` model and PyMuPDF coordinate
system; it does not bundle upstream source, Java runtime, or hybrid services.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from researchmind.models import TextBlock, TextBlockRole


MIN_GAP_POINTS = 5.0
NARROW_BLOCK_WIDTH_RATIO = 0.10
MAX_HEADING_CHARS = 160
MAX_CAPTION_CHARS = 500
MAX_FORMULA_CHARS = 500
MAX_NUMBERED_HEADING_WORDS = 16
MAX_SECTION_NUMBER_COMPONENT = 999

_CAPTION_PATTERN = re.compile(
    r"^(?P<label>(?:fig(?:ure)?\.?|table)\s*"
    r"(?:[a-z]?\d+(?:\.\d+)*[a-z]?|[ivxlcdm]+)"
    r"|[图表]\s*(?:\d+(?:\.\d+)*|[一二三四五六七八九十百]+))"
    r"(?P<separator>\s+|[.:：、-](?!\d)[\s.:：、-]*|$)(?P<rest>.*)$",
    re.IGNORECASE,
)
_NUMERIC_HEADING_PATTERN = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*)[.)]?\s+(?P<title>.+)$"
)
_ROMAN_HEADING_PATTERN = re.compile(
    r"^(?P<number>[IVXLCDM]+)[.)]\s+(?P<title>.+)$"
)
_CHINESE_HEADING_PATTERN = re.compile(
    r"^第[0-9一二三四五六七八九十百]+[章节]\s*\S+"
)
_CAPTION_REFERENCE_START_PATTERN = re.compile(
    r"^(?:shows?|shown|reorganises?|reorganizes?|describes?|illustrates?|"
    r"presents?|gives?|contains?|reports?|compares?|summari[sz]es?|depicts?|"
    r"demonstrates?|lists?|introduces?|provides?|is|are|was|were)\b",
    re.IGNORECASE,
)
_CHINESE_CAPTION_REFERENCE_START_PATTERN = re.compile(
    r"^(?:给出(?:了)?|描述(?:了)?|显示(?:了)?|说明(?:了)?|展示(?:了)?|"
    r"表明(?:了)?|列出(?:了)?|比较(?:了)?|是|中|可见)"
)
_PROCEDURE_OR_EXERCISE_START_PATTERN = re.compile(
    r"^(?:procedure|input|output|return|repeat|for\b|while\b|sample\b|"
    r"说明|证明|比较|试求|写出|考虑|设\b|已知|假设)",
    re.IGNORECASE,
)
_REFERENCE_HINT_PATTERN = re.compile(
    r"(?:https?://|\bdoi\b|\bet\s+al\.|\((?:19|20)\d{2}[a-z]?\))",
    re.IGNORECASE,
)
_STRONG_MATH_PATTERN = re.compile(
    r"[∑∫∏√∂∇∞±×÷≤≥≈≠≡∈∉⊂⊆⊗⊕→←↔]"
)
_RELATION_PATTERN = re.compile(r"(?:=|≤|≥|≈|≠|≡|(?<!<)<(?!<)|(?<!>)>(?!>))")
_OPERATOR_OR_NOTATION_PATTERN = re.compile(
    r"(?:[+*/^_]|(?<!\w)-(?!\s)|[()[\]{}]|\b(?:sin|cos|tan|log|exp)\b)",
    re.IGNORECASE,
)
_DERIVATIVE_PATTERN = re.compile(
    r"(?:\bd[A-Za-zα-ωΑ-Ω]+\s*/\s*d[A-Za-zα-ωΑ-Ω]+|∂)",
)
_LATEX_PATTERN = re.compile(
    r"\\(?:frac|sum|int|prod|sqrt|partial|nabla|begin|left|right)\b"
)
_CODE_HINT_PATTERN = re.compile(
    r"(?:^R>|<-|\bcursor\.execute\b|\bSELECT\b|\b(?:def|class|import)\s+|"
    r"\[[^\]]*\bfor\b[^\]]*\])",
    re.IGNORECASE,
)
_COMMON_HEADINGS = frozenset(
    {
        "abstract",
        "introduction",
        "background",
        "related work",
        "method",
        "methods",
        "methodology",
        "experiments",
        "experimental results",
        "results",
        "discussion",
        "conclusion",
        "conclusions",
        "references",
        "摘要",
        "引言",
        "背景",
        "相关工作",
        "方法",
        "实验",
        "实验结果",
        "结果",
        "讨论",
        "结论",
        "参考文献",
    }
)


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


def normalize_formula_text(text: str) -> str:
    """Keep formula line boundaries while removing extraction-only spacing."""

    return "\n".join(
        " ".join(line.split())
        for line in text.splitlines()
        if line.strip()
    ).strip()


def classify_block_role(text: str) -> TextBlockRole:
    """Classify only high-confidence structural and mathematical blocks."""

    normalized = " ".join(text.split())
    if not normalized:
        return "body"
    if len(normalized) <= MAX_CAPTION_CHARS and _looks_like_caption(normalized):
        return "caption"
    if len(normalized) <= MAX_FORMULA_CHARS and _looks_like_formula(normalized):
        return "formula"
    if len(normalized) > MAX_HEADING_CHARS:
        return "body"

    normalized_heading = normalized.rstrip(":：").casefold()
    if normalized_heading in _COMMON_HEADINGS:
        return "heading"
    if _looks_like_numbered_heading(normalized):
        return "heading"
    if _CHINESE_HEADING_PATTERN.match(normalized):
        return "heading"
    return "body"


def _looks_like_caption(text: str) -> bool:
    match = _CAPTION_PATTERN.match(text)
    if match is None:
        return False

    remainder = match.group("rest").strip()
    if not remainder:
        return True
    if _CAPTION_REFERENCE_START_PATTERN.match(remainder):
        return False
    if _CHINESE_CAPTION_REFERENCE_START_PATTERN.match(remainder):
        return False
    return True


def _looks_like_formula(text: str) -> bool:
    if _REFERENCE_HINT_PATTERN.search(text) or _CODE_HINT_PATTERN.search(text):
        return False

    latin_word_count = len(re.findall(r"[A-Za-z]{2,}", text))
    cjk_character_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if latin_word_count > 8 or cjk_character_count > 16:
        return False

    if _LATEX_PATTERN.search(text) or _DERIVATIVE_PATTERN.search(text):
        return True
    if _STRONG_MATH_PATTERN.search(text):
        return len(text.split()) <= 16
    if not _RELATION_PATTERN.search(text):
        return False
    if text.endswith((".", "?", "!", "。", "？", "！")):
        return False
    if "$" in text and "=" not in text:
        return False

    has_notation = bool(_OPERATOR_OR_NOTATION_PATTERN.search(text))
    return has_notation or len(text) <= 80


def _looks_like_numbered_heading(text: str) -> bool:
    numeric_match = _NUMERIC_HEADING_PATTERN.match(text)
    if numeric_match is not None:
        components = [int(value) for value in numeric_match.group("number").split(".")]
        if any(value > MAX_SECTION_NUMBER_COMPONENT for value in components):
            return False
        return _looks_like_heading_title(numeric_match.group("title"))

    roman_match = _ROMAN_HEADING_PATTERN.match(text)
    if roman_match is None:
        return False
    return _looks_like_heading_title(roman_match.group("title"))


def _looks_like_heading_title(title: str) -> bool:
    normalized = title.strip()
    if not normalized:
        return False

    common_title = normalized.rstrip(":：").casefold() in _COMMON_HEADINGS
    first_character = normalized[0]
    if first_character.isascii() and first_character.isalpha():
        if first_character.islower() and not common_title:
            return False
    elif not ("\u4e00" <= first_character <= "\u9fff"):
        return False

    if normalized.endswith((".", "?", "!", ";", "。", "？", "！", "；")):
        return False
    if any(mark in normalized for mark in ("=", "<", ">")):
        return False
    if "." in normalized or "," in normalized or ";" in normalized:
        return False
    if _REFERENCE_HINT_PATTERN.search(normalized):
        return False
    if _PROCEDURE_OR_EXERCISE_START_PATTERN.match(normalized):
        return False
    if len(re.findall(r"[A-Za-z0-9]+", normalized)) > MAX_NUMBERED_HEADING_WORDS:
        return False
    return True


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
