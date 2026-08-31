---
name: pdf-research
description: Evaluate and review ResearchMind scientific-PDF viewing, parsing, extraction quality, document understanding, and isolated parser/OCR technology spikes. Use for PDF rendering, reading order, text/bbox selection, formulas, tables, figures, captions, OCR, or tools such as PyMuPDF, OpenDataLoader-PDF, Docling, and Marker; not for generic project planning or unapproved production integration.
---

# PDF Research

Make evidence-based PDF decisions that improve ResearchMind's reading-to-context
workflow without replacing a stable implementation merely because another parser has
more features.

Read `docs/ARCHITECTURE.md` for the current PDF boundary and
`V1 to V2过渡要求.md` for the approved transition stage. Do not implement a planned
PDF/OCR capability when the task only asks for evaluation or the stage is unapproved.

## Separate the Responsibilities

Do not evaluate “PDF support” as one undifferentiated capability:

- **PDF Viewer** helps the user see and navigate the original document. Its concerns
  include rendering fidelity, page navigation, zoom, search, and interaction.
- **PDF Parser** extracts text, geometry, images, and structural candidates for
  ResearchMind. Its concerns include reading order, blocks, bbox, symbols, tables,
  figures, captions, and OCR.
- **Document Understanding** selects and interprets parser evidence for
  ResearchContext. A parser output is not automatically a useful prompt or a correct
  semantic model.

Rendering aims to show the source faithfully. Parsing aims to expose useful,
traceable evidence. Understanding decides how that evidence supports a research task.

## Current 2.0.0rc1 PDF Baseline

The production baseline uses PyMuPDF inside `pdf/` for validation, rendering, text
blocks, search, bbox geometry, lightweight embedded-image regions, revision-aware
caches, and low-text coverage diagnosis. `pdf/layout.py` provides conservative
reading-order, copy-friendly paragraph, heading/caption, and formula-candidate rules.

T1 additionally carries page/block/bbox from direct text/formula block selection into
ResearchContext and KnowledgeNote. T2 completed a repeatable five-document comparison:
retain PyMuPDF and defer OpenDataLoader-PDF. The spike remains in `experiments/`; no
candidate parser entered `src/`.

T3 added a separate read-only Python CodeContext path and did not change PDF parsing,
ResearchContext fields, PyMuPDF ownership, or the T2 dependency decision. T4
user-confirmed evidence links preserve this boundary: their paper endpoint consumes
existing page/block/bbox provenance, while code parsing remains outside `pdf/`.
T5-B1 adds one controlled Python range-replacement path under `code/`; it does not
change PDF extraction, selection provenance, formula handling, parser adoption, or
ResearchContext. Do not use T5-B1 as authority to write PDF-derived content back into
source files or to adopt OCR/parser dependencies.

ResearchMind reviewed local OpenDataLoader-PDF material and adopted a small
XY-Cut-inspired idea in its own Python/PyMuPDF layout code. OpenDataLoader-PDF's
Java/JAR/runtime and data model are not production dependencies. Treat
OpenDataLoader-PDF, Docling, Marker, OCR engines, or a replacement PDF engine as
candidates until a separate spike and adoption decision exist.

Do not claim current support for scanned-text OCR, image-formula recovery, semantic
tables, vector-chart understanding, exact two-dimensional equation reconstruction, or
arbitrary document structure.

T6-D did not change the PyMuPDF boundary. Mouse-wheel page navigation remains an
unimplemented CCv2 interaction spike candidate and must prove debounce, page bounds,
trackpad behavior, and no ordinary-scroll hijacking before production adoption.

## Investigation Workflow

1. Define the concrete user failure: viewing, selection, parsing, source location, or
   context quality.
2. Reproduce it with a named page and a representative paper; preserve a safe fixture
   or evaluation record when licensing/privacy permits.
3. Identify whether the failure belongs to Viewer, Parser, layout normalization,
   Selection, or Context Builder.
4. Measure the current PyMuPDF/ResearchMind result before comparing alternatives.
5. Prefer a small rule or boundary-local fix when it solves the measured problem.
6. Use an isolated `experiments/` spike for a major dependency or parser replacement.
7. Decide adopt, reject, defer, or collect more evidence. Adoption is a separate
   architecture/implementation task.

## Evaluation Matrix

Select criteria relevant to the claim, and record failures as well as successes:

- text accuracy and missing/duplicated characters;
- page number, text block, line/span, and bbox fidelity;
- single- and double-column reading order;
- paragraph joining, hyphenation, headings, lists, and references;
- English, Chinese, Unicode, Greek symbols, operators, superscript, and subscript;
- inline math, display math, matrices, equation numbering, and text around equations;
- table cells/order, figures, captions, raster versus vector content;
- digital, scanned, blank, malformed, long, and complex-layout PDFs;
- rendering/extraction latency, memory, and cache behavior;
- Windows support, local/offline behavior, privacy/network transfer;
- dependency size, runtime setup, license, maintenance, replaceability, and failure
  semantics.

For quantitative comparison, keep the corpus and metric fixed before/after. Useful
metrics include reading-order error count, character/word accuracy, locator accuracy,
formula structural match, table cell accuracy, latency, peak memory, and human
readability. Do not invent precision/recall without labeled ground truth.

## Mathematics-specific Review

For mathematical papers, inspect superscripts, subscripts, Greek symbols, operators,
inline/display equations, numbering, multiline alignment, matrices, and reading order
around equations separately. A flattened digital text layer may support selection and
LLM-assisted LaTeX, but it is not evidence that the original two-dimensional formula
was recovered.

Image formula OCR and automatic LaTeX reconstruction require their own labeled corpus,
quality thresholds, privacy analysis, and failure UX. Do not silently merge them into
the current selection-driven LaTeX path.

## Third-party and Core Boundary

- Do not build a rendering engine from scratch; prefer mature PDF technology.
- Keep every third-party PDF object and error inside a PDF adapter.
- Convert output into ResearchMind-owned models before it reaches Application, Core,
  UI, prompts, or persistence.
- Do not make a vendor JSON/element schema the `Document` model.
- Preserve page/block/bbox provenance and explicit confidence/origin when conversion
  is lossy.
- Do not add a dependency merely to obtain richer or prettier JSON.

## Review Output

End a PDF decision or spike with:

- user problem and responsibility boundary;
- baseline and representative samples;
- before/after results and failure cases;
- dependency, privacy, Windows, and maintenance impact;
- internal-model mapping;
- recommendation and what it does not authorize;
- regression plan for the existing V1.3.2 loop.
