---
name: testing-review
description: Verify ResearchMind V1.3.2 optimizations, bug fixes, integrations, spikes, and approved transition work with regression-first unit/integration/Streamlit checks, representative research fixtures, quality evaluation, and honest evidence reporting.
---

# Testing and Review

Code is complete only after the changed behavior has been exercised by relevant tests. Inspection supports verification but does not replace execution. Use `docs/ARCHITECTURE.md` as the source of truth for current behavior and `V1 to V2过渡要求.md` for the approved transition gate and its exit evidence.

Current gate (2026-08-31): T5-A/T5-B1 and T6-A–T6-D are completed at local internal
`2.0.0rc1`; the source baseline is `269 passed, 1 skipped`. Its wheel builds and installs in a
fresh Python 3.12 venv, the installed `researchmind` command returns a loopback
Streamlit health response, backup/restore hashes match, repeat restore is rejected,
pip-audit reports no known vulnerabilities after pip 26.2.1, and the 2,000-file index
passes twice at 3.43/3.66 seconds. The user explicitly confirmed the paper,
independent-code, and T5-B1 manual journeys on 2026-08-31; report them as user evidence,
not browser automation. Code → Obsidian has focused use-case/Markdown/Vault/AppTest
coverage for current selection ownership, stale selection/question response rejection, relative-only
provenance, preview-before-save, and no absolute-root leakage. The T3 slice covers the explicit
local-folder/Python-first decision. The verified slice includes limits/exclusions,
UTF-8 and syntax failure semantics, AST symbol provenance, bounded CodeContext,
injection-resistant preview/prompt parity, fake-provider explanation, and Streamlit
smoke coverage. T4 adds locator validation, confidence and duplicate rules,
user-confirmed origin labels, session-state behavior, KnowledgeNote copying,
Markdown rendering, and a Streamlit paper-to-code link smoke.
T5-A adds strict action/wrapper rejection, prompt/tool-result injection boundaries,
fixed source availability, repeated/unknown action stops, question/call/output
budgets, provider/tool/user-stop audit, absolute-path omission, and Streamlit
start-preview-continue-final coverage with fake providers.
T6-A adds pure project-summary checks and a Streamlit regression proving the code
workspace opens without a PDF, exposes beginner/reproduction goals, reports static
entry/import/dependency/problem-file clues, and preserves paper/assistant navigation.
T6-B adds configuration warning/error/no-leak/no-mutation checks, manifest/SHA-256
Markdown backup and verified absent-target restore, malicious/tampered archive
rejection, CLI/Streamlit coverage, a non-editable clean install, and a real
baseline-wheel/current-wheel/baseline-wheel cycle with unchanged external Markdown.
T6-C adds a reproducible generated-data benchmark, source authority audit, pip-audit
before/remediation/after evidence, loopback restart recovery, and a 134-test focused
suite. The user explicitly confirmed its desktop/narrow-window manual checklist; do
not relabel that confirmation as AppTest, HTTP health, screenshots, or automated
browser evidence. T5-B1 adds focused protocol/core/writer/use-case and Streamlit tests.
Its only skip is Windows-host symlink creation; report it as an environment skip while
retaining source inspection and explicit production symlink rejection. T5-BX execution
remains unapproved.

For T5-B1 changes, preserve the separate red/green suite for protocol injection,
path/symlink/selection ownership, stale SHA-256 conflicts, no-confirmation zero writes,
recovery-copy non-overwrite, atomic apply, external-edit-safe rollback, audit metadata,
and explicit proof that no Shell/test/install authority exists. Execution requires an
isolated sandbox spike; a subprocess timeout is not a sandbox.

## Regression-first Baseline

Protect the working V1.3.2 loop in proportion to the change:

```text
open PDF → read/search/select → translate/LaTeX/explain → follow up
→ KnowledgeNote → Markdown → Obsidian Vault
```

A focused test proves the new behavior; it does not by itself prove the loop still
works. Run affected integration and Streamlit checks whenever a change crosses
selection, context, provider, conversation, state, or persistence boundaries.

For T6-A and later code-workspace checks, distinguish static evidence from execution:
an import or entry-point candidate is not proof that a dependency is installed, a
script runs, tests pass, or a result is reproducible. Verify that absolute project
paths and excluded file content do not leak into summaries or model inputs.
For code-note checks, also verify that preview alone writes nothing, only the existing
Vault boundary persists Markdown, PDF locator fields are absent, and changing the
selection/response or applying/rolling back code invalidates stale note previews.

Classify evidence correctly:

- **API connectivity**: endpoint/authentication/request mechanics work;
- **context quality**: the intended evidence is relevant, bounded, and traceable;
- **answer quality**: the model's explanation is useful and faithful for a labeled
  research example;
- **visual UX**: the real browser layout and interaction are usable.

One category cannot be reported as another. In particular, HTTP 200 is not evidence
that ResearchContext or the research answer is correct.

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

- `core/selection.py`: direct block selection, page/block/bbox preservation, current-page match, whole-document fallback, whitespace/case normalization, duplicates, and the non-blocking empty-locator result.
- `core/research_context.py`: selected text, adjacent-block context, page fallback, metadata fallback, context budget, and oversized input.
- For context changes, also assert page/source provenance, section/caption/formula
  association, conversation inclusion, irrelevant-text exclusion, and prompt payload
  size where applicable.
- `core/conversation.py`: recent-message ordering, history budget, empty history, and oversized messages.

### Application and knowledge capture

- use cases call the owning Domain and Infrastructure boundaries rather than duplicating their work;
- `capture_knowledge` handles optional fields, selected message inclusion, tags, user notes, and provenance in `KnowledgeNote`;
- failed provider or Vault operations do not leave application/session state reporting false success.

### LLM and prompts

Using a fake provider, cover:

- concept, math, algorithm, contextual, and follow-up prompt builders;
- the selection-to-LaTeX prompt, strict `<latex>` response parser, size bound, and
  rejection of TeX document/file/link/macro capabilities;
- application use cases build and pass `ResearchContext` before provider calls;
- `<paper_context>` delimiters and the instruction that paper/history content is untrusted data;
- timeout/API error mapping to `LlmApiError`;
- empty or malformed responses mapped to `LlmBadResponseError`;
- no secrets or full sensitive payloads in logs or user errors.
- LaTeX conversion uses a fresh `ResearchContext`, fake provider, and returns one
  validated expression without invoking a compiler.

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
- representative single-column and double-column scientific layouts;
- missing, invalid/corrupt, and oversized files;
- extension and PDF magic-byte validation;
- blank pages;
- Unicode such as Chinese and Greek letters;
- mathematical symbols and extraction limitations;
- superscript, subscript, Greek symbols, headings, paragraphs, tables, figures, and
  captions when the changed capability claims to handle them;
- flattened formula text used for LaTeX conversion without claiming OCR or exact
  two-dimensional reconstruction;
- page order, page numbers, text blocks, search hits, and zoomed rendering.
- a long-document performance/memory sample and a scanned/low-text sample when parser,
  caching, OCR diagnosis, or dependency evaluation changes.

Assert project exceptions at the PDF boundary rather than PyMuPDF-specific exceptions leaking outward.

### CodeContext

Use temporary project folders only. Cover eligible and excluded files, syntax errors,
non-UTF-8 input, file-count/total/per-file limits, symlink/root containment, and
project errors. Assert import/function/class/method line provenance and include a
sentinel proving source text was parsed but never executed. Test symbol and line
selection, context budget/rejection, `<code_context>` escaping, absolute-path
omission, preview/request parity, fake-provider explanation, and Streamlit state.
Never point routine tests at a user's private repository or run its code.

### Controlled code change (T5-B1)

Use a disposable temporary Python project and fake provider. Cover strict single-wrapper
parsing, prompt injection, relative-path-only diffs, project/selection/index ownership,
UTF-8 and syntax/size/change-line budgets, raw SHA-256 source conflicts, path traversal,
symlink and ordinary-file checks, no-confirmation/cancel zero writes, non-overwriting
recovery, atomic replacement failure, external-edit-safe rollback, and metadata-only
audit. Assert apply/rollback refresh the in-memory `CodeProject` and invalidate stale
selection/response state. Never run the modified project, Shell, tests, or installers.

### Evidence links

Use project models and temporary PDF/code inputs. Cover located/unlocated paper
selection, code-project ownership, line/source consistency, paper/mathematics/
algorithm kinds, valid and invalid confidence, duplicate claims, and explicit
generation method. Verify UI and Markdown distinguish user-confirmed,
deterministic, and model-inferred origins while the production path creates only
user-confirmed links. Assert link creation makes no provider call, opening a new
source clears stale links, KnowledgeNote copies the list, and export contains both
locators without an absolute code root.

### Obsidian integration

Using a temporary Vault, test:

- readable Markdown sections and traceability: title, author, page, and quoted source;
- validated LaTeX appears as bounded display math and is omitted when absent;
- optional translation, question/answer, user notes, and tags;
- optional evidence links with both endpoints, relation, confidence, origin, and
  safely formatted excerpts;
- filename sanitization and path-traversal rejection;
- configured subdirectory creation/validation behavior;
- collision numbering and the invariant that existing files are never overwritten;
- invalid Vault paths and write failures surfaced to callers;
- only `.md` plain-text output.

For T6-B maintenance, also test:

- configuration reports contain no credential values or absolute Vault paths, perform
  no network request, and do not create the configured subdirectory;
- backup ignores non-Markdown data and rejects symlinks, existing archives, excessive
  file counts/size, and read failures;
- restore validates every member and manifest entry before staging, rejects traversal,
  duplicate/encrypted/symlink/unsupported/tampered content, and never writes into an
  existing target;
- clean install uses a new Python 3.12 venv and non-editable package install; package
  upgrade/rollback uses saved artifacts and verifies persistent files outside the
  environment remain unchanged;
- package-index or proxy failures are reported separately from project packaging
  failures and are not hidden with unsafe install flags.

### Configuration and state

Test typed defaults, invalid settings, target language, context/history budgets, PDF size limit, provider selection, and Vault path validation without exposing secrets. Test state helper functions rather than scattering direct `st.session_state` mutations through view tests.

V1 has no database. Do not add database tests or fixtures unless a separately approved architecture change introduces persistence.

## Integration Coverage

Use a fixture PDF, deterministic fake provider, and temporary Vault to exercise the full product loop:

```text
open → render/search → select → translate → constrained LaTeX → explain → follow up
→ capture KnowledgeNote → render Markdown → save without overwrite
```

Also cover important interrupted paths: unlocatable selection still translates/explains, provider failure does not corrupt conversation state, invalid PDF does not crash the app, and Vault failure does not report a successful save.

## Optimization and Spike Evaluation

For an optimization, define the user-visible or quality baseline before implementation
and compare the same corpus and metric after it. Useful measures include selection
steps, location success, reading-order errors, parser accuracy, context
precision/recall, payload characters/tokens, latency, memory, and human readability.
Choose only measures that answer the stated problem.

For a major-dependency spike:

- keep the experiment outside production imports and routine tests;
- use representative scientific papers and record failures, not only showcase cases;
- compare against the current PyMuPDF/ResearchMind behavior on the same inputs;
- record Windows/local setup, runtime, memory, privacy/network behavior, dependency
  and license cost, and internal-model mapping effort;
- report adopt, reject, or defer as a recommendation, not as proof of production
  integration.

## Streamlit Smoke Coverage

Use Streamlit AppTest for the smallest stable end-to-end checks:

- app starts with missing/valid configuration handled clearly;
- a document can be opened and pages navigated, zoomed, and searched;
- selection, translation, explanation mode, and follow-up actions update the visible conversation;
- LaTeX conversion exposes a copyable expression and local math preview before it is
  captured into Markdown;
- knowledge capture preview appears and saves only to the temporary Vault;
- reruns preserve intended state through `app/state.py`.
- the code workspace opens a temporary project, selects code, previews evidence, and
  receives a fake explanation without execution.
- T5-B1 previews a strict relative-path diff, requires explicit apply/rollback consent,
  writes only the disposable selected file, exposes a recovery receipt, supports safe
  rollback, and makes cancel a zero-write metadata-only event.
- a located PDF selection and current code selection can form a user-confirmed link
  that reaches KnowledgeNote without a network call.

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
For a phase gate, map each exit criterion to evidence and leave the phase incomplete
when a required manual, quality, security, or regression check is missing. A user's
explicit manual acceptance may close a manual checklist, but name who confirmed it and
never convert it into automated browser evidence.
