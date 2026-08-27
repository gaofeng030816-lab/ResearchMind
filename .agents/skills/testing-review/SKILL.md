---
name: testing-review
description: Verify ResearchMind code changes, bug fixes, integrations, and completion claims with the V1 unit/integration/Streamlit test strategy, fake providers, regression tests, and honest result reporting.
---

# Testing and Review

Code is complete only after the changed behavior has been exercised by relevant tests. Inspection supports verification but does not replace execution. Use `docs/architecture.md` as the source of truth for the V1 behavior and boundaries being tested.

## Verification Loop

After a code change:

1. Review the changed files for scope, module ownership, type hints, errors, privacy, and secrets.
2. Run the narrowest tests that directly cover the change.
3. Run affected integration tests when the behavior crosses modules, configuration, PDF files, providers, or Vault I/O.
4. Run a Streamlit AppTest smoke check when UI composition, state, navigation, or actions changed.
5. Diagnose failures, fix only in-scope causes, and rerun every affected check.
6. Review the final Git diff. If Git metadata is unavailable, re-read every changed file and compare it with the requested behavior and architecture.
7. Report commands and actual outcomes, including skipped and unrelated failures.

Do not require the entire suite for a documentation-only edit, but validate structured files or skills with their available validator and inspect terminology/links for consistency.

## Test Isolation

- Routine tests never call a real LLM or translation API. Use `FakeLlmProvider`, mocks, or deterministic fakes.
- Tests never write to the user's real Obsidian Vault. Use a temporary directory.
- Tests never depend on the user's `.env`, keys, network, or personal PDFs.
- Keep fixture PDFs small and committed only when their license and contents are safe.
- Freeze or inject time where filenames and timestamps are asserted.
- Test observable behavior and invariants, not private implementation details or exact prompt prose without a functional reason.

## Unit Coverage by Responsibility

### Core

Test pure functions thoroughly:

- `core/selection.py`: current-page match, whole-document fallback, whitespace/case normalization, duplicates, and the non-blocking empty-locator result.
- `core/research_context.py`: selected text, adjacent-block context, page fallback, metadata fallback, context budget, and oversized input.
- `core/conversation.py`: recent-message ordering, history budget, empty history, and oversized messages.

### Application and knowledge capture

- use cases call the owning Domain and Infrastructure boundaries rather than duplicating their work;
- `capture_knowledge` handles optional fields, selected message inclusion, tags, user notes, and provenance in `KnowledgeNote`;
- failed provider or Vault operations do not leave application/session state reporting false success.

### LLM and prompts

Using a fake provider, cover:

- concept, math, algorithm, contextual, and follow-up prompt builders;
- application use cases build and pass `ResearchContext` before provider calls;
- `<paper_context>` delimiters and the instruction that paper/history content is untrusted data;
- timeout/API error mapping to `LlmApiError`;
- empty or malformed responses mapped to `LlmBadResponseError`;
- no secrets or full sensitive payloads in logs or user errors.

Do not assert a provider's natural-language answer. Assert messages, boundaries, calls, parsed results, and errors that ResearchMind owns.

### Translation

Test independently from AI explanation:

- selected text and configured target language reach `LlmTranslationProvider`;
- translation does not require PDF objects or a full `ResearchContext`;
- its prompt treats input as data, not instructions;
- provider failures map to `TranslationError`;
- empty input/response behavior matches the use-case contract.

### PDF

Fixture coverage must include:

- normal single-page and multi-page PDFs;
- missing, invalid/corrupt, and oversized files;
- extension and PDF magic-byte validation;
- blank pages;
- Unicode such as Chinese and Greek letters;
- mathematical symbols and extraction limitations;
- page order, page numbers, text blocks, search hits, and zoomed rendering.

Assert project exceptions at the PDF boundary rather than PyMuPDF-specific exceptions leaking outward.

### Obsidian integration

Using a temporary Vault, test:

- readable Markdown sections and traceability: title, author, page, and quoted source;
- optional translation, question/answer, user notes, and tags;
- filename sanitization and path-traversal rejection;
- configured subdirectory creation/validation behavior;
- collision numbering and the invariant that existing files are never overwritten;
- invalid Vault paths and write failures surfaced to callers;
- only `.md` plain-text output.

### Configuration and state

Test typed defaults, invalid settings, target language, context/history budgets, PDF size limit, provider selection, and Vault path validation without exposing secrets. Test state helper functions rather than scattering direct `st.session_state` mutations through view tests.

V1 has no database. Do not add database tests or fixtures unless a separately approved architecture change introduces persistence.

## Integration Coverage

Use a fixture PDF, deterministic fake provider, and temporary Vault to exercise the full product loop:

```text
open → render/search → select → translate → explain → follow up
→ capture KnowledgeNote → render Markdown → save without overwrite
```

Also cover important interrupted paths: unlocatable selection still translates/explains, provider failure does not corrupt conversation state, invalid PDF does not crash the app, and Vault failure does not report a successful save.

## Streamlit Smoke Coverage

Use Streamlit AppTest for the smallest stable end-to-end checks:

- app starts with missing/valid configuration handled clearly;
- a document can be opened and pages navigated, zoomed, and searched;
- selection, translation, explanation mode, and follow-up actions update the visible conversation;
- knowledge capture preview appears and saves only to the temporary Vault;
- reruns preserve intended state through `app/state.py`.

Avoid brittle pixel or exact-layout assertions; use a manual checklist for visual details AppTest cannot reliably cover.

## Bug-Fixing Workflow

For a bug:

1. Reproduce it with the smallest concrete input or sequence.
2. Add a regression test that fails for the demonstrated cause.
3. Apply the smallest fix at the module that owns the behavior.
4. Run the regression test and the affected suite.
5. Report if the original behavior could not be reproduced; do not invent a passing regression.

## Reporting

End completed code work with four concise sections:

- **Changed:** files/behaviors changed and why.
- **Tested:** exact commands and what each covered.
- **Result:** pass/fail counts or faithful summaries of actual output.
- **Remaining issues:** skipped checks, environment limitations, known limitations, and unrelated failures.

Never say “works,” “all tests pass,” or “complete” when the relevant test was not run. A missing dependency, unavailable environment, or unrelated failure is a reported limitation, not a pass.
