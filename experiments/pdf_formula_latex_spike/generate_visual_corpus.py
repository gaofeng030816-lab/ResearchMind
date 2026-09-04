"""Generate one license-free visual QA PDF for the formula spike.

This evidence-only script uses the bundled PDF artifact runtime.  ReportLab and
Pillow are not ResearchMind production dependencies.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "output"
    / "pdf"
    / "formula-spike-visual-corpus.pdf"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _generate(args.output)
    print(args.output.resolve())
    return 0


def _generate(path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    pdf.setTitle("ResearchMind Formula Spike Visual Corpus")
    pdf.setAuthor("ResearchMind test fixture")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, height - 54, "Digital formula geometry cases")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        54,
        height - 76,
        "License-free QA page: display, inline, scripts, fraction, matrix, and negatives.",
    )

    y = height - 125
    pdf.setFont("Helvetica", 11)
    pdf.drawString(54, y, "Display with superscript:")
    pdf.setFont("Times-Roman", 18)
    pdf.drawString(250, y - 2, "E = mc")
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(303, y + 7, "2")

    y -= 58
    pdf.setFont("Helvetica", 11)
    pdf.drawString(54, y, "Subscript and superscript:")
    pdf.setFont("Times-Roman", 18)
    pdf.drawString(250, y - 2, "x")
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(259, y - 8, "i")
    pdf.setFont("Times-Roman", 18)
    pdf.drawString(271, y - 2, " in R")
    pdf.setFont("Times-Roman", 10)
    pdf.drawString(306, y + 7, "n")

    y -= 68
    pdf.setFont("Helvetica", 11)
    pdf.drawString(54, y, "Stacked fraction (must preserve 2-D structure):")
    pdf.setFont("Times-Roman", 15)
    pdf.drawCentredString(330, y + 13, "a + b")
    pdf.line(300, y + 8, 360, y + 8)
    pdf.drawCentredString(330, y - 10, "c + d")

    y -= 90
    pdf.setFont("Helvetica", 11)
    pdf.drawString(54, y, "Matrix (must not flatten row/column order):")
    pdf.setFont("Times-Roman", 15)
    pdf.drawString(298, y + 12, "[ a   b ]")
    pdf.drawString(298, y - 10, "[ c   d ]")

    y -= 78
    pdf.setFont("Helvetica", 11)
    pdf.drawString(54, y, "Inline case: The model uses P(Y|X) for prediction.")
    y -= 38
    pdf.drawString(54, y, "Negative prose: Version 2.0 = current baseline.")
    y -= 28
    pdf.setFont("Courier", 9)
    pdf.drawString(54, y, "cursor.execute('SELECT x FROM t WHERE id=%s')")

    pdf.showPage()
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, height - 54, "Embedded raster formula boundary")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(
        54,
        height - 76,
        "This formula has no PDF text layer and requires a user-confirmed vision/OCR path.",
    )
    image = Image.new("RGB", (1200, 150), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 56)
    except OSError:
        font = ImageFont.load_default(size=56)
    draw.text((36, 38), "T = {(x_i, y_i)}_{i=1}^{N}", fill="black", font=font)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    pdf.drawImage(
        ImageReader(buffer),
        72,
        height - 190,
        width=468,
        height=58.5,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.setFont("Helvetica", 10)
    pdf.drawString(72, height - 220, "Expected: one wide, short embedded-image candidate.")
    pdf.save()


if __name__ == "__main__":
    raise SystemExit(main())
