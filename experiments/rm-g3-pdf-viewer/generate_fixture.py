"""Generate the deterministic, non-private PDF used by the G3 browser Spike."""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas


def main() -> None:
    output = Path("tmp/pdfs/g3-digital-text-fixture.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(output), pagesize=A4, pageCompression=0)
    width, height = A4
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(54, height - 60, "ResearchMind G3 PDF text-layer fixture")
    canvas.setFont("Helvetica", 12)
    canvas.drawString(54, height - 100, "Select this exact sentence with a real browser mouse.")
    canvas.drawString(54, height - 125, "Page one provides a stable single-column baseline.")
    canvas.drawString(54, height - 160, "Math symbols are a later recognition gate; this page tests text selection only.")
    canvas.drawString(54, 42, "Synthetic and non-private - page 1")
    canvas.showPage()
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(54, height - 60, "Two-column ordering fixture")
    canvas.setFont("Helvetica", 11)
    left = ["Left column first line.", "Left column second line.", "Left column final line."]
    right = ["Right column first line.", "Right column second line.", "Right column final line."]
    for index, text in enumerate(left):
        canvas.drawString(54, height - 105 - index * 28, text)
    for index, text in enumerate(right):
        canvas.drawString(width / 2 + 22, height - 105 - index * 28, text)
    canvas.drawString(54, 42, "Synthetic and non-private - page 2")
    canvas.save()


if __name__ == "__main__":
    main()
