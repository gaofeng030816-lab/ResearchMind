"""Dispatch project-owned static parsers without source execution."""

from researchmind.code.python_parser import parse_python_symbols
from researchmind.code.r_parser import parse_r_symbols
from researchmind.code.tree_sitter_parser import parse_tree_sitter_symbols
from researchmind.models import CodeExtractionMethod, CodeLanguage, CodeSymbol


def parse_code_symbols(
    language: CodeLanguage,
    relative_path: str,
    source: str,
) -> tuple[tuple[CodeSymbol, ...], CodeExtractionMethod]:
    """Return normalized symbols and the extraction method used."""

    if language == "python":
        return parse_python_symbols(relative_path, source), "ast"
    if language == "r":
        return parse_r_symbols(relative_path, source), "lexical"
    return (
        parse_tree_sitter_symbols(language, relative_path, source),
        "tree_sitter",
    )
