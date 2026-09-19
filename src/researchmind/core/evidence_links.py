"""Pure rules for explicit, traceable paper-to-code evidence links."""

from __future__ import annotations

from math import isfinite

from researchmind.core.code_context import get_code_file
from researchmind.models import (
    CodeEvidenceReference,
    CodeProject,
    CodeSelection,
    Document,
    EvidenceLink,
    EvidenceRelation,
    PaperEvidenceKind,
    PaperEvidenceReference,
    ReadingSelection,
)
from researchmind.models.text_block import BoundingBox


_EVIDENCE_KINDS: tuple[PaperEvidenceKind, ...] = (
    "paper",
    "mathematics",
    "algorithm",
)
_RELATIONS: tuple[EvidenceRelation, ...] = (
    "implements",
    "explains",
    "supports",
    "contradicts",
    "related",
)


def create_user_confirmed_evidence_link(
    document: Document,
    reading_selection: ReadingSelection,
    code_project: CodeProject,
    code_selection: CodeSelection,
    *,
    evidence_kind: PaperEvidenceKind,
    relation: EvidenceRelation,
    confidence: float,
    rationale: str | None = None,
) -> EvidenceLink:
    """Create one user-confirmed link after validating both source locators."""

    if evidence_kind not in _EVIDENCE_KINDS:
        raise ValueError(
            "Paper evidence kind must be paper, mathematics, or algorithm."
        )
    if relation not in _RELATIONS:
        raise ValueError(
            "Evidence relation must be implements, explains, supports, "
            "contradicts, or related."
        )
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not isfinite(float(confidence))
        or not 0 <= float(confidence) <= 1
    ):
        raise ValueError("Evidence confidence must be between 0 and 1.")

    paper_excerpt = reading_selection.text.strip()
    locator = reading_selection.locator
    if (
        reading_selection.source_type != "pdf"
        or not paper_excerpt
        or locator is None
    ):
        raise ValueError(
            "A located paper selection is required before creating a link."
        )
    page_number = _located_positive_int(locator.get("page_number"))
    if page_number is None or page_number > document.num_pages:
        raise ValueError(
            "A located paper selection is required before creating a link."
        )
    block_index = _located_non_negative_int(locator.get("block_index"))
    bbox = _located_bbox(locator.get("bbox"))

    if code_selection.project_id != code_project.id:
        raise ValueError(
            "The code selection does not belong to the opened code project."
        )
    code_file = get_code_file(code_project, code_selection.relative_path)
    if code_selection.language != code_file.language:
        raise ValueError(
            "The code selection language no longer matches the opened project."
        )
    if code_selection.extraction_method == "text":
        if (
            code_selection.symbol_kind is not None
            or code_selection.symbol_name is not None
        ):
            raise ValueError("A text range cannot claim a parsed code symbol.")
    elif code_selection.extraction_method != code_file.extraction_method:
        raise ValueError("The code selection extraction method is no longer valid.")
    elif not any(
        symbol.start_line == code_selection.start_line
        and symbol.end_line == code_selection.end_line
        and symbol.kind == code_selection.symbol_kind
        and symbol.qualified_name == code_selection.symbol_name
        for symbol in code_file.symbols
    ):
        raise ValueError("The selected code symbol is no longer valid.")
    if (
        code_selection.start_line < 1
        or code_selection.end_line < code_selection.start_line
        or code_selection.end_line > code_file.line_count
    ):
        raise ValueError("The code selection line locator is no longer valid.")
    selected_source = "\n".join(
        code_file.source.splitlines()[
            code_selection.start_line - 1 : code_selection.end_line
        ]
    )
    if not code_selection.text.strip() or selected_source != code_selection.text:
        raise ValueError(
            "The code selection no longer matches the opened code project."
        )

    return EvidenceLink(
        paper=PaperEvidenceReference(
            document_id=document.id,
            document_title=document.title,
            evidence_kind=evidence_kind,
            page_number=page_number,
            block_index=block_index,
            bbox=bbox,
            excerpt=paper_excerpt,
        ),
        code=CodeEvidenceReference(
            project_id=code_project.id,
            project_name=code_project.name,
            relative_path=code_selection.relative_path,
            start_line=code_selection.start_line,
            end_line=code_selection.end_line,
            excerpt=code_selection.text,
            extraction_method=code_selection.extraction_method,
            language=code_selection.language,
            symbol_kind=code_selection.symbol_kind,
            symbol_name=code_selection.symbol_name,
        ),
        relation=relation,
        confidence=float(confidence),
        generation_method="user_confirmed",
        rationale=_optional_text(rationale),
    )


def add_evidence_link(
    existing_links: list[EvidenceLink],
    link: EvidenceLink,
) -> list[EvidenceLink]:
    """Return a copied collection with one non-duplicate claim appended."""

    identity = _link_identity(link)
    if any(_link_identity(existing) == identity for existing in existing_links):
        raise ValueError("This paper-to-code evidence link already exists.")
    return [*existing_links, link]


def _link_identity(link: EvidenceLink) -> tuple[object, ...]:
    return (
        link.paper.document_id,
        link.paper.evidence_kind,
        link.paper.page_number,
        link.paper.block_index,
        link.paper.bbox,
        link.paper.excerpt,
        link.code.project_id,
        link.code.relative_path,
        link.code.start_line,
        link.code.end_line,
        link.code.excerpt,
        link.relation,
        link.generation_method,
    )


def _located_positive_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return None


def _located_non_negative_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _located_bbox(value: object) -> BoundingBox | None:
    if value is None:
        return None
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or not all(
            isinstance(coordinate, (int, float))
            and not isinstance(coordinate, bool)
            and isfinite(float(coordinate))
            for coordinate in value
        )
    ):
        return None
    return tuple(float(coordinate) for coordinate in value)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
