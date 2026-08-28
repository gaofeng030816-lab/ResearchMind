"""Tests for document-level application diagnostics."""

from pathlib import Path

from researchmind.app.use_cases import get_document_text_coverage
from researchmind.pdf import open_pdf
from tests.fixtures.pdf_factory import create_text_pdf


def test_text_coverage_reports_fully_extractable_document(
    multi_page_pdf: Path,
) -> None:
    coverage = get_document_text_coverage(open_pdf(multi_page_pdf))

    assert coverage.total_pages == 3
    assert coverage.pages_with_text == 3
    assert coverage.ratio == 1.0
    assert coverage.is_limited is False


def test_text_coverage_flags_document_without_extractable_text(
    blank_page_pdf: Path,
) -> None:
    coverage = get_document_text_coverage(open_pdf(blank_page_pdf))

    assert coverage.total_pages == 1
    assert coverage.pages_with_text == 0
    assert coverage.ratio == 0.0
    assert coverage.is_limited is True


def test_text_coverage_flags_ten_percent_extraction(
    tmp_path: Path,
) -> None:
    path = create_text_pdf(
        tmp_path / "limited-text.pdf",
        [["Only text page"], [], [], [], [], [], [], [], [], []],
    )

    coverage = get_document_text_coverage(open_pdf(path))

    assert coverage.total_pages == 10
    assert coverage.pages_with_text == 1
    assert coverage.ratio == 0.1
    assert coverage.is_limited is True
