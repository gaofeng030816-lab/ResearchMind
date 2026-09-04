"""Block-level text search over an extracted PDF document."""

from __future__ import annotations

from dataclasses import dataclass
import re

from researchmind.pdf.reader import OpenedDocument


DEFAULT_EXCERPT_CHARS = 180


@dataclass(frozen=True)
class TextMatch:
    """A search hit tied to one page and extracted text block."""

    page_number: int
    block_index: int
    excerpt: str


def search_text(
    opened_document: OpenedDocument,
    query: str,
    *,
    excerpt_chars: int = DEFAULT_EXCERPT_CHARS,
) -> list[TextMatch]:
    """Return one ordered match for each text block containing ``query``."""

    normalized_query = _normalize_whitespace(query)
    if not normalized_query:
        return []
    if excerpt_chars <= 0:
        raise ValueError("excerpt_chars must be greater than zero.")

    pattern = re.compile(re.escape(normalized_query), flags=re.IGNORECASE)
    matches: list[TextMatch] = []

    for page in opened_document.pages:
        for block in page.blocks:
            searchable_text = _normalize_whitespace(block.text)
            match = pattern.search(searchable_text)
            if match is None:
                continue
            matches.append(
                TextMatch(
                    page_number=page.page_number,
                    block_index=block.block_index,
                    excerpt=_build_excerpt(
                        searchable_text,
                        match.start(),
                        match.end(),
                        excerpt_chars,
                    ),
                )
            )

    return matches


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _build_excerpt(
    text: str,
    match_start: int,
    match_end: int,
    excerpt_chars: int,
) -> str:
    if len(text) <= excerpt_chars:
        return text

    match_length = match_end - match_start
    remaining = max(excerpt_chars - match_length, 0)
    start = max(match_start - remaining // 2, 0)
    end = min(start + excerpt_chars, len(text))
    start = max(end - excerpt_chars, 0)

    excerpt = text[start:end]
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt += "..."
    return excerpt
