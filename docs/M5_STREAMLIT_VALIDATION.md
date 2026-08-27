# M5 Streamlit UI Validation

Date: 2026-08-27

## Delivered scope

- `app/state.py` is the single explicit mutation boundary for application-owned
  Streamlit session state.
- `app/app.py` composes the four V1 views in reading order.
- The reader view opens a local PDF, renders the current page, exposes extracted
  text in a copy-enabled panel, navigates immediately by previous/next/page
  number, changes zoom, searches the document, and jumps to matching pages.
- The actions view locates copied or entered text and keeps translation separate
  from the four explanation modes.
- The conversation view displays in-memory messages and performs grounded
  follow-up calls against the active document and selection.
- The knowledge view selects conversation content, captures user understanding
  and tags, previews Markdown through the application API, and saves through
  the Obsidian integration.
- The UI displays expected PDF, configuration, LLM, translation, and Vault
  errors and shows the external-transfer notice before every LLM-backed action.
- `scripts/run_app.py` provides a Python entry point for the Streamlit process.

## Automated verification

- Focused Streamlit and launcher regression tests:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\e2e\test_streamlit_app.py tests\unit\test_run_app.py -q --basetemp=.pytest-tmp-ui-bugs
  ```

  Result: `4 passed`.

  The test runs the complete UI loop with fake AI functions and an isolated
  temporary Vault:

  ```text
  start -> open -> flip -> search -> select -> translate -> explain
  -> follow up -> open knowledge panel -> preview -> save -> read back
  ```

- Full regression suite:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp-m5
  ```

  Result after the PDF reading-quality follow-up: `115 passed`.

- Python compilation: `python -m compileall -q src tests` passed.
- Streamlit startup: the real application served its shell on
  `http://localhost:8501/` and returned HTTP `200`; the background test process
  was stopped afterward.
- The launcher was also exercised interactively: it displayed the local URL
  without asking for an email address, disabled Streamlit usage telemetry, and
  stopped on `Ctrl+C` without a Python traceback.
- Layer scan: no view imports `pdf`, `llm`, `translation`, or
  `integration.obsidian`; explicit application session-state writes occur only
  in `app/state.py`; environment access remains confined to `config.py`.
- Patch hygiene: `git diff --check` passed before this validation record was
  added.

## Real configuration checks

- The ignored local `.env` loads a configured Dots base URL, custom `api-key`
  header, `dots3-note-prev` model, and an existing Vault directory. No secret
  value was printed, copied into tracked files, or committed.
- A live call through the production Dots provider returned a non-empty response
  after the custom-header compatibility fix recorded in
  `M2_LLM_VALIDATION.md`.
- A real smoke note was written without overwrite to the configured test Vault,
  as recorded in `M4_OBSIDIAN_VALIDATION.md`.
- The production PDF use cases opened a real 5-page PDF under the user's course
  materials, extracted non-empty page-one text, and rendered a valid PNG.

## Manual visual status

The first human pass found a disabled extracted-text field, an unsynchronized
page-number control, and Streamlit's optional first-run email prompt. These were
reproduced and fixed with regression tests. The automated browser connection
had exited unexpectedly twice earlier, so a final human recheck of the corrected
page remains before claiming the M5 visual checklist is fully complete.
