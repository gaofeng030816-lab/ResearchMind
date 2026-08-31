"""Pure proposal-building tests for T5-B1 code replacement."""

from dataclasses import replace
from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    create_code_line_selection,
    open_code_project,
)
from researchmind.code import read_code_snapshot
from researchmind.core.code_changes import (
    MAX_CHANGED_LINES,
    build_code_change_proposal,
    replace_code_project_file,
    validate_code_change_snapshot,
)


def test_build_proposal_splices_only_selection_and_shows_path_safe_diff(
    tmp_path: Path,
) -> None:
    root = tmp_path / "private-project"
    root.mkdir()
    source_path = root / "model.py"
    source_path.write_text(
        "HEADER = 1\n"
        "def normalize(value: float) -> float:\n"
        "    return value / 10\n"
        "FOOTER = 2\n",
        encoding="utf-8",
    )
    project = open_code_project(root)
    selection = create_code_line_selection(
        project,
        "model.py",
        start_line=2,
        end_line=3,
    )
    snapshot = read_code_snapshot(project, "model.py")

    proposal = build_code_change_proposal(
        project,
        selection,
        snapshot,
        replacement_text=(
            "def normalize(value: float) -> float:\n"
            "    return value / 100.0"
        ),
    )

    assert proposal.relative_path == "model.py"
    assert proposal.candidate_source.splitlines() == [
        "HEADER = 1",
        "def normalize(value: float) -> float:",
        "    return value / 100.0",
        "FOOTER = 2",
    ]
    assert proposal.candidate_source.endswith(("\n", "\r"))
    assert "--- a/model.py" in proposal.unified_diff
    assert "+++ b/model.py" in proposal.unified_diff
    assert str(root) not in proposal.unified_diff
    assert proposal.syntax_valid is True
    assert proposal.changed_line_count == 2


def test_proposal_rejects_stale_selection_and_invalid_python(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "model.py").write_text("value = 1\n", encoding="utf-8")
    project = open_code_project(root)
    selection = create_code_line_selection(
        project,
        "model.py",
        start_line=1,
        end_line=1,
    )
    snapshot = read_code_snapshot(project, "model.py")

    with pytest.raises(ValueError, match="changed since it was indexed"):
        validate_code_change_snapshot(
            project,
            selection,
            replace(snapshot, source="value = 9\n"),
        )

    with pytest.raises(ValueError, match="valid Python syntax"):
        build_code_change_proposal(
            project,
            selection,
            snapshot,
            replacement_text="def broken(",
        )


def test_proposal_rejects_more_than_changed_line_budget(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    original = "\n".join(f"value_{index} = {index}" for index in range(201))
    (root / "many.py").write_text(original + "\n", encoding="utf-8")
    project = open_code_project(root)
    selection = create_code_line_selection(
        project,
        "many.py",
        start_line=1,
        end_line=201,
    )
    snapshot = read_code_snapshot(project, "many.py")
    replacement = "\n".join(
        f"changed_{index} = {index}" for index in range(201)
    )

    with pytest.raises(ValueError, match=str(MAX_CHANGED_LINES)):
        build_code_change_proposal(
            project,
            selection,
            snapshot,
            replacement_text=replacement,
        )


def test_replace_code_project_file_updates_only_one_indexed_file(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "one.py").write_text("value = 1\n", encoding="utf-8")
    (root / "two.py").write_text("other = 2\n", encoding="utf-8")
    project = open_code_project(root)
    updated = replace(project.files[0], source="value = 10\n", size_bytes=11)

    refreshed = replace_code_project_file(project, updated)

    assert refreshed.id == project.id
    assert refreshed.files[0].source == "value = 10\n"
    assert refreshed.files[1] == project.files[1]
    assert refreshed.total_source_bytes == (
        project.total_source_bytes - project.files[0].size_bytes + 11
    )
