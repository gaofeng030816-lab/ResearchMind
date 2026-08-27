"""Small, license-free PDFs generated exclusively for automated tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pymupdf


PAGE_WIDTH = 360
PAGE_HEIGHT = 300


def create_text_pdf(
    path: Path,
    pages: Sequence[Sequence[str]],
    *,
    title: str = "",
    author: str = "",
) -> Path:
    """Create a PDF whose input strings become spatially separate blocks."""

    document = pymupdf.open()
    try:
        document.set_metadata({"title": title, "author": author})
        for block_texts in pages:
            page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
            for index, block_text in enumerate(block_texts):
                page.insert_text(
                    (36, 54 + index * 72),
                    block_text,
                    fontname="helv",
                    fontsize=12,
                )
        document.save(path)
    finally:
        document.close()
    return path


def create_unicode_math_pdf(path: Path) -> Path:
    """Create a page with CJK, Greek, and mathematical test content."""

    document = pymupdf.open()
    try:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_text(
            (36, 60),
            "中文文本",
            fontname="china-s",
            fontsize=14,
        )
        page.insert_text(
            (36, 120),
            "α β γ ∑ ∫",
            fontname="china-s",
            fontsize=14,
        )
        page.insert_text(
            (36, 180),
            "Equation: x^2 + y^2 = z^2",
            fontname="helv",
            fontsize=12,
        )
        document.save(path)
    finally:
        document.close()
    return path


def create_corrupt_pdf(path: Path) -> Path:
    """Create a file with a PDF signature but invalid document structure."""

    path.write_bytes(b"%PDF-1.7\nthis is not a valid PDF body")
    return path
