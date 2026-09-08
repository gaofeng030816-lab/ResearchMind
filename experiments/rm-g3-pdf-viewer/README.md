# ResearchMind G3 PDF.js viewer experiment

This is an isolated Streamlit Custom Components v2 experiment. It renders one
bounded in-memory PDF page with PDF.js, exposes a browser text layer, previews a
mouse selection locally, and emits an untrusted candidate event only after the
user presses the experiment's submit button. The harness also tests focused,
edge-only wheel pagination, a typing-safe `Ctrl+Shift+A` AI-panel shortcut, and
native responsive paper-only/paper-plus-code layouts.

It is not imported by the ResearchMind application, is not a production viewer,
and does not call AI, translation, the working-library database, Zotero, or
Obsidian. A submitted candidate is re-extracted with PyMuPDF and must match current
revision, page, normalized text, bounded geometry, and a unique page occurrence.
The result remains an experiment type and is not yet a production `ReadingSelection`.

## Reproduce the fixture check

Requirements: Python 3.12, Streamlit 1.62 and PyMuPDF 1.28 for this isolated
environment, Node.js 24, npm, and Microsoft Edge. From this directory:

```powershell
cd rm_g3_pdf_viewer\frontend
npm ci
npm run build
cd ..\..
python -m pip install -e ".[fixture]"
python generate_fixture.py
python -m streamlit run example.py --server.address=127.0.0.1 --server.port=8504
```

In another terminal, pass the local Playwright module, fixture PDF, and an ignored
output directory to `browser_pdf_smoke.cjs`. The repository validation record
contains the exact observed environment and results.

`corpus.json` reuses the path-free, SHA-256-pinned five-document T2 corpus. Supply
lawful local copies at runtime as `id=path` arguments to `browser_corpus_probe.cjs`;
the probe stores only counts and booleans, never paths or selected document text.

## Experiment boundary

- PDF payloads must start with `%PDF-` and are limited to 10 MiB.
- PyMuPDF validates the upload and supplies the trusted page count; page and
  scale inputs are bounded before browser serialization.
- The component returns document revision, page, Unicode item ranges, normalized boxes,
  viewport, sequence, selected text, and engine version.
- The browser event remains untrusted. `provenance.py` rebuilds a current PyMuPDF
  character snapshot and returns trusted PDF-coordinate line boxes only when text
  and geometry identify one occurrence; client boxes never become provenance.
- Wheel page turns require explicit viewer focus, the current page edge, an
  80-pixel accumulated gesture, a valid adjacent page, and server revalidation.
  The first/last-page outer-scroll path is left available.
- After the first local load, a CCv2 loaded-revision state lets page and scale
  reruns omit the complete PDF payload. If the browser resource cache is absent,
  the component clears that state and the next rerun resends validated bytes.
- Vite emits fixed index.js and index.css assets so repeated setuptools builds
  cannot accumulate obsolete hashed bundles in a wheel.
- `Ctrl+Shift+A` is ignored while an input, text area, select, button, editable
  region, CodeMirror, or Monaco control owns the event. The displayed AI panel
  is a no-network placeholder only.
- `frontend/build`, `node_modules`, generated PDFs, screenshots, and local virtual
  environments are generated artifacts and are not source-controlled.

The component was scaffolded from the official Streamlit v2 component template at
commit `0b042aaa95e9080be93b079fd0c1519ee84e85cf`. PDF.js licensing is recorded in
`THIRD_PARTY_NOTICES.md`.
