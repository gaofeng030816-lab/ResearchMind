# M4 Knowledge Capture and Obsidian Validation

Date: 2026-08-27

## Delivered scope

- `capture_knowledge` assembles a traceable `KnowledgeNote` from the opened
  document, optional selection, selected conversation messages, user notes,
  tags, and an optional user title.
- `render_markdown` produces readable UTF-8 Markdown with source metadata,
  quoted source text, optional translation, questions, AI explanations, user
  understanding, tags, and creation time.
- `write_note_to_vault` validates the configured Vault, confines output to a
  relative subdirectory, sanitizes cross-platform filenames, prefixes the date,
  writes only `.md`, and uses exclusive creation with collision numbering.
- `save_note_to_vault` is the application entry point; no other production
  module writes files.
- The integration test now covers the complete V1 non-UI product loop:

  ```text
  open -> render/search -> select -> translate -> explain -> follow up
  -> capture KnowledgeNote -> render Markdown -> save -> read back
  ```

## Safety behavior verified

- Missing or non-directory Vault roots are rejected.
- Absolute, blank, dot, and traversal subdirectories are rejected.
- Existing files used as output directories are rejected.
- Windows-invalid characters and reserved device names are sanitized.
- Filename collisions append `-2`, `-3`, and so on; existing content is never
  overwritten because files are opened in exclusive-create mode.
- Write failures surface as project-defined errors with no silent success.
- Tests write only to an isolated temporary Vault.

## Verification performed

- Focused M4 suite:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\unit\test_obsidian_markdown.py tests\unit\test_obsidian_vault.py tests\unit\test_knowledge_use_cases.py tests\integration\test_research_flow.py -q --basetemp=.pytest_tmp_m4
  ```

  Result: `17 passed`.

- Full regression suite:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp_m4_all
  ```

  Result: `108 passed`.

- Python compilation: `python -m compileall -q src tests` passed.
- Dependency consistency: `python -m pip check` reported no broken requirements.
- Patch hygiene: `git diff --check` passed.
- Layer scan: no Core/Models or PDF dependency violations were found, and the
  sole production file writer is the Obsidian Vault module.
- Secret scan: no API-key-like value was found in source, tests, documentation,
  or `.env.example`. The credential-bearing local `.env` is ignored by Git and
  was checked only through non-secret configuration state.

## Configuration and manual checks

The tracked template and ignored local `.env` select the Dots-compatible base
URL, `api-key` header, and `dots3-note-prev` model. The local API key is
configured and was never printed, staged, or committed. A live call through the
fixed provider returned a non-empty response.

The generated Markdown was written and read back as UTF-8 in automated tests.
A real non-overwriting smoke note was also created successfully in the configured
test Vault under its `ResearchMind` subdirectory. Opening that file in the
Obsidian desktop application remains a visual manual check.
