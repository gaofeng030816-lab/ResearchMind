"""Integration coverage for V3-G1 managed PDF library behavior."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.database import (
    LibraryConfirmationError,
    LibraryDatabaseError,
    LibraryImportError,
    LibraryNotFoundError,
)
from researchmind.models import UploadedFileData


def test_pdf_import_dedupe_restart_open_and_revision(
    tmp_path: Path,
    single_page_pdf: Path,
    multi_page_pdf: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    upload = UploadedFileData(
        name="paper.pdf",
        content=single_page_pdf.read_bytes(),
    )

    first = use_cases.import_pdf_to_library(upload, settings=settings)
    duplicate = use_cases.import_pdf_to_library(upload, settings=settings)

    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert duplicate.entry.record.id == first.entry.record.id
    assert first.entry.asset.relative_path.startswith("papers/")
    assert Path(first.entry.asset.relative_path).is_absolute() is False

    restarted_entries = use_cases.list_library_entries(settings=settings)
    reopened = use_cases.open_library_paper(
        first.entry.record.id,
        settings=settings,
    )

    assert [entry.record.id for entry in restarted_entries] == [
        first.entry.record.id
    ]
    assert reopened.document.title == "Fixture Research Paper"
    assert reopened.document.num_pages == 1

    revision = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="paper-revision.pdf",
            content=multi_page_pdf.read_bytes(),
        ),
        record_id=first.entry.record.id,
        settings=settings,
    )

    assert revision.entry.record.id == first.entry.record.id
    assert revision.entry.asset.revision == 2
    assert use_cases.open_library_paper(
        first.entry.record.id,
        settings=settings,
    ).document.num_pages == 3


def test_soft_remove_restores_duplicate_without_deleting_managed_pdf(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    upload = UploadedFileData(
        name="paper.pdf",
        content=single_page_pdf.read_bytes(),
    )
    imported = use_cases.import_pdf_to_library(upload, settings=settings)
    managed_path = (
        settings.researchmind_data_dir
        / "assets"
        / Path(imported.entry.asset.relative_path)
    )

    with pytest.raises(LibraryConfirmationError, match="Confirm removal"):
        use_cases.remove_library_record(
            imported.entry.record.id,
            confirmed=False,
            settings=settings,
        )

    use_cases.remove_library_record(
        imported.entry.record.id,
        confirmed=True,
        settings=settings,
    )

    assert use_cases.list_library_entries(settings=settings) == []
    assert managed_path.is_file()

    duplicate = use_cases.import_pdf_to_library(upload, settings=settings)

    assert duplicate.duplicate is True
    assert duplicate.entry.record.id == imported.entry.record.id
    assert duplicate.entry.record.removed_at is None


def test_managed_copy_deletion_is_separate_and_requires_soft_remove(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    imported = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="paper.pdf",
            content=single_page_pdf.read_bytes(),
        ),
        settings=settings,
    )
    record_id = imported.entry.record.id

    with pytest.raises(LibraryConfirmationError, match="Remove"):
        use_cases.delete_library_managed_copies(
            record_id,
            confirmed=True,
            settings=settings,
        )

    use_cases.remove_library_record(
        record_id,
        confirmed=True,
        settings=settings,
    )
    with pytest.raises(LibraryConfirmationError, match="Confirm"):
        use_cases.delete_library_managed_copies(
            record_id,
            confirmed=False,
            settings=settings,
        )

    assert use_cases.delete_library_managed_copies(
        record_id,
        confirmed=True,
        settings=settings,
    ) == 1
    assert not list(
        (settings.researchmind_data_dir / "assets").rglob("*.pdf")
    )
    with pytest.raises(LibraryNotFoundError):
        use_cases.open_library_paper(record_id, settings=settings)


def test_invalid_pdf_and_database_failure_leave_no_visible_asset(
    tmp_path: Path,
    single_page_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")

    with pytest.raises(LibraryImportError, match="signature"):
        use_cases.import_pdf_to_library(
            UploadedFileData(name="bad.pdf", content=b"not a pdf"),
            settings=settings,
        )

    def fail_create(*_args: object, **_kwargs: object) -> object:
        raise LibraryDatabaseError("simulated database failure")

    monkeypatch.setattr(
        "researchmind.database.LibraryRepository.create_entry",
        fail_create,
    )
    with pytest.raises(LibraryDatabaseError, match="simulated"):
        use_cases.import_pdf_to_library(
            UploadedFileData(
                name="paper.pdf",
                content=single_page_pdf.read_bytes(),
            ),
            settings=settings,
        )

    assert not list((settings.researchmind_data_dir / "assets").rglob("*.pdf"))
    assert not list((settings.researchmind_data_dir / ".staging").iterdir())


def test_finalize_failure_rolls_back_database_record(
    tmp_path: Path,
    single_page_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")

    def fail_finalize(*_args: object, **_kwargs: object) -> object:
        raise LibraryImportError("simulated finalize failure")

    monkeypatch.setattr(
        "researchmind.database.ManagedStorage.finalize",
        fail_finalize,
    )
    with pytest.raises(LibraryImportError, match="simulated"):
        use_cases.import_pdf_to_library(
            UploadedFileData(
                name="paper.pdf",
                content=single_page_pdf.read_bytes(),
            ),
            settings=settings,
        )

    assert use_cases.list_library_entries(settings=settings) == []
    assert not list((settings.researchmind_data_dir / "assets").rglob("*.pdf"))
    assert not list((settings.researchmind_data_dir / ".staging").iterdir())


def test_data_directory_must_be_explicit_and_separate_from_vault(
    tmp_path: Path,
) -> None:
    with pytest.raises(LibraryImportError, match="not configured"):
        use_cases.list_library_entries(settings=Settings())

    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(
        use_cases.USER_FACING_ERRORS,
        match="separate from the Obsidian Vault",
    ):
        use_cases.list_library_entries(
            settings=Settings(
                researchmind_data_dir=vault / "ResearchMindData",
                obsidian_vault_path=vault,
            )
        )


def test_concurrent_duplicate_pdf_import_converges_without_orphans(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    upload = UploadedFileData(
        name="paper.pdf",
        content=single_page_pdf.read_bytes(),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _index: use_cases.import_pdf_to_library(
                    upload,
                    settings=settings,
                ),
                range(2),
            )
        )

    assert len({result.entry.record.id for result in results}) == 1
    assert sorted(result.duplicate for result in results) == [False, True]
    assert len(use_cases.list_library_entries(settings=settings)) == 1
    assert len(
        list((settings.researchmind_data_dir / "assets").rglob("*.pdf"))
    ) == 1
    assert not list((settings.researchmind_data_dir / ".staging").iterdir())
