---
name: pdf-research
description: Evaluate and review ResearchMind V3 PDF viewing, the adopted browser text-layer selection, extraction, formula-region detection, formula-to-LaTeX recognition, and isolated parser/OCR/component spikes. Use for PDF rendering, scroll/selection geometry, formulas, tables, figures, OCR, PyMuPDF, pdf.js, CCv2, or candidate PDF tools.
---

# PDF Research

Make evidence-based PDF decisions for ResearchMind's reading-to-context workflow.
Preserve the accepted PyMuPDF V2 baseline until a V3 gate adopts a measured change.

Read docs/ARCHITECTURE.md for current behavior, the relevant V3 decision record for
accepted evidence, and docs/PDF_FORMULA_LATEX_SPIKE.md when formula recognition is
involved.
V3-G3 adopted a locally bundled CCv2/pdf.js 6.3.289 text layer on top of the stable
G1 PDF identity/revision. V3-G4 subsequently completed click-only translation and
explicit evidence/draft capture from verified ReadingSelection values. V3-G5 is
Completed: `pdf/formulas.py` owns revision-bound local detection and one bounded PNG
crop; `llm/formula_recognizer.py` owns the narrow provider protocol and adopted
OpenAI-compatible remote adapter. Exact crop preview/consent, edit/validate/accept and
optional evidence capture are required. No local OCR weight, scanned-page OCR or
whole-PDF conversion is adopted; read
docs/V3_G5_FORMULA_RECOGNITION_DECISION.md.

## Separate the Responsibilities

- **Viewer:** shows the source, handles page/continuous navigation, zoom, search,
  selectable text layer, keyboard/mouse events, and scroll ownership.
- **Parser:** extracts text, spans, geometry, images, and structural candidates.
- **Formula detector:** proposes page regions likely to contain mathematics.
- **Formula recognizer:** converts one validated region into a LaTeX candidate.
- **Document understanding:** chooses bounded evidence for ResearchContext and notes.

Do not treat a good render, extracted string, detected box, or model response as proof
of the other responsibilities.

## Current Baseline and V3 Need

V2 uses PyMuPDF for validation, page images, search, text blocks/bboxes, conservative
layout roles, and embedded-image regions. It presents page imagery plus copy-friendly
blocks. The isolated formula Spike demonstrated useful digital/display-region and
image-crop candidates, but not reliable exact two-dimensional reconstruction.

The current G3 browser-selection contract is:

1. retain PyMuPDF as backend parser/rendering evidence;
2. render hash-bound local PDFs up to 10 MiB through the packaged CCv2/pdf.js layer;
3. treat viewer events as candidates and map them to ReadingSelection only after
   current-page PyMuPDF text/geometry reconciliation;
4. reject stale/duplicate/cross-instance events and retain the V2 image/text fallback.

Further detector precision or a local recognizer remains a new measured change:
benchmark on the locked G5 corpora and do not weaken the adopted per-crop boundary.

Native st.pdf may be compared for viewing, but its packaged dependency and event
surface must be verified; it is not assumed to expose the selection provenance V3
needs.

## Browser Selection and Interaction

For CCv2/pdf.js, verify:

- selection text matches the visible text layer;
- page, span/character range, and bboxes map to the current PDF revision;
- double-column, ligature, Unicode, superscript/subscript, and hyphenation behavior;
- ordinary page scrolling is not hijacked;
- wheel page-change ownership, page bounds, trackpad bursts, debounce, focus, and
  nested scroll regions;
- keyboard shortcut scope does not fire while typing or in unrelated widgets;
- reruns rehydrate current page/selection without duplicate events;
- component cleanup removes listeners and supports multiple instances.

Use only Streamlit Custom Components v2 for new interactive components. Start with an
isolated inline Spike; use the official component template before any packaged
component.

## Formula Recognition

Evaluate inline/display equations, integral and summation limits, roots, fractions,
Greek symbols, superscripts/subscripts, matrices, aligned multiline equations, and
equation numbers separately.

Success means a structurally useful, editable LaTeX candidate with traceable source,
not pixel-identical typography. Record:

- region detection recall/false positives;
- symbol/token and structural match on labeled formulas;
- reading-order/context errors around the region;
- latency, memory, Windows packaging, model size, and failure rate;
- whether content stays local or a crop is sent remotely;
- strict LaTeX validation and user edit/acceptance UX.

Never claim that flattened PDF text recovers the original formula layout. Never send
an entire paper to a formula service when one crop is sufficient. Whole-PDF-to-LaTeX
is not implied by region recognition.

## File Import Boundary

Streamlit uploads provide bytes and names, not a trusted original path. Validate PDF
extension, magic bytes, size, duplicate hash, and parseability before creating a
managed asset. Preserve the original display filename as untrusted metadata and use a
safe internal name/path.

## Investigation Workflow

1. Name the user failure and owning responsibility.
2. Reproduce it on a named page/corpus and capture the current V2 result.
3. Define a fixed metric and failure cases before comparison.
4. Prefer a boundary-local rule when it solves the measured problem.
5. Keep new components, parsers, OCR engines, and models in experiments until adopted.
6. Record Windows/local setup, dependency/license/maintenance, privacy/network
   behavior, internal-model mapping, and rollback.
7. Recommend adopt, reject, defer, or gather more evidence; recommendation is not
   production integration.

## Representative Evaluation

Include digital and scanned pages, single/double column, English/Chinese/Unicode,
complex mathematical layout, tables/figures/captions, malformed/blank pages, long
documents, and low-text coverage when the claim touches them. Use ground truth only
where it is actually labeled; do not invent accuracy percentages.

## Third-party Boundary

Keep PyMuPDF, pdf.js, parser JSON, OCR/model outputs, and vendor errors inside their
own PDF/component adapter. Convert them to ResearchMind models before Application,
Core, prompts, database, or notes. Preserve page/bbox/hash/origin/confidence whenever
conversion is lossy.

## Review Output

End with the problem/responsibility, fixed samples and baseline, before/after evidence,
failure cases, dependency/privacy/Windows impact, internal-model mapping, recommendation,
what it does not authorize, and regression coverage for the V2 reading loop.
