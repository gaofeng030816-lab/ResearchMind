# M3 Translation, Core Logic, and Use-Case Validation

Date: 2026-08-27

## Delivered scope

- Independent `TranslationProvider`, `TranslationError`, translation service,
  and the V1 `LlmTranslationProvider` implementation.
- Pure selection location, `ResearchContext` assembly, and conversation-history
  budgeting rules under `core/`.
- Application use cases for opening and viewing PDFs, searching, creating a
  selection, translating, explaining, and asking a grounded follow-up.
- A deterministic `FakeLlmProvider` and a no-network integration flow covering:

  ```text
  open PDF -> view/search -> select -> translate -> explain -> follow up
  ```

## Milestone boundary decision

`DEVELOPMENT_PLAN.md` contains a scope inconsistency: M3 asks for all nine use
cases, while M4 explicitly assigns `capture_knowledge` and
`save_note_to_vault` to the Obsidian milestone. M3 follows the more concrete M4
boundary and delivers the seven use cases through follow-up. Knowledge capture,
Markdown rendering, and Vault writing remain M4 work.

## Verification performed

- Focused M3 suite:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\unit\test_core_selection.py tests\unit\test_core_conversation.py tests\unit\test_core_research_context.py tests\unit\test_translation.py tests\integration\test_research_flow.py -q --basetemp=.pytest_tmp_m3
  ```

  Result: `21 passed`.

- Full regression suite:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp_all
  ```

  Result: `92 passed`.

- Python compilation: `python -m compileall -q src tests` passed.
- Dependency consistency: `python -m pip check` reported no broken requirements.
- Patch hygiene: `git diff --check` passed.
- Layer scan: no Streamlit, PyMuPDF, application, LLM, translation, or
  integration imports were found under `core/` or `models/`.
- Secret scan: no API-key-like value was found in project source, tests,
  documentation, or `.env.example`.

All automated M3 tests use fake providers. They do not make network requests or
spend API credits.

## Known limitations

- Context and history budgets use a deterministic four-characters-per-token
  approximation to avoid adding a provider-specific tokenizer in V1. Actual
  token usage varies by model and language.
- Selection location is normalized block-level substring matching. A selection
  spanning multiple extracted PDF blocks remains usable but is unlocated.
- An unlocated selection sends only the selected text; ResearchMind does not
  attach arbitrary page or document text.
- A real Dots API call remains a manual M2 validation item. No live call was made
  because no ignored local `.env` configuration is present in the workspace.
