"""V3-G6 multilingual static-reading acceptance tests."""

from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    get_code_project_summary,
    preview_code_context,
    propose_code_change,
)
from researchmind.code.languages import language_for_relative_path
from researchmind.code.parsers import parse_code_symbols
from researchmind.code.python_parser import parse_python_symbols
from researchmind.code.reader import open_code_project
from researchmind.core.code_context import select_code_symbol


SAMPLES = {
    "python": (
        "main.py",
        "import os\n\ndef main(value):\n    return value + 1\n",
        "ast",
        {"import", "function"},
    ),
    "c": (
        "main.c",
        "#include <stdio.h>\ntypedef int Count;\n"
        "int main(void) { return 0; }\n",
        "tree_sitter",
        {"import", "type", "function"},
    ),
    "java": (
        "Main.java",
        "import java.util.List;\nclass Main { "
        "int run() { return 1; } }\n",
        "tree_sitter",
        {"import", "type", "method"},
    ),
    "julia": (
        "main.jl",
        "using LinearAlgebra\nfunction run(x)\n    x + 1\nend\n",
        "tree_sitter",
        {"import", "function"},
    ),
    "r": (
        "main.R",
        "library(ggplot2)\nrun <- function(x) {\n    x + 1\n}\n",
        "lexical",
        {"import", "function"},
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    (
        ("a.py", "python"),
        ("a.c", "c"),
        ("a.h", "c"),
        ("A.java", "java"),
        ("a.jl", "julia"),
        ("a.R", "r"),
        ("README.md", None),
    ),
)
def test_language_mapping_is_extension_bounded(
    relative_path: str,
    expected: str | None,
) -> None:
    assert language_for_relative_path(relative_path) == expected


@pytest.mark.parametrize(
    ("language", "relative_path", "source", "method", "kinds"),
    [
        (language, *sample)
        for language, sample in SAMPLES.items()
    ],
)
def test_each_language_maps_to_project_owned_symbols(
    language: str,
    relative_path: str,
    source: str,
    method: str,
    kinds: set[str],
) -> None:
    symbols, extraction_method = parse_code_symbols(
        language,
        relative_path,
        source,
    )

    assert extraction_method == method
    assert kinds.issubset({symbol.kind for symbol in symbols})
    assert all(symbol.relative_path == relative_path for symbol in symbols)
    assert all(symbol.start_line <= symbol.end_line for symbol in symbols)


def test_python_adapter_preserves_existing_ast_output() -> None:
    relative_path, source, _method, _kinds = SAMPLES["python"]

    symbols, method = parse_code_symbols("python", relative_path, source)

    assert method == "ast"
    assert symbols == parse_python_symbols(relative_path, source)


@pytest.mark.parametrize(
    ("language", "relative_path", "source", "expected_name"),
    (
        ("c", "point.c", "struct Point { int x; };\n", "Point"),
        ("julia", "point.jl", "struct Point\n    x::Float64\nend\n", "Point"),
    ),
)
def test_c_and_julia_type_declarations_are_located(
    language: str,
    relative_path: str,
    source: str,
    expected_name: str,
) -> None:
    symbols, method = parse_code_symbols(language, relative_path, source)

    assert method == "tree_sitter"
    assert any(
        item.kind == "type" and item.name == expected_name
        for item in symbols
    )


@pytest.mark.parametrize(
    ("language", "relative_path", "source"),
    (
        ("c", "bad.c", "int main( {"),
        ("java", "Bad.java", "class Bad { void run( }"),
        ("julia", "bad.jl", "function run(x)\n"),
    ),
)
def test_tree_sitter_incomplete_source_fails_to_text_fallback(
    language: str,
    relative_path: str,
    source: str,
) -> None:
    with pytest.raises(SyntaxError):
        parse_code_symbols(language, relative_path, source)


def test_r_lexical_adapter_ignores_comments_and_strings() -> None:
    source = (
        '# fake <- function(x) { x }\n'
        'text <- "also <- function(x)"\n'
        "real <- function(x) {\n"
        "    stats::median(x)\n"
        "}\n"
    )

    symbols, method = parse_code_symbols("r", "analysis.R", source)

    assert method == "lexical"
    functions = [item.name for item in symbols if item.kind == "function"]
    imports = [item.name for item in symbols if item.kind == "import"]
    assert functions == ["real"]
    assert imports == ["stats"]


def test_mixed_project_is_static_bounded_and_language_aware(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "mixed"
    project_path.mkdir()
    marker = tmp_path / "must-not-exist.txt"
    for _language, (name, source, _method, _kinds) in SAMPLES.items():
        (project_path / name).write_text(source, encoding="utf-8")
    (project_path / "side_effect.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    (project_path / "secrets.java").write_text(
        "class Secret {}\n",
        encoding="utf-8",
    )
    vendor = project_path / "vendor"
    vendor.mkdir()
    (vendor / "ignored.c").write_text("int hidden;\n", encoding="utf-8")

    project = open_code_project(project_path)
    summary = get_code_project_summary(project)

    assert not marker.exists()
    assert "secrets.java" not in {item.relative_path for item in project.files}
    assert "vendor/ignored.c" not in {
        item.relative_path for item in project.files
    }
    assert summary.languages == ("c", "java", "julia", "python", "r")
    assert {item.extraction_method for item in project.files} == {
        "ast",
        "tree_sitter",
        "lexical",
    }

    java_file = next(item for item in project.files if item.language == "java")
    method_index = next(
        index
        for index, symbol in enumerate(java_file.symbols)
        if symbol.kind == "method"
    )
    selection = select_code_symbol(
        project,
        java_file.relative_path,
        symbol_index=method_index,
    )
    preview = preview_code_context(
        project,
        selection,
        question="Explain this method.",
    )
    assert selection.language == "java"
    assert selection.extraction_method == "tree_sitter"
    assert preview.language == "java"

    with pytest.raises(ValueError, match="limited to Python"):
        propose_code_change(
            project,
            selection,
            instruction="Change the return value.",
        )


def test_reader_degrades_invalid_tree_sitter_source_to_text(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "broken"
    project_path.mkdir()
    (project_path / "broken.c").write_text("int main( {", encoding="utf-8")

    project = open_code_project(project_path)
    code_file = project.files[0]

    assert code_file.language == "c"
    assert code_file.status == "syntax_error"
    assert code_file.extraction_method == "text"
    assert code_file.symbols == ()
