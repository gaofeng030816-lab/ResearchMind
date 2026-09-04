# M5.1 PDF Reading Quality Validation

Date: 2026-08-27

## User-visible changes

- `scripts/run_app.py` starts Streamlit with `server.headless=false`, so
  Streamlit asks Windows to open the local page in the default browser. The
  launcher still disables the first-run Email prompt and usage telemetry.
- Extracted prose is normalized from visual PDF line wrapping into copy-friendly
  paragraphs, including conservative dehyphenation across lowercase word wraps.
- Text blocks are ordered with a deterministic recursive whitespace-cut
  algorithm before they are used by the reader, search, selection, or
  ResearchContext assembly.
- The reader exposes one copy button per ordered text block plus a separate
  whole-page copy panel.
- Embedded bitmap regions of at least 24 by 24 PDF points are recorded as
  `FigureRegion` objects, cropped to PNG on demand, previewed, and downloadable.

## OpenDataLoader PDF decision

The local Apache-2.0 OpenDataLoader PDF checkout was inspected. Its geometry-
based XY-Cut++ reading-order design and bounding-box-first output informed this
change. Its Python package is a Java CLI wrapper, the checkout has no built JAR,
and the machine has no Java executable. Hybrid OCR/chart/table/formula support
would additionally require Docling, EasyOCR, FastAPI/Uvicorn, and a second local
service. None of those dependencies or processes were added. Details are in
`OPENDATALOADER_PDF_REVIEW.md`.

## Verification

- Regression tests were first observed failing for row-major two-column order,
  missing figure regions, and `server.headless=true`.
- Focused PDF, launcher, and Streamlit suites:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\unit\test_pdf_reader.py tests\unit\test_run_app.py tests\e2e\test_streamlit_app.py -q --basetemp=.pytest-tmp-pdf-layout
  ```

  Result before the final UI assertion was added: `26 passed`; the additional
  ordered-block/figure-download AppTest passed independently.

- Full regression and compilation:

  ```powershell
  .\.venv\Scripts\python.exe -m compileall -q src tests scripts
  .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-pdf-layout
  ```

  Result: `115 passed`.

- A real five-page, two-column paper under the user's course materials was
  opened with the production PDF boundary. Page one produced 18 blocks ordered
  as header/title/metadata, abstract, complete left column, complete right
  column, footer, and vertical download notice.
- The real launcher started on port 8501 without an Email prompt. Automatic
  browser opening still depends on Windows having a valid default HTTP browser
  association.

## Honest limitations

- Recursive geometry improves common digital two-column academic papers but
  cannot guarantee the author's intended order for every mixed layout.
- Only embedded raster-image occurrences are detected. Vector-only plots,
  borderless tables, formulas, scans, and chart semantics are not recognized.
- OCR and hybrid layout models remain outside V1 and require a separate
  dependency/architecture decision.
