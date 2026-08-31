"""Tests for explicit paper-to-code evidence links."""

from pathlib import Path

import pytest

from researchmind.core import (
    add_evidence_link,
    create_user_confirmed_evidence_link,
    select_code_symbol,
)
from researchmind.models import (
    CodeFile,
    CodeProject,
    CodeSymbol,
    Document,
    ReadingSelection,
)


def test_user_confirmed_link_preserves_both_endpoints_and_provenance() -> None:
    document = _document()
    project = _project()
    code_selection = select_code_symbol(
        project,
        "solver.py",
        symbol_index=0,
    )
    reading_selection = ReadingSelection(
        text="The update follows Equation 3.",
        locator={
            "page_number": 4,
            "block_index": 7,
            "bbox": (10.0, 20.0, 200.0, 45.0),
        },
    )

    link = create_user_confirmed_evidence_link(
        document,
        reading_selection,
        project,
        code_selection,
        evidence_kind="mathematics",
        relation="implements",
        confidence=0.85,
        rationale="The variable names and update order match.",
    )

    assert link.paper.document_id == "paper-1"
    assert link.paper.document_title == "Optimization Paper"
    assert link.paper.evidence_kind == "mathematics"
    assert link.paper.page_number == 4
    assert link.paper.block_index == 7
    assert link.paper.bbox == (10.0, 20.0, 200.0, 45.0)
    assert link.paper.excerpt == "The update follows Equation 3."
    assert link.code.project_id == "project-1"
    assert link.code.relative_path == "solver.py"
    assert link.code.start_line == 1
    assert link.code.end_line == 2
    assert link.code.symbol_kind == "function"
    assert link.code.symbol_name == "step"
    assert link.code.extraction_method == "ast"
    assert link.relation == "implements"
    assert link.confidence == 0.85
    assert link.generation_method == "user_confirmed"
    assert link.rationale == "The variable names and update order match."


def test_evidence_link_requires_located_paper_selection_and_matching_code() -> None:
    document = _document()
    project = _project()
    code_selection = select_code_symbol(
        project,
        "solver.py",
        symbol_index=0,
    )

    with pytest.raises(ValueError, match="located paper selection"):
        create_user_confirmed_evidence_link(
            document,
            ReadingSelection(text="Unlocated text"),
            project,
            code_selection,
            evidence_kind="paper",
            relation="related",
            confidence=0.5,
        )

    with pytest.raises(ValueError, match="code project"):
        create_user_confirmed_evidence_link(
            document,
            ReadingSelection(
                text="Located text",
                locator={"page_number": 1},
            ),
            CodeProject(
                id="other-project",
                name=project.name,
                root_path=project.root_path,
                files=project.files,
                total_source_bytes=project.total_source_bytes,
            ),
            code_selection,
            evidence_kind="paper",
            relation="related",
            confidence=0.5,
        )


def test_user_confirmed_link_accepts_algorithm_evidence() -> None:
    project = _project()

    link = create_user_confirmed_evidence_link(
        _document(),
        ReadingSelection(
            text="Algorithm 1 applies this update until convergence.",
            locator={"page_number": 5},
        ),
        project,
        select_code_symbol(project, "solver.py", symbol_index=0),
        evidence_kind="algorithm",
        relation="implements",
        confidence=0.75,
    )

    assert link.paper.evidence_kind == "algorithm"


@pytest.mark.parametrize("confidence", (-0.01, 1.01, float("nan")))
def test_evidence_link_rejects_invalid_confidence(confidence: float) -> None:
    project = _project()

    with pytest.raises(ValueError, match="between 0 and 1"):
        create_user_confirmed_evidence_link(
            _document(),
            ReadingSelection(
                text="Located text",
                locator={"page_number": 1},
            ),
            project,
            select_code_symbol(project, "solver.py", symbol_index=0),
            evidence_kind="paper",
            relation="supports",
            confidence=confidence,
        )


def test_evidence_link_collection_rejects_duplicate_claims() -> None:
    project = _project()
    arguments = (
        _document(),
        ReadingSelection(
            text="Located text",
            locator={"page_number": 1},
        ),
        project,
        select_code_symbol(project, "solver.py", symbol_index=0),
    )
    first = create_user_confirmed_evidence_link(
        *arguments,
        evidence_kind="paper",
        relation="related",
        confidence=0.7,
    )
    duplicate = create_user_confirmed_evidence_link(
        *arguments,
        evidence_kind="paper",
        relation="related",
        confidence=0.9,
    )

    assert add_evidence_link([], first) == [first]
    with pytest.raises(ValueError, match="already exists"):
        add_evidence_link([first], duplicate)


def _document() -> Document:
    return Document(
        id="paper-1",
        title="Optimization Paper",
        authors=["Ada Researcher"],
        source_type="pdf",
        path=Path("paper.pdf"),
        num_pages=8,
    )


def _project() -> CodeProject:
    source = "def step(x):\n    return x + 1\n"
    code_file = CodeFile(
        relative_path="solver.py",
        source=source,
        size_bytes=len(source.encode("utf-8")),
        line_count=2,
        status="parsed",
        extraction_method="ast",
        symbols=(
            CodeSymbol(
                relative_path="solver.py",
                name="step",
                qualified_name="step",
                kind="function",
                start_line=1,
                end_line=2,
            ),
        ),
    )
    return CodeProject(
        id="project-1",
        name="optimizer",
        root_path=Path("private/optimizer"),
        files=(code_file,),
        total_source_bytes=code_file.size_bytes,
    )
