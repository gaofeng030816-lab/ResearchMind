"""Tests for the read-only local Python project boundary."""

from pathlib import Path

import pytest

from researchmind.code import CodeProjectLimitError, open_code_project


def test_open_code_project_indexes_python_without_executing_it(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "sample-project"
    project_path.mkdir()
    sentinel = tmp_path / "must-not-exist.txt"
    (project_path / "app.py").write_text(
        "import os\n"
        "\n"
        "class Reader:\n"
        "    def read(self, path: str) -> str:\n"
        "        return path\n"
        "\n"
        "def main() -> None:\n"
        f"    open({str(sentinel)!r}, 'w').write('executed')\n",
        encoding="utf-8",
    )
    (project_path / "broken.py").write_text(
        "def incomplete(\n",
        encoding="utf-8",
    )
    (project_path / "latin1.py").write_bytes(b"# caf\xe9\n")
    (project_path / "empty.py").write_text("", encoding="utf-8")
    (project_path / "secrets.py").write_text(
        "API_KEY = 'not-for-indexing'\n",
        encoding="utf-8",
    )
    hidden = project_path / ".hidden"
    hidden.mkdir()
    (hidden / "skip.py").write_text("hidden = True\n", encoding="utf-8")
    virtual_environment = project_path / ".venv"
    virtual_environment.mkdir()
    (virtual_environment / "skip.py").write_text(
        "dependency = True\n",
        encoding="utf-8",
    )

    project = open_code_project(project_path)

    assert [code_file.relative_path for code_file in project.files] == [
        "app.py",
        "broken.py",
        "empty.py",
        "latin1.py",
    ]
    app_file, broken_file, empty_file, latin1_file = project.files
    assert app_file.status == "parsed"
    assert [
        (
            symbol.kind,
            symbol.qualified_name,
            symbol.start_line,
            symbol.end_line,
        )
        for symbol in app_file.symbols
    ] == [
        ("import", "os", 1, 1),
        ("class", "Reader", 3, 5),
        ("method", "Reader.read", 4, 5),
        ("function", "main", 7, 8),
    ]
    assert broken_file.status == "syntax_error"
    assert broken_file.extraction_method == "text"
    assert broken_file.source.splitlines() == ["def incomplete("]
    assert empty_file.status == "parsed"
    assert empty_file.line_count == 0
    assert latin1_file.status == "unreadable"
    assert latin1_file.source == ""
    assert not sentinel.exists()


def test_open_code_project_preserves_relative_path_order_across_folders(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "ordered-project"
    (project_path / "beta").mkdir(parents=True)
    (project_path / "Alpha").mkdir()
    (project_path / "zeta.py").write_text("zeta = 1\n", encoding="utf-8")
    (project_path / "beta" / "two.py").write_text(
        "two = 2\n",
        encoding="utf-8",
    )
    (project_path / "Alpha" / "one.py").write_text(
        "one = 1\n",
        encoding="utf-8",
    )

    project = open_code_project(project_path)

    assert [code_file.relative_path for code_file in project.files] == [
        "Alpha/one.py",
        "beta/two.py",
        "zeta.py",
    ]


@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"max_files": 1}, "file limit"),
        ({"max_total_bytes": 8}, "total source-size limit"),
        ({"max_file_bytes": 8}, "per-file size limit"),
    ),
)
def test_open_code_project_rejects_configured_limits(
    tmp_path: Path,
    kwargs: dict[str, int],
    match: str,
) -> None:
    project_path = tmp_path / "large-project"
    project_path.mkdir()
    (project_path / "one.py").write_text("value = 1\n", encoding="utf-8")
    (project_path / "two.py").write_text("value = 2\n", encoding="utf-8")

    with pytest.raises(CodeProjectLimitError, match=match):
        open_code_project(project_path, **kwargs)
