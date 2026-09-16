# V3-G5 formula-recognition quality gate

Status: G5 completed evidence. Nothing in this directory is imported by the
production application; adopted runtime code lives under `src/researchmind/`.

## What was retained from the candidate audit

The local `LaTeX_OCR_PRO` snapshot usefully demonstrates a complete experimental
shape: normalize reference LaTeX, render formula images, crop/pad/grayscale them,
decode tokens with alternatives, then compare textual and visual outputs. ResearchMind
has clean-room implementations only for the fixed corpus, crop pipeline and
exact/token/structure metrics. Alternate-candidate and render-back comparison remain
future options. No legacy candidate source, dependency, dataset, model weight, Django
endpoint or shell pipeline is copied or executed.

Direct adoption is rejected: the snapshot is GPL-3.0, declares Python 3.5 and
TensorFlow 1.12/1.15, has no data submodule or weights, and uses `shell=True` for
parts of preprocessing/PDF conversion. See `candidate_audit.json` for hash-locked
evidence.

## Corpus and metrics

`corpus.tex` contains 20 license-free synthetic cases covering integrals, sums,
limits, fractions, roots, Greek symbols, scripts, matrices, aligned/cases layouts,
products, vectors and equation numbers. Every formula occupies one page. The build
step turns each page into a tight grayscale PNG and writes a SHA-256 manifest.

All recognizers must consume the same bounded crops and emit an explicit status plus
recognizer/model/execution/latency provenance. `evaluation.py` reports conservative
normalized exact match, token edit similarity, structural exact match, coverage and
strict ResearchMind LaTeX safety. A syntax pass is not mathematical correctness.

Planned adoption thresholds are fixed before provider comparison:

- coverage at least 85%;
- every returned candidate passes strict LaTeX safety;
- normalized exact match at least 75%;
- mean token similarity at least 95%;
- structural exact match at least 90%.

The final G5 corpus adds 18 bounded regions from three user-authorized papers. Reports
store source IDs/hashes and page/bbox only, never source paths or paper text. The
detector report, remote recognizer reports, failure diagnostic, visual spot check and
browser fake-provider evidence sit beside this file. Synthetic thresholds select the
adapter; the real corpus records detector failures, source-notation variance and the
need for editing rather than claiming source-TeX recovery.

## Rebuild

Compile `corpus.tex` with the bundled Tectonic workflow, then run:

```powershell
& .\.venv\Scripts\python.exe `
  experiments\g5_formula_recognition\build_corpus.py `
  --pdf path\to\corpus.pdf
```

Evaluate any isolated recognizer output with:

```powershell
& .\.venv\Scripts\python.exe `
  experiments\g5_formula_recognition\evaluation.py `
  path\to\predictions.json
```

G5 adopted only the production boundary recorded in
`docs/V3_G5_FORMULA_RECOGNITION_DECISION.md`. This experiment does not authorize a
local model installation, whole-page/whole-PDF conversion, automatic transfer, reuse
of crop consent, or persistence of an unaccepted model candidate.
