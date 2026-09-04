# OpenDataLoader PDF Review for ResearchMind

Date: 2026-08-27

## Source reviewed

The local source tree at `<local-opendataloader-checkout>` was reviewed for
reading-order, text, table, image, chart, OCR, and Python integration code. The
repository identifies OpenDataLoader PDF as Apache-2.0 software and carries:

- `LICENSE` — Apache License 2.0;
- `NOTICE` — Copyright 2025-2026 Hancom, Inc.;
- `XYCutPlusPlusSorter.java` — geometry-based reading-order analysis;
- image region, caption, table, Markdown, JSON, tagged-PDF, and hybrid modules;
- a Python package that wraps a bundled Java CLI rather than reimplementing the
  extraction engine in Python.

## What ResearchMind adopted

ResearchMind adopted the product ideas that fit its existing local V1 boundary:

- use bounding boxes and recursive whitespace cuts instead of naïve row-major
  sorting for common two-column papers;
- preserve text blocks as the unit for selection, search, context, and copying;
- normalize visual line wrapping into copy-friendly prose while retaining block
  boundaries;
- keep only embedded-image bounding boxes in memory and crop a figure PNG on
  demand from the source page.

The resulting implementation is ResearchMind-specific Python in
`src/researchmind/pdf/layout.py` and `src/researchmind/pdf/reader.py`. No
OpenDataLoader Java source, JAR, model, or binary asset is bundled.

## What was deliberately not adopted

- The local checkout contains no built JAR, and this machine has no `java`
  executable. Adding a Java build/runtime would expand installation and process
  complexity.
- Hybrid OCR and complex chart/table/formula understanding require Docling,
  EasyOCR, FastAPI/Uvicorn, and an additional local service. That conflicts with
  ResearchMind V1's single Python process and current dependency policy.
- Tagged-PDF generation and accessibility remediation are valuable but outside
  ResearchMind's reading-to-knowledge product loop.

## Remaining limitations

The lightweight path improves ordinary digital two-column papers but is not a
replacement for a full document-layout engine. It does not OCR scans, infer
table semantics, convert formulas to LaTeX, understand chart meaning, or
reliably isolate figures drawn only from PDF vector primitives. Those require a
separately approved dependency and architecture decision if they become a core
product requirement.
