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


def create_two_column_pdf(path: Path) -> Path:
    """Create a two-column page with a wrapped paragraph and embedded chart."""

    document = pymupdf.open()
    try:
        page = document.new_page(width=600, height=800)
        page.insert_textbox(
            pymupdf.Rect(50, 30, 550, 60),
            "Two Column Study",
            fontname="helv",
            fontsize=14,
        )
        page.insert_textbox(
            pymupdf.Rect(50, 100, 280, 180),
            "Left first para-\ngraph continues here.",
            fontname="helv",
            fontsize=11,
        )
        page.insert_textbox(
            pymupdf.Rect(50, 150, 280, 210),
            "Left second block.",
            fontname="helv",
            fontsize=11,
        )
        page.insert_textbox(
            pymupdf.Rect(320, 100, 550, 180),
            "Right first block.",
            fontname="helv",
            fontsize=11,
        )
        page.insert_textbox(
            pymupdf.Rect(320, 150, 550, 210),
            "Right second block.",
            fontname="helv",
            fontsize=11,
        )
        chart_bytes = (
            b"P6\n4 2\n255\n"
            + bytes(
                [
                    220, 40, 40,
                    220, 40, 40,
                    40, 80, 220,
                    40, 80, 220,
                    220, 40, 40,
                    220, 40, 40,
                    40, 80, 220,
                    40, 80, 220,
                ]
            )
        )
        page.insert_image(
            pymupdf.Rect(320, 340, 550, 455),
            stream=chart_bytes,
        )
        page.insert_textbox(
            pymupdf.Rect(50, 750, 550, 780),
            "Page footer",
            fontname="helv",
            fontsize=10,
        )
        document.save(path)
    finally:
        document.close()
    return path


def create_corrupt_pdf(path: Path) -> Path:
    """Create a file with a PDF signature but invalid document structure."""

    path.write_bytes(b"%PDF-1.7\nthis is not a valid PDF body")
    return path
