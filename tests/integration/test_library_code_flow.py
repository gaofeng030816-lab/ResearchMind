"""Integration coverage for V3-G1 managed Python-directory imports."""

from pathlib import Path

import pytest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.database import LibraryImportError
from researchmind.models import UploadedFileData


def test_code_directory_import_filters_sensitive_files_and_reopens(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    uploads = [
        UploadedFileData(
            name="demo/main.py",
            content=b"from pkg.helper import answer\nprint(answer())\n",
        ),
        UploadedFileData(
            name="demo/pkg/helper.py",
            content=b"def answer():\n    return 42\n",
        ),
        UploadedFileData(
            name="demo/.venv/ignored.py",
            content=b"SECRET = 'ignored'\n",
        ),
        UploadedFileData(
            name="demo/secrets.py",
            content=b"API_KEY = 'ignored'\n",
        ),
    ]

    imported = use_cases.import_code_directory_to_library(
        uploads,
        settings=settings,
    )
    reopened = use_cases.open_library_code_project(
        imported.entry.record.id,
        settings=settings,
    )

    assert imported.entry.record.title == "demo"
    assert imported.entry.asset.kind == "code_directory"
    assert reopened.id == imported.entry.record.id
    assert reopened.name == "demo"
    assert reopened.managed_by_researchmind is True
    assert [code_file.relative_path for code_file in reopened.files] == [
        "main.py",
        "pkg/helper.py",
    ]
    assert not (reopened.root_path / ".venv").exists()
    assert not (reopened.root_path / "secrets.py").exists()


def test_code_directory_hash_is_order_independent_and_supports_revision(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    uploads = [
        UploadedFileData(name="demo/b.py", content=b"value = 2\n"),
        UploadedFileData(name="demo/a.py", content=b"value = 1\n"),
    ]
    imported = use_cases.import_code_directory_to_library(
        uploads,
        settings=settings,
    )

    duplicate = use_cases.import_code_directory_to_library(
        list(reversed(uploads)),
        project_name="A different label does not alter content identity",
        settings=settings,
    )
    revision = use_cases.import_code_directory_to_library(
        [
            UploadedFileData(name="demo/a.py", content=b"value = 1\n"),
            UploadedFileData(name="demo/b.py", content=b"value = 3\n"),
        ],
        record_id=imported.entry.record.id,
        settings=settings,
    )

    assert duplicate.duplicate is True
    assert duplicate.entry.record.id == imported.entry.record.id
    assert revision.entry.record.id == imported.entry.record.id
    assert revision.entry.asset.revision == 2
    reopened = use_cases.open_library_code_project(
        imported.entry.record.id,
        settings=settings,
    )
    assert "value = 3" in use_cases.get_code_file(reopened, "b.py").source


@pytest.mark.parametrize(
    ("uploads", "message"),
    (
        (
            [UploadedFileData(name="../escape.py", content=b"value = 1\n")],
            "unsafe relative path",
        ),
        (
            [UploadedFileData(name="demo/bad.py", content=b"\xff")],
            "valid UTF-8",
        ),
        (
            [UploadedFileData(name="demo/readme.txt", content=b"text")],
            "Python files only",
        ),
    ),
)
def test_code_directory_rejects_unsafe_or_unsupported_uploads(
    tmp_path: Path,
    uploads: list[UploadedFileData],
    message: str,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")

    with pytest.raises(LibraryImportError, match=message):
        use_cases.import_code_directory_to_library(
            uploads,
            settings=settings,
        )

    assert not list((settings.researchmind_data_dir / "assets").rglob("*.py"))
    assert not list((settings.researchmind_data_dir / ".staging").iterdir())


def test_managed_code_cannot_use_in_place_t5_b1_change(
    tmp_path: Path,
    fake_llm_provider: object,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    imported = use_cases.import_code_directory_to_library(
        [
            UploadedFileData(
                name="demo/main.py",
                content=b"def answer():\n    return 42\n",
            )
        ],
        settings=settings,
    )
    project = use_cases.open_library_code_project(
        imported.entry.record.id,
        settings=settings,
    )
    selection = use_cases.create_code_symbol_selection(
        project,
        "main.py",
        symbol_index=0,
    )

    with pytest.raises(ValueError, match="read-only"):
        use_cases.propose_code_change(
            project,
            selection,
            instruction="Return 43.",
            llm_provider=fake_llm_provider,
            settings=settings,
        )

    assert fake_llm_provider.calls == []


def test_deleting_removed_code_record_removes_only_managed_directory(
    tmp_path: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    imported = use_cases.import_code_directory_to_library(
        [
            UploadedFileData(
                name="demo/main.py",
                content=b"value = 1\n",
            )
        ],
        settings=settings,
    )
    record_id = imported.entry.record.id
    managed_root = (
        settings.researchmind_data_dir
        / "assets"
        / Path(imported.entry.asset.relative_path)
    )
    external_source = tmp_path / "external.py"
    external_source.write_text("value = 99\n", encoding="utf-8")

    use_cases.remove_library_record(
        record_id,
        confirmed=True,
        settings=settings,
    )
    assert use_cases.delete_library_managed_copies(
        record_id,
        confirmed=True,
        settings=settings,
    ) == 1

    assert not managed_root.exists()
    assert external_source.read_text(encoding="utf-8") == "value = 99\n"
