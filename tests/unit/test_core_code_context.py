"""Tests for pure code selection and bounded CodeContext assembly."""

import pytest

from researchmind.core import (
    build_code_context,
    select_code_lines,
    select_code_symbol,
)
from researchmind.models import CodeFile, CodeProject, CodeSymbol


def test_symbol_and_line_selection_preserve_code_provenance() -> None:
    code_file = _code_file()
    project = _project(code_file)

    symbol_selection = select_code_symbol(project, "module.py", symbol_index=0)
    line_selection = select_code_lines(
        project,
        "module.py",
        start_line=4,
        end_line=5,
    )

    assert symbol_selection.relative_path == "module.py"
    assert symbol_selection.start_line == 2
    assert symbol_selection.end_line == 3
    assert symbol_selection.symbol_kind == "function"
    assert symbol_selection.symbol_name == "add"
    assert symbol_selection.extraction_method == "ast"
    assert symbol_selection.text == "def add(a, b):\n    return a + b"
    assert line_selection.symbol_kind is None
    assert line_selection.extraction_method == "text"
    assert line_selection.text == "\nresult = add(1, 2)"


def test_code_context_is_bounded_and_rejects_an_oversized_selection() -> None:
    code_file = _code_file()
    project = _project(code_file)
    selection = select_code_symbol(project, "module.py", symbol_index=0)

    context = build_code_context(
        selection,
        code_file,
        user_question="Why is this helper pure?",
        context_token_budget=20,
    )

    assert context.project_name == "sample"
    assert context.relative_path == "module.py"
    assert context.selected_code == selection.text
    assert len(context.selected_code) + len(context.surrounding_code) <= 80

    whole_file = select_code_lines(
        project,
        "module.py",
        start_line=1,
        end_line=5,
    )
    with pytest.raises(ValueError, match="smaller line range"):
        build_code_context(
            whole_file,
            code_file,
            user_question="Explain this.",
            context_token_budget=4,
        )


def test_code_line_selection_validates_the_requested_range() -> None:
    project = _project(_code_file())

    with pytest.raises(ValueError, match="between 1 and 5"):
        select_code_lines(
            project,
            "module.py",
            start_line=0,
            end_line=2,
        )
    with pytest.raises(ValueError, match="must not be after"):
        select_code_lines(
            project,
            "module.py",
            start_line=4,
            end_line=2,
        )


def _code_file() -> CodeFile:
    return CodeFile(
        relative_path="module.py",
        source="import math\ndef add(a, b):\n    return a + b\n\nresult = add(1, 2)\n",
        size_bytes=65,
        line_count=5,
        status="parsed",
        extraction_method="ast",
        symbols=(
            CodeSymbol(
                relative_path="module.py",
                name="add",
                qualified_name="add",
                kind="function",
                start_line=2,
                end_line=3,
            ),
        ),
    )


def _project(code_file: CodeFile) -> CodeProject:
    return CodeProject(
        id="project-1",
        name="sample",
        root_path="/private/sample",
        files=(code_file,),
        total_source_bytes=code_file.size_bytes,
    )
