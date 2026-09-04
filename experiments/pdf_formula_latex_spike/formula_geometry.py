"""Recognize digital-text formula regions without changing production PDF models.

This module is intentionally isolated under ``experiments``.  It reads PyMuPDF's
plain dictionaries, converts them into spike-owned dataclasses, and never calls a
model, OCR engine, network service, or file writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from statistics import median
from typing import Literal

from researchmind.llm.errors import LlmBadResponseError
from researchmind.llm.latex import parse_latex_response


BBox = tuple[float, float, float, float]
FormulaKind = Literal["display", "inline"]

_MATH_FONT_HINTS = (
    "cambria math",
    "cmex",
    "cmmi",
    "cmsy",
    "euler",
    "math",
    "mt extra",
    "symbol",
)
_MONOSPACE_FONT_HINTS = ("courier", "mono", "consolas")
_RELATION_RE = re.compile(r"(?:=|≠|≤|≥|≈|∼|∈|∉|⊂|⊆|→|↦|:=|≔)")
_STRONG_MATH_RE = re.compile(r"[α-ωΑ-Ω∑∏∫√∞∂∇±×÷·≤≥≠≈∼∈∉⊂⊆→↦]")
_NOTATION_RE = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9]*\s*[=<>≤≥≠≈∼∈⊆→:+\-*/^_]"
    r"|[=<>≤≥≠≈∼∈⊆→:+\-*/^_]\s*[A-Za-z0-9(])"
)
_INLINE_FRAGMENT_RE = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9_]*\([^\n()]{1,50}[|=,][^\n()]{1,50}\)"
    r"|[A-Za-z][A-Za-z0-9_]*\s*[=≤≥≠≈∈⊆]\s*[A-Za-z0-9(])"
)
_PROSE_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_PROSE_MARKER_RE = re.compile(
    r"\b(?:and|as|by|for|in|is|notation|of|or|the|then|to|we|where|with)\b",
    re.IGNORECASE,
)
_CODE_HINT_RE = re.compile(
    r"(?:cursor\.execute|SELECT\s+.+\s+FROM|\bdef\s+\w+\s*\(|"
    r"\bclass\s+\w+|<-\s*\w+\(|\bimport\s+\w+)",
    re.IGNORECASE,
)
_UNSAFE_TEXT_RE = re.compile(r"[\x00\r]|(?:https?://)|(?:\\(?:input|include|write|read))")

_SYMBOL_LATEX = {
    "α": r"\alpha ",
    "β": r"\beta ",
    "γ": r"\gamma ",
    "δ": r"\delta ",
    "ε": r"\epsilon ",
    "θ": r"\theta ",
    "λ": r"\lambda ",
    "μ": r"\mu ",
    "π": r"\pi ",
    "ρ": r"\rho ",
    "σ": r"\sigma ",
    "τ": r"\tau ",
    "φ": r"\phi ",
    "ω": r"\omega ",
    "Γ": r"\Gamma ",
    "Δ": r"\Delta ",
    "Θ": r"\Theta ",
    "Λ": r"\Lambda ",
    "Σ": r"\Sigma ",
    "Φ": r"\Phi ",
    "Ω": r"\Omega ",
    "∑": r"\sum ",
    "∏": r"\prod ",
    "∫": r"\int ",
    "√": r"\sqrt{}",
    "∞": r"\infty ",
    "∂": r"\partial ",
    "∇": r"\nabla ",
    "±": r"\pm ",
    "×": r"\times ",
    "÷": r"\div ",
    "·": r"\cdot ",
    "≤": r"\le ",
    "≥": r"\ge ",
    "≠": r"\ne ",
    "≈": r"\approx ",
    "∼": r"\sim ",
    "∈": r"\in ",
    "∉": r"\notin ",
    "⊂": r"\subset ",
    "⊆": r"\subseteq ",
    "→": r"\to ",
    "↦": r"\mapsto ",
    "＝": "=",
    "−": "-",
    "|": r"\mid ",
}
_SAFE_PLAIN_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    " +-*/=()[]<>,.:;_^!'?"
)


@dataclass(frozen=True, slots=True)
class FormulaCandidate:
    """One bounded formula candidate derived only from a PDF digital text layer."""

    page_number: int
    source_lines: tuple[tuple[int, int], ...]
    bbox: BBox
    source_text: str
    normalized_text: str
    kind: FormulaKind
    confidence: float
    origin: str
    signals: tuple[str, ...]
    latex_candidate: str | None

    @property
    def needs_model(self) -> bool:
        """Whether the bounded source still needs constrained model reconstruction."""

        return self.latex_candidate is None


@dataclass(frozen=True, slots=True)
class _Span:
    text: str
    bbox: BBox
    size: float
    font: str
    flags: int
    origin_y: float


def recognize_formula_candidates(
    page: object,
    *,
    page_number: int,
) -> list[FormulaCandidate]:
    """Return formula candidates from a PyMuPDF-compatible page.

    Image blocks are deliberately ignored.  The spike does not perform OCR and does
    not claim that spatially stacked rows form a fraction, matrix, or aligned system.
    """

    if isinstance(page_number, bool) or page_number < 1:
        raise ValueError("page_number must be a positive one-based integer")

    raw = page.get_text("dict", sort=False)
    candidates: list[FormulaCandidate] = []
    for block_index, block in enumerate(raw.get("blocks", [])):
        if block.get("type") != 0:
            continue
        for line_index, line in enumerate(block.get("lines", [])):
            spans = _coerce_spans(line.get("spans", []))
            if not spans:
                continue
            display = _display_candidate(
                spans,
                page_number=page_number,
                block_index=block_index,
                line_index=line_index,
            )
            if display is not None:
                candidates.append(display)
                continue
            candidates.extend(
                _inline_candidates(
                    spans,
                    page_number=page_number,
                    block_index=block_index,
                    line_index=line_index,
                )
            )
    return _merge_adjacent_displays(_deduplicate(candidates))


def _display_candidate(
    spans: list[_Span],
    *,
    page_number: int,
    block_index: int,
    line_index: int,
) -> FormulaCandidate | None:
    text = _join_span_text(spans)
    if not text or _CODE_HINT_RE.search(text) or _UNSAFE_TEXT_RE.search(text):
        return None

    signals, score = _score_line(spans, text)
    if (
        "prose_penalty" in signals
        or "sentence_penalty" in signals
        or _CJK_RE.search(text)
        or _PROSE_MARKER_RE.search(text)
    ):
        return None
    if score < 3:
        return None
    if not ({"math_font", "math_symbol", "script", "relation_notation"} & set(signals)):
        return None

    return _make_candidate(
        spans,
        page_number=page_number,
        block_index=block_index,
        line_index=line_index,
        kind="display",
        signals=signals,
        confidence=min(0.95, 0.56 + score * 0.065),
    )


def _inline_candidates(
    spans: list[_Span],
    *,
    page_number: int,
    block_index: int,
    line_index: int,
) -> list[FormulaCandidate]:
    result: list[FormulaCandidate] = []
    base_size = max(span.size for span in spans)
    consumed: set[int] = set()
    for seed_index, seed in enumerate(spans):
        if seed_index in consumed or not _span_starts_inline_math(
            seed,
            base_size=base_size,
        ):
            continue

        start_index = seed_index
        while (
            start_index > 0
            and start_index - 1 not in consumed
            and _span_is_inline_neutral(spans[start_index - 1])
            and _spans_are_close(spans[start_index - 1], spans[start_index])
        ):
            start_index -= 1

        end_index = seed_index
        while end_index + 1 < len(spans) and (
            _span_starts_inline_math(spans[end_index + 1], base_size=base_size)
            or _span_is_inline_neutral(spans[end_index + 1])
        ) and _spans_are_close(spans[end_index], spans[end_index + 1]):
            end_index += 1

        group = spans[start_index : end_index + 1]
        consumed.update(range(start_index, end_index + 1))
        text = _join_span_text(group)
        if (
            text
            and len(text) <= 160
            and _is_actionable_inline(group, text)
            and not _CODE_HINT_RE.search(text)
            and not _UNSAFE_TEXT_RE.search(text)
        ):
            signals = ["bounded_inline"]
            if any(_is_math_font(item.font) for item in group):
                signals.append("math_font")
            if _STRONG_MATH_RE.search(text):
                signals.append("math_symbol")
            if _INLINE_FRAGMENT_RE.search(text):
                signals.append("inline_pattern")
            if _has_script(group):
                signals.append("script")
            result.append(
                _make_candidate(
                    group,
                    page_number=page_number,
                    block_index=block_index,
                    line_index=line_index,
                    kind="inline",
                    signals=signals,
                    confidence=min(0.9, 0.64 + 0.06 * (len(signals) - 1)),
                )
            )
    return result


def _score_line(spans: list[_Span], text: str) -> tuple[list[str], int]:
    signals: list[str] = []
    score = 0
    total_chars = max(1, sum(len(span.text.strip()) for span in spans))
    math_font_chars = sum(
        len(span.text.strip()) for span in spans if _is_math_font(span.font)
    )

    if math_font_chars:
        signals.append("math_font")
        score += 1
        if math_font_chars / total_chars >= 0.4:
            signals.append("math_font_dominant")
            score += 2
    if _STRONG_MATH_RE.search(text):
        signals.append("math_symbol")
        score += 2
    if _has_script(spans):
        signals.append("script")
        score += 2
    if _RELATION_RE.search(text) and _NOTATION_RE.search(text):
        signals.append("relation_notation")
        score += 2
    if len(text) <= 48 and re.search(r"[+\-*/^_=≤≥∈⊆]", text):
        signals.append("compact_notation")
        score += 1

    prose_words = _PROSE_WORD_RE.findall(text)
    if len(prose_words) >= 5:
        signals.append("prose_penalty")
        score -= 3
    if len(prose_words) >= 3 and text.rstrip().endswith((".", "。", "?", "!")):
        signals.append("sentence_penalty")
        score -= 2
    if any(_is_monospace_font(span.font) for span in spans):
        signals.append("monospace_penalty")
        score -= 3
    return signals, score


def _make_candidate(
    spans: list[_Span],
    *,
    page_number: int,
    block_index: int,
    line_index: int,
    kind: FormulaKind,
    signals: list[str],
    confidence: float,
) -> FormulaCandidate:
    source_text = _join_span_text(spans)
    latex_candidate = _latex_from_spans(spans)
    return FormulaCandidate(
        page_number=page_number,
        source_lines=((block_index, line_index),),
        bbox=_union_bbox(span.bbox for span in spans),
        source_text=source_text,
        normalized_text=" ".join(source_text.split()),
        kind=kind,
        confidence=round(confidence, 3),
        origin="digital_text_geometry",
        signals=tuple(signals),
        latex_candidate=latex_candidate,
    )


def _latex_from_spans(spans: list[_Span]) -> str | None:
    source_text = _join_span_text(spans)
    if (
        not source_text
        or len(source_text) > 400
        or _CODE_HINT_RE.search(source_text)
        or _UNSAFE_TEXT_RE.search(source_text)
        or len(_PROSE_WORD_RE.findall(source_text)) > 2
    ):
        return None

    base_size = max(span.size for span in spans)
    base_origins = [
        span.origin_y for span in spans if span.size >= base_size * 0.85
    ]
    baseline = median(base_origins or [span.origin_y for span in spans])
    fragments: list[str] = []
    previous: _Span | None = None
    for span in spans:
        converted = _text_to_latex(span.text.strip())
        if converted is None:
            return None
        script_kind = _script_kind(span, base_size=base_size, baseline=baseline)
        if script_kind == "superscript":
            fragments.append(f"^{{{converted.strip()}}}")
        elif script_kind == "subscript":
            fragments.append(f"_{{{converted.strip()}}}")
        else:
            if previous is not None and _needs_space(previous, span):
                fragments.append(" ")
            fragments.append(converted)
        previous = span

    latex = re.sub(r"[ \t]+", " ", "".join(fragments)).strip()
    if not latex:
        return None
    try:
        return parse_latex_response(f"<latex>{latex}</latex>")
    except LlmBadResponseError:
        return None


def _text_to_latex(text: str) -> str | None:
    converted: list[str] = []
    for character in text:
        if character in _SYMBOL_LATEX:
            converted.append(_SYMBOL_LATEX[character])
        elif character in _SAFE_PLAIN_CHARS:
            converted.append(character)
        elif character.isspace():
            converted.append(" ")
        else:
            return None
    return "".join(converted)


def _span_starts_inline_math(span: _Span, *, base_size: float) -> bool:
    text = span.text.strip()
    return bool(
        text
        and (
            _is_math_font(span.font)
            or _STRONG_MATH_RE.search(text)
            or _INLINE_FRAGMENT_RE.fullmatch(text)
            or span.size <= base_size * 0.82
        )
    )


def _span_is_inline_neutral(span: _Span) -> bool:
    text = span.text.strip()
    if not text:
        return False
    return bool(
        len(text) <= 2
        and re.fullmatch(r"[A-Za-z0-9()[\]{},.+\-*/=|_^＝]+", text)
    )


def _spans_are_close(left: _Span, right: _Span) -> bool:
    gap = right.bbox[0] - left.bbox[2]
    return -0.5 <= gap <= max(8.0, min(left.size, right.size) * 0.75)


def _is_actionable_inline(spans: list[_Span], text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    math_font_count = sum(_is_math_font(span.font) for span in spans)
    has_relation_notation = bool(
        _RELATION_RE.search(text) and _NOTATION_RE.search(text)
    )
    return bool(
        _INLINE_FRAGMENT_RE.search(text)
        or has_relation_notation
        or (len(compact) >= 3 and math_font_count >= 2)
        or (len(compact) >= 3 and _has_script(spans))
        or (len(compact) >= 2 and _STRONG_MATH_RE.search(text))
    )


def _has_script(spans: list[_Span]) -> bool:
    if len(spans) < 2:
        return False
    base_size = max(span.size for span in spans)
    base_origins = [
        span.origin_y for span in spans if span.size >= base_size * 0.85
    ]
    baseline = median(base_origins or [span.origin_y for span in spans])
    return any(
        _script_kind(span, base_size=base_size, baseline=baseline) is not None
        for span in spans
    )


def _script_kind(
    span: _Span,
    *,
    base_size: float,
    baseline: float,
) -> Literal["superscript", "subscript"] | None:
    if span.size > base_size * 0.82:
        return None
    offset = span.origin_y - baseline
    if offset <= -base_size * 0.12:
        return "superscript"
    if offset >= base_size * 0.12:
        return "subscript"
    return None


def _coerce_spans(raw_spans: list[dict[str, object]]) -> list[_Span]:
    result: list[_Span] = []
    for raw_span in raw_spans:
        text = str(raw_span.get("text", ""))
        raw_bbox = raw_span.get("bbox")
        size = float(raw_span.get("size", 0.0))
        if not text.strip() or not _valid_bbox(raw_bbox) or not isfinite(size) or size <= 0:
            continue
        bbox = tuple(float(value) for value in raw_bbox)
        raw_origin = raw_span.get("origin")
        origin_y = (
            float(raw_origin[1])
            if isinstance(raw_origin, (list, tuple))
            and len(raw_origin) == 2
            and isfinite(float(raw_origin[1]))
            else bbox[3]
        )
        result.append(
            _Span(
                text=text,
                bbox=bbox,
                size=size,
                font=str(raw_span.get("font", "")),
                flags=int(raw_span.get("flags", 0)),
                origin_y=origin_y,
            )
        )
    return sorted(result, key=lambda span: (span.bbox[0], span.bbox[1]))


def _join_span_text(spans: list[_Span]) -> str:
    pieces: list[str] = []
    previous: _Span | None = None
    for span in spans:
        text = span.text.strip()
        if not text:
            continue
        if previous is not None and _needs_space(previous, span):
            pieces.append(" ")
        pieces.append(text)
        previous = span
    return "".join(pieces).strip()


def _needs_space(previous: _Span, current: _Span) -> bool:
    gap = current.bbox[0] - previous.bbox[2]
    threshold = max(0.8, min(previous.size, current.size) * 0.16)
    return gap > threshold


def _valid_bbox(value: object) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return False
    try:
        coordinates = tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return False
    return all(isfinite(item) for item in coordinates) and (
        coordinates[2] >= coordinates[0] and coordinates[3] >= coordinates[1]
    )


def _union_bbox(boxes: object) -> BBox:
    values = list(boxes)
    return (
        min(box[0] for box in values),
        min(box[1] for box in values),
        max(box[2] for box in values),
        max(box[3] for box in values),
    )


def _is_math_font(font: str) -> bool:
    folded = font.casefold().replace("-", " ")
    return any(hint in folded for hint in _MATH_FONT_HINTS)


def _is_monospace_font(font: str) -> bool:
    folded = font.casefold()
    return any(hint in folded for hint in _MONOSPACE_FONT_HINTS)


def _deduplicate(candidates: list[FormulaCandidate]) -> list[FormulaCandidate]:
    result: list[FormulaCandidate] = []
    seen: set[tuple[int, tuple[tuple[int, int], ...], BBox, str]] = set()
    for candidate in candidates:
        key = (
            candidate.page_number,
            candidate.source_lines,
            candidate.bbox,
            candidate.normalized_text,
        )
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


def _merge_adjacent_displays(
    candidates: list[FormulaCandidate],
) -> list[FormulaCandidate]:
    merged: list[FormulaCandidate] = []
    for candidate in candidates:
        if merged and _can_merge_display(merged[-1], candidate):
            merged[-1] = _merge_display_pair(merged[-1], candidate)
        else:
            merged.append(candidate)
    return merged


def _can_merge_display(left: FormulaCandidate, right: FormulaCandidate) -> bool:
    if (
        left.page_number != right.page_number
        or left.kind != "display"
        or right.kind != "display"
    ):
        return False
    left_height = max(0.1, left.bbox[3] - left.bbox[1])
    right_height = max(0.1, right.bbox[3] - right.bbox[1])
    vertical_overlap = min(left.bbox[3], right.bbox[3]) - max(
        left.bbox[1], right.bbox[1]
    )
    gap = right.bbox[0] - left.bbox[2]
    return (
        vertical_overlap / min(left_height, right_height) >= 0.55
        and -12.0 <= gap <= 18.0
    )


def _merge_display_pair(
    left: FormulaCandidate,
    right: FormulaCandidate,
) -> FormulaCandidate:
    gap = right.bbox[0] - left.bbox[2]
    separator = " " if gap > 1.0 else ""
    source_text = f"{left.source_text}{separator}{right.source_text}"
    latex_candidate = _join_safe_latex(
        left.latex_candidate,
        right.latex_candidate,
        separator=separator,
    )
    signals = tuple(
        dict.fromkeys((*left.signals, *right.signals, "cross_block_merge"))
    )
    return FormulaCandidate(
        page_number=left.page_number,
        source_lines=tuple(sorted((*left.source_lines, *right.source_lines))),
        bbox=_union_bbox((left.bbox, right.bbox)),
        source_text=source_text,
        normalized_text=" ".join(source_text.split()),
        kind="display",
        confidence=max(left.confidence, right.confidence),
        origin="digital_text_geometry",
        signals=signals,
        latex_candidate=latex_candidate,
    )


def _join_safe_latex(
    left: str | None,
    right: str | None,
    *,
    separator: str,
) -> str | None:
    if left is None or right is None:
        return None
    combined = f"{left}{separator}{right}"
    try:
        return parse_latex_response(f"<latex>{combined}</latex>")
    except LlmBadResponseError:
        return None
