"""PDF fixtures used by the M1 unit suite."""

from pathlib import Path

import pytest

from tests.fixtures.pdf_factory import (
    create_corrupt_pdf,
    create_text_pdf,
    create_unicode_math_pdf,
)


@pytest.fixture
def single_page_pdf(tmp_path: Path) -> Path:
    return create_text_pdf(
        tmp_path / "single-page.pdf",
        [["ResearchMind introduction", "Second context block"]],
        title="Fixture Research Paper",
        author="Ada Researcher; Grace Scientist",
    )


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    return create_text_pdf(
        tmp_path / "multi-page.pdf",
        [
            ["Page one unique text", "Shared optimization method"],
            ["Page two unique text", "Shared Optimization result"],
            ["Page three conclusion"],
        ],
    )


@pytest.fixture
def blank_page_pdf(tmp_path: Path) -> Path:
    return create_text_pdf(tmp_path / "blank-page.pdf", [[]])


@pytest.fixture
def unicode_math_pdf(tmp_path: Path) -> Path:
    return create_unicode_math_pdf(tmp_path / "unicode-math.pdf")


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    return create_corrupt_pdf(tmp_path / "corrupt.pdf")
