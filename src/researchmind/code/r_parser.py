"""Conservative non-executing R symbol extraction."""

from __future__ import annotations

import re

from researchmind.models import CodeSymbol


_FUNCTION_RE = re.compile(
    r"(?m)^[ \t]*([A-Za-z.][A-Za-z0-9._]*)[ \t]*(?:<-|<<-|=)[ \t]*function[ \t]*\("
)
_IMPORT_RE = re.compile(
    r'''(?m)^[ \t]*(?:library|require)[ \t]*\([ \t]*'''
    r'''(?:["']([^"']+)["']|([A-Za-z.][A-Za-z0-9._]*))'''
)
_NAMESPACE_RE = re.compile(
    r"\b([A-Za-z.][A-Za-z0-9._]*):::{0,1}[A-Za-z.][A-Za-z0-9._]*"
)


def parse_r_symbols(relative_path: str, source: str) -> tuple[CodeSymbol, ...]:
    """Locate common R functions and imports without evaluating source."""

    masked = _mask_strings_and_comments(source)
    symbols: list[CodeSymbol] = []
    for match in _FUNCTION_RE.finditer(masked):
        name = match.group(1)
        start_line = _line_number(masked, match.start())
        end_line = _function_end_line(masked, match.end(), start_line)
        symbols.append(
            CodeSymbol(
                relative_path=relative_path,
                name=name,
                qualified_name=name,
                kind="function",
                start_line=start_line,
                end_line=end_line,
            )
        )

    for match in _IMPORT_RE.finditer(source):
        name = match.group(1) or match.group(2)
        symbols.append(
            CodeSymbol(
                relative_path=relative_path,
                name=name,
                qualified_name=name,
                kind="import",
                start_line=_line_number(source, match.start()),
                end_line=_line_number(source, match.end()),
            )
        )

    for match in _NAMESPACE_RE.finditer(masked):
        name = match.group(1)
        symbols.append(
            CodeSymbol(
                relative_path=relative_path,
                name=name,
                qualified_name=name,
                kind="import",
                start_line=_line_number(masked, match.start()),
                end_line=_line_number(masked, match.end()),
            )
        )
    return _deduplicated(symbols)


def _mask_strings_and_comments(source: str) -> str:
    characters = list(source)
    quote: str | None = None
    escaped = False
    in_comment = False
    for index, character in enumerate(source):
        if in_comment:
            if character == "\n":
                in_comment = False
            else:
                characters[index] = " "
            continue
        if quote is not None:
            if character == "\n":
                quote = None
                escaped = False
                continue
            characters[index] = " "
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            characters[index] = " "
        elif character == "#":
            in_comment = True
            characters[index] = " "
    return "".join(characters)


def _function_end_line(masked: str, search_start: int, start_line: int) -> int:
    body_start = masked.find("{", search_start)
    line_end = masked.find("\n", search_start)
    if body_start < 0 or (line_end >= 0 and body_start > line_end):
        return start_line
    depth = 0
    for index in range(body_start, len(masked)):
        if masked[index] == "{":
            depth += 1
        elif masked[index] == "}":
            depth -= 1
            if depth == 0:
                return _line_number(masked, index + 1)
    return len(masked.splitlines()) or 1


def _line_number(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _deduplicated(symbols: list[CodeSymbol]) -> tuple[CodeSymbol, ...]:
    unique = {
        (item.kind, item.name, item.start_line, item.end_line): item
        for item in symbols
    }
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.start_line, item.end_line, item.kind, item.name),
        )
    )
