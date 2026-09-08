"""Small synthetic DOM fixtures, not PDFs or PDF extraction ground truth."""

from contract import PageSnapshot, Span


CASES = {
    "single": ("Select these words, then submit the selection.", "The second line is separate evidence."),
    "columns": ("Left column: first paragraph.", "Left column: second paragraph.",
                "Right column: first paragraph.", "Right column: second paragraph."),
    "unicode": ("A😀积分 ∑ α e\u0301 中文", "office ligature: ﬁ; hyphen-", "ation is not automatically repaired."),
    "math": ("Integral: ∫ f(x) dx; sum: ∑ x_i", "Text only — not formula recognition or LaTeX."),
    "empty": (),
}


def make_snapshot(case: str, page: int, instance: str) -> PageSnapshot:
    if case not in CASES or type(page) is not int or page not in (1, 2):
        raise ValueError("Unknown synthetic page")
    texts = CASES[case] if page == 1 else ("Page two. Previous-page selections must expire.",)
    # Deliberately coarse synthetic coordinates, unrelated to CSS/PDF pixels.
    spans = tuple(Span(text, (0.0, float(i * 30), 400.0, float(i * 30 + 20)))
                  for i, text in enumerate(texts))
    return PageSnapshot(f"synthetic-v1:{case}", instance, page, spans)
