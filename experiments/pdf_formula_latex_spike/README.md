# Digital PDF formula recognition and LaTeX spike

Status: isolated Spike; not adopted into `src/researchmind/`.

## Technical question

Can ResearchMind use the existing PyMuPDF dependency to locate bounded formulas in a
digital PDF, preserve page/block/line/bbox provenance, and create a safe LaTeX
candidate for simple notation without claiming OCR or full two-dimensional equation
understanding?

The previous production heuristic classifies flattened block text.  This experiment
adds font family, font size, baseline shift, relation/operator, and span bbox signals.
It owns its own `FormulaCandidate` model so no experimental type enters Core, UI,
prompts, or Obsidian.

## Before/after criteria

The license-free automated cases require:

- simple display formulas and superscript/subscript notation are detected with a
  one-based page number and non-empty bbox;
- `E = mc²`, `xᵢ ∈ Rⁿ`, and Greek/relation symbols receive strict-parser-safe LaTeX;
- the inline formula `P(Y|X)` is bounded separately from surrounding prose;
- ordinary prose containing an equals sign and code-shaped text do not become
  candidates;
- image-only blocks return no candidate, making the OCR gap visible;
- stacked fractions and matrices are not silently labeled as deterministic LaTeX.

Two rendered representative pages have narrow manual labels for display-formula
region count only.  Inline candidates are still observational and their counts are
not reported as precision or recall.  The Chinese digital PDF deliberately includes
one display formula embedded as a JPEG; a digital-text recognizer must report zero
for that region rather than pretending it reconstructed the image.

## Run

```powershell
& .\.venv\Scripts\python.exe -m pytest `
  tests\unit\test_pdf_formula_latex_spike.py -q `
  --basetemp .release-tmp\formula-spike-tests

& .\.venv\Scripts\python.exe experiments\pdf_formula_latex_spike\benchmark.py `
  --sample code_security=D:\path\2408.02509v1.pdf `
  --sample statistical_learning=D:\path\统计学习方法李航(非扫描版).pdf `
  --sample chinese_scan=D:\path\chinese_scan.pdf
```

The benchmark validates each SHA-256 and prints only counts, confidence/signals, and
relative page locators.  It stores neither formula text nor absolute paths, makes no
network request, and never calls a real LLM.

`generate_visual_corpus.py` creates a license-free two-page QA artifact under
`output/pdf/` with both digital and raster formula cases.  It uses the bundled
artifact runtime only; ReportLab and Pillow are not added to ResearchMind's runtime
dependencies.

An explicit multimodal probe is separate.  It sends only one bounded crop after the
caller supplies `--confirm-external-transfer`:

```powershell
& .\.venv\Scripts\python.exe `
  experiments\pdf_formula_latex_spike\probe_multimodal.py `
  --pdf D:\path\lawful-test.pdf --page 1 --bbox 100 200 400 260 `
  --confirm-external-transfer
```

The crop is a size-limited PNG data URL.  No PDF path, surrounding page, API key, or
full request is printed.  Routine tests inject a fake completion callable and never
make a network request.

## Capability boundary

High-confidence one-dimensional notation can receive a deterministic LaTeX preview.
More complex bounded source should continue through ResearchMind's existing,
user-triggered ResearchContext and strict `<latex>` response parser.  A valid string
is still a reconstruction, not mathematical ground truth.

Fractions, roots with spatial radicands, matrices, aligned multi-line systems,
damaged font encodings, raster formulas, and scanned pages are not solved by the
deterministic digital-text path.  The isolated F2 crop path can ask the already
configured multimodal model to reconstruct one user-confirmed region, and two
license-free live probes cover scripts/set notation and a stacked fraction.  Its
result remains untrusted and must pass the existing strict LaTeX parser.

F2 is not local OCR and does not segment formulas inside a full-page scan.  It does
not authorize automatic upload, whole-page transfer, background processing, or
saving without preview.  Production adoption still requires a labeled real-formula
corpus, confidence/failure UX, privacy evidence, and an explicit architecture
decision.
