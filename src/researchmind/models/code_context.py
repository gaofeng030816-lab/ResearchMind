"""Project-owned models for static local code evidence."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from researchmind.models.code_selection import (
    CodeExtractionMethod,
    CodeLanguage,
    CodeSelection,
    CodeSymbolKind,
)


CodeFileStatus = Literal["parsed", "syntax_error", "unreadable"]


@dataclass(frozen=True)
class CodeSymbol:
    """One statically located source symbol."""

    relative_path: str
    name: str
    qualified_name: str
    kind: CodeSymbolKind
    start_line: int
    end_line: int
    parent_name: str | None = None


@dataclass(frozen=True)
class CodeFile:
    """One bounded source file converted at the code-reader boundary."""

    relative_path: str
    source: str
    size_bytes: int
    line_count: int
    status: CodeFileStatus
    extraction_method: CodeExtractionMethod
    language: CodeLanguage = "python"
    symbols: tuple[CodeSymbol, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class CodeProject:
    """One explicitly opened local folder held only in session memory."""

    id: str
    name: str
    root_path: Path
    files: tuple[CodeFile, ...]
    total_source_bytes: int
    managed_by_researchmind: bool = False


@dataclass(frozen=True)
class CodeProjectSummary:
    """Deterministic, path-safe overview for learning and reproduction."""

    project_name: str
    total_files: int
    parsed_files: int
    syntax_error_files: int
    unreadable_files: int
    total_lines: int
    definition_count: int
    import_count: int
    entry_point_candidates: tuple[str, ...] = ()
    imported_modules: tuple[str, ...] = ()
    languages: tuple[CodeLanguage, ...] = ()
    external_dependency_candidates: tuple[str, ...] = ()
    problem_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodeContext:
    """Bounded code evidence for one explicit explanation request."""

    selection: CodeSelection
    project_name: str
    relative_path: str
    start_line: int
    end_line: int
    selected_code: str
    surrounding_code: str
    extraction_method: CodeExtractionMethod
    user_question: str
    symbol_kind: CodeSymbolKind | None = None
    symbol_name: str | None = None
    language: CodeLanguage = "python"
    source: Literal["code"] = "code"
