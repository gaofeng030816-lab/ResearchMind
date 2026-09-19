"""Traceable links between paper evidence and static code evidence."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from researchmind.models.code_selection import (
    CodeExtractionMethod,
    CodeLanguage,
    CodeSymbolKind,
)
from researchmind.models.text_block import BoundingBox


PaperEvidenceKind = Literal["paper", "mathematics", "algorithm"]
EvidenceRelation = Literal[
    "implements",
    "explains",
    "supports",
    "contradicts",
    "related",
]
EvidenceGenerationMethod = Literal[
    "user_confirmed",
    "deterministic",
    "model_inference",
]


@dataclass(frozen=True)
class PaperEvidenceReference:
    """One located paper or mathematical excerpt."""

    document_id: str
    document_title: str
    evidence_kind: PaperEvidenceKind
    page_number: int
    excerpt: str
    block_index: int | None = None
    bbox: BoundingBox | None = None
    source_type: Literal["pdf"] = "pdf"


@dataclass(frozen=True)
class CodeEvidenceReference:
    """One static code excerpt with project-relative provenance."""

    project_id: str
    project_name: str
    relative_path: str
    start_line: int
    end_line: int
    excerpt: str
    extraction_method: CodeExtractionMethod
    symbol_kind: CodeSymbolKind | None = None
    symbol_name: str | None = None
    language: CodeLanguage = "python"
    source_type: Literal["code"] = "code"


@dataclass(frozen=True)
class EvidenceLink:
    """An explicit claim relating one paper reference to one code reference."""

    paper: PaperEvidenceReference
    code: CodeEvidenceReference
    relation: EvidenceRelation
    confidence: float
    generation_method: EvidenceGenerationMethod
    rationale: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: str = field(default_factory=lambda: uuid4().hex)
