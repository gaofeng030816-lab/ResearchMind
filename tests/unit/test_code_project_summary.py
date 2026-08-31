"""T6-A pure project-overview tests for learning and reproduction."""

from pathlib import Path

from researchmind.core import summarize_code_project
from researchmind.models import CodeFile, CodeProject, CodeSymbol


def test_code_project_summary_reports_structure_and_reproduction_clues() -> None:
    project = CodeProject(
        id="project-1",
        name="paper-implementation",
        root_path=Path("D:/private/paper-implementation"),
        files=(
            CodeFile(
                relative_path="train.py",
                source=(
                    "import os\n"
                    "import numpy as np\n"
                    "from package.model import Solver\n"
                    "def main():\n"
                    "    return Solver()\n"
                ),
                size_bytes=100,
                line_count=5,
                status="parsed",
                extraction_method="ast",
                symbols=(
                    CodeSymbol(
                        relative_path="train.py",
                        name="os",
                        qualified_name="os",
                        kind="import",
                        start_line=1,
                        end_line=1,
                    ),
                    CodeSymbol(
                        relative_path="train.py",
                        name="numpy",
                        qualified_name="numpy",
                        kind="import",
                        start_line=2,
                        end_line=2,
                    ),
                    CodeSymbol(
                        relative_path="train.py",
                        name="package.model.Solver",
                        qualified_name="package.model.Solver",
                        kind="import",
                        start_line=3,
                        end_line=3,
                    ),
                    CodeSymbol(
                        relative_path="train.py",
                        name="main",
                        qualified_name="main",
                        kind="function",
                        start_line=4,
                        end_line=5,
                    ),
                ),
            ),
            CodeFile(
                relative_path="package/model.py",
                source="class Solver:\n    pass\n",
                size_bytes=30,
                line_count=2,
                status="parsed",
                extraction_method="ast",
                symbols=(
                    CodeSymbol(
                        relative_path="package/model.py",
                        name="Solver",
                        qualified_name="Solver",
                        kind="class",
                        start_line=1,
                        end_line=2,
                    ),
                ),
            ),
            CodeFile(
                relative_path="broken.py",
                source="def broken(:\n",
                size_bytes=13,
                line_count=1,
                status="syntax_error",
                extraction_method="text",
                error="Python syntax error at line 1.",
            ),
        ),
        total_source_bytes=143,
    )

    summary = summarize_code_project(project)

    assert summary.project_name == "paper-implementation"
    assert summary.total_files == 3
    assert summary.parsed_files == 2
    assert summary.syntax_error_files == 1
    assert summary.unreadable_files == 0
    assert summary.total_lines == 8
    assert summary.definition_count == 2
    assert summary.import_count == 3
    assert summary.entry_point_candidates == ("train.py",)
    assert summary.imported_modules == ("numpy", "os", "package")
    assert summary.external_dependency_candidates == ("numpy",)
    assert summary.problem_files == ("broken.py",)
    assert "D:/private" not in repr(summary)


def test_code_project_summary_is_stable_when_project_is_empty() -> None:
    project = CodeProject(
        id="empty",
        name="empty-project",
        root_path=Path("D:/private/empty-project"),
        files=(),
        total_source_bytes=0,
    )

    summary = summarize_code_project(project)

    assert summary.total_files == 0
    assert summary.total_lines == 0
    assert summary.entry_point_candidates == ()
    assert summary.external_dependency_candidates == ()
    assert summary.problem_files == ()


def test_code_project_summary_does_not_label_relative_import_as_external() -> None:
    project = CodeProject(
        id="relative-import",
        name="package-project",
        root_path=Path("D:/private/package-project"),
        files=(
            CodeFile(
                relative_path="package/main.py",
                source="from .helpers import build\n",
                size_bytes=27,
                line_count=1,
                status="parsed",
                extraction_method="ast",
                symbols=(
                    CodeSymbol(
                        relative_path="package/main.py",
                        name=".helpers.build",
                        qualified_name=".helpers.build",
                        kind="import",
                        start_line=1,
                        end_line=1,
                    ),
                ),
            ),
            CodeFile(
                relative_path="package/helpers.py",
                source="def build():\n    return 1\n",
                size_bytes=26,
                line_count=2,
                status="parsed",
                extraction_method="ast",
            ),
        ),
        total_source_bytes=53,
    )

    summary = summarize_code_project(project)

    assert summary.imported_modules == (".helpers",)
    assert summary.external_dependency_candidates == ()
