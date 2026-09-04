"""Traceable, read-only selection from a local code project."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4


CodeExtractionMethod = Literal["ast", "text"]
CodeSymbolKind = Literal["class", "function", "method", "import"]


@dataclass(frozen=True)
class CodeSelection:
    """User-confirmed code and the exact local provenance that produced it."""

    project_id: str
    project_name: str
    relative_path: str
    start_line: int
    end_line: int
    text: str
    extraction_method: CodeExtractionMethod
    symbol_kind: CodeSymbolKind | None = None
    symbol_name: str | None = None
    source_type: Literal["code"] = "code"
    id: str = field(default_factory=lambda: uuid4().hex)
