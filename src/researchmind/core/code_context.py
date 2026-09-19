"""Pure selection and bounded-context rules for static code evidence."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath
from sys import stdlib_module_names

from researchmind.core.conversation import APPROXIMATE_CHARS_PER_TOKEN
from researchmind.models import (
    CodeContext,
    CodeFile,
    CodeProject,
    CodeProjectSummary,
    CodeSelection,
)


DEFAULT_SURROUNDING_LINE_RADIUS = 20
_ENTRY_POINT_STEMS = frozenset(
    {
        "app",
        "cli",
        "demo",
        "eval",
        "evaluate",
        "main",
        "run",
        "test",
        "train",
    }
)


def summarize_code_project(project: CodeProject) -> CodeProjectSummary:
    """Summarize an indexed project without reading or executing new files."""

    parsed_files = sum(item.status == "parsed" for item in project.files)
    syntax_error_files = sum(
        item.status == "syntax_error" for item in project.files
    )
    unreadable_files = sum(
        item.status == "unreadable" for item in project.files
    )
    symbols = tuple(
        symbol
        for code_file in project.files
        for symbol in code_file.symbols
    )
    imported_modules = _sorted_unique(
        module
        for symbol in symbols
        if symbol.kind == "import"
        if (module := _import_root(symbol.name))
    )
    local_modules = _local_module_roots(project)
    external_candidates = tuple(
        module
        for module in imported_modules
        if not module.startswith(".")
        and module not in stdlib_module_names
        and module.casefold() not in local_modules
    )
    entry_points = _sorted_unique(
        code_file.relative_path
        for code_file in project.files
        if _is_entry_point_candidate(code_file)
    )
    problem_files = _sorted_unique(
        code_file.relative_path
        for code_file in project.files
        if code_file.status != "parsed"
    )
    return CodeProjectSummary(
        project_name=project.name,
        total_files=len(project.files),
        parsed_files=parsed_files,
        syntax_error_files=syntax_error_files,
        unreadable_files=unreadable_files,
        languages=tuple(sorted({item.language for item in project.files})),
        total_lines=sum(item.line_count for item in project.files),
        definition_count=sum(
            symbol.kind in {"class", "type", "function", "method"}
            for symbol in symbols
        ),
        import_count=sum(symbol.kind == "import" for symbol in symbols),
        entry_point_candidates=entry_points,
        imported_modules=imported_modules,
        external_dependency_candidates=external_candidates,
        problem_files=problem_files,
    )


def select_code_symbol(
    project: CodeProject,
    relative_path: str,
    *,
    symbol_index: int,
) -> CodeSelection:
    """Select exactly one statically located symbol from an indexed file."""

    code_file = _required_code_file(project, relative_path)
    if symbol_index < 0 or symbol_index >= len(code_file.symbols):
        raise ValueError(
            f"Symbol index must be between 0 and {len(code_file.symbols) - 1}."
        )
    symbol = code_file.symbols[symbol_index]
    text = _selected_lines(
        code_file,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
    )
    return CodeSelection(
        project_id=project.id,
        project_name=project.name,
        relative_path=code_file.relative_path,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        text=text,
        extraction_method=code_file.extraction_method,
        language=code_file.language,
        symbol_kind=symbol.kind,
        symbol_name=symbol.qualified_name,
    )


def select_code_lines(
    project: CodeProject,
    relative_path: str,
    *,
    start_line: int,
    end_line: int,
) -> CodeSelection:
    """Select an explicit inclusive line range without parsing or execution."""

    code_file = _required_code_file(project, relative_path)
    text = _selected_lines(
        code_file,
        start_line=start_line,
        end_line=end_line,
    )
    return CodeSelection(
        project_id=project.id,
        project_name=project.name,
        relative_path=code_file.relative_path,
        start_line=start_line,
        end_line=end_line,
        text=text,
        extraction_method="text",
        language=code_file.language,
    )


def build_code_context(
    selection: CodeSelection,
    code_file: CodeFile,
    *,
    user_question: str,
    context_token_budget: int,
    surrounding_line_radius: int = DEFAULT_SURROUNDING_LINE_RADIUS,
) -> CodeContext:
    """Assemble selected code plus only the nearest lines that fit the budget."""

    if selection.relative_path != code_file.relative_path:
        raise ValueError("Code selection does not belong to the supplied file.")
    question = user_question.strip()
    if not question:
        raise ValueError("Code explanation question must not be blank.")
    if context_token_budget <= 0:
        raise ValueError("Code context token budget must be positive.")
    if surrounding_line_radius < 0:
        raise ValueError("Surrounding line radius must not be negative.")

    max_characters = context_token_budget * APPROXIMATE_CHARS_PER_TOKEN
    if len(selection.text) > max_characters:
        raise ValueError(
            "Selected code exceeds the context budget; choose a smaller line range."
        )
    surrounding_code = _nearest_surrounding_lines(
        code_file,
        selection,
        max_characters=max_characters - len(selection.text),
        radius=surrounding_line_radius,
    )
    return CodeContext(
        selection=selection,
        project_name=selection.project_name,
        relative_path=selection.relative_path,
        start_line=selection.start_line,
        end_line=selection.end_line,
        selected_code=selection.text,
        surrounding_code=surrounding_code,
        extraction_method=selection.extraction_method,
        user_question=question,
        symbol_kind=selection.symbol_kind,
        symbol_name=selection.symbol_name,
        language=selection.language,
    )


def get_code_file(project: CodeProject, relative_path: str) -> CodeFile:
    """Return one indexed file by its normalized relative path."""

    return _required_code_file(project, relative_path)


def _import_root(name: str) -> str:
    relative_level = len(name) - len(name.lstrip("."))
    normalized = name.lstrip(".")
    if not normalized:
        return ""
    root = normalized.split(".", maxsplit=1)[0]
    return f"{'.' * relative_level}{root}"


def _local_module_roots(project: CodeProject) -> set[str]:
    roots: set[str] = set()
    for code_file in project.files:
        path = PurePosixPath(code_file.relative_path)
        if len(path.parts) > 1:
            roots.add(path.parts[0].casefold())
        elif path.stem != "__init__":
            roots.add(path.stem.casefold())
    return roots


def _is_entry_point_candidate(code_file: CodeFile) -> bool:
    if code_file.status != "parsed":
        return False
    path = PurePosixPath(code_file.relative_path)
    if path.stem.casefold() in _ENTRY_POINT_STEMS:
        return True
    return any(
        symbol.kind == "function"
        and symbol.parent_name is None
        and symbol.name.casefold() == "main"
        for symbol in code_file.symbols
    )


def _sorted_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(values),
            key=lambda value: value.casefold(),
        )
    )


def _required_code_file(
    project: CodeProject,
    relative_path: str,
) -> CodeFile:
    normalized = relative_path.replace("\\", "/")
    code_file = next(
        (
            item
            for item in project.files
            if item.relative_path == normalized
        ),
        None,
    )
    if code_file is None:
        raise ValueError(f"Code file is not part of this project: {normalized}")
    if not code_file.source:
        raise ValueError(
            f"Code file is unavailable for selection: {normalized}"
        )
    return code_file


def _selected_lines(
    code_file: CodeFile,
    *,
    start_line: int,
    end_line: int,
) -> str:
    if start_line < 1 or start_line > code_file.line_count:
        raise ValueError(
            f"Start line must be between 1 and {code_file.line_count}."
        )
    if end_line < 1 or end_line > code_file.line_count:
        raise ValueError(
            f"End line must be between 1 and {code_file.line_count}."
        )
    if start_line > end_line:
        raise ValueError("Start line must not be after end line.")
    return "\n".join(code_file.source.splitlines()[start_line - 1 : end_line])


def _nearest_surrounding_lines(
    code_file: CodeFile,
    selection: CodeSelection,
    *,
    max_characters: int,
    radius: int,
) -> str:
    if max_characters <= 0 or radius == 0:
        return ""
    lines = code_file.source.splitlines()
    selected_lines: dict[int, str] = {}
    used_characters = 0
    for distance in range(1, radius + 1):
        candidate_numbers = (
            selection.start_line - distance,
            selection.end_line + distance,
        )
        for line_number in candidate_numbers:
            if line_number < 1 or line_number > len(lines):
                continue
            rendered = f"{line_number}: {lines[line_number - 1]}"
            separator_cost = 1 if selected_lines else 0
            if used_characters + len(rendered) + separator_cost > max_characters:
                continue
            selected_lines[line_number] = rendered
            used_characters += len(rendered) + separator_cost
    return "\n".join(
        selected_lines[line_number]
        for line_number in sorted(selected_lines)
    )
