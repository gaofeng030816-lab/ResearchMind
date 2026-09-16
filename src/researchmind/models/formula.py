"""Framework-independent models for bounded formula recognition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from researchmind.models.text_block import BoundingBox


FormulaRegionKind = Literal["display", "inline"]
FormulaSourceKind = Literal["digital_text", "embedded_image"]
FormulaExecution = Literal["local", "remote"]
FormulaRecognitionStatus = Literal["recognized", "unreadable"]


@dataclass(frozen=True)
class FormulaRegion:
    """One locally detected, revision-bound region on a PDF page."""

    id: str
    document_id: str
    document_revision: str
    page_number: int
    bbox: BoundingBox
    kind: FormulaRegionKind
    source_kind: FormulaSourceKind
    detector_origin: str
    detector_confidence: float
    signals: tuple[str, ...] = ()
    source_text: str | None = None


@dataclass(frozen=True)
class FormulaCrop:
    """One in-memory PNG crop; bytes and private paths are never persisted."""

    region: FormulaRegion
    png_bytes: bytes = field(repr=False)
    sha256: str
    width_px: int
    height_px: int


@dataclass(frozen=True)
class FormulaRecognitionCandidate:
    """Untrusted recognizer output until accepted by the user."""

    id: str
    region: FormulaRegion
    crop_sha256: str
    recognizer: str
    model_revision: str
    execution: FormulaExecution
    status: FormulaRecognitionStatus
    latex_candidate: str | None
    elapsed_ms: int
    created_at: datetime
    accepted_latex: str | None = None
    accepted_at: datetime | None = None


@dataclass(frozen=True)
class FormulaTransferPreview:
    """Local-only disclosure of the exact crop a recognizer would receive."""

    region_id: str
    crop_sha256: str
    byte_count: int
    width_px: int
    height_px: int
    recognizer: str
    model_revision: str
    execution: FormulaExecution
    will_leave_device: bool
