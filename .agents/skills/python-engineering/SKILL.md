---
name: python-engineering
description: Implement incremental ResearchMind Python changes for the verified V1.3.2 baseline or an explicitly approved transition slice while preserving module ownership, project models, dependency boundaries, error semantics, and understandable code. Do not use it to authorize unapproved V2 scope.
---

# Python Engineering

Build explicit, typed, testable Python that a beginner/intermediate developer can understand. Read `docs/ARCHITECTURE.md` before making structural choices; it is the source of truth for current technology, ownership, and dependency rules. For transition work, confirm that the relevant stage in `V1 to V2过渡要求.md` is approved before adding future models or infrastructure.

Current gate (2026-08-31): T5-A/T5-B1 and T6-A–T6-D are completed at local internal
version `2.0.0rc1`, with a `269 passed, 1 skipped` source baseline. The installed
`researchmind` launcher, diagnostics, recovery, security, repeated performance checks,
and user-confirmed paper/independent-code/T5-B1 journeys pass. Code → Obsidian is
implemented through `capture_code_knowledge`, code-specific Markdown, dedicated
session state, explicit preview, and the existing Vault writer. Preserve its current
selection/source/response validation, relative-only provenance, no-PDF entry, and
no-model/no-source-write save semantics. PDF wheel-page interaction remains an
unimplemented CCv2 spike candidate. T3 adds
`models/code_*`, read-only `code/` infrastructure, pure `core/code_context.py`,
bounded code prompts/use cases, and one Streamlit code workspace. Keep candidate PDF
parsers outside `src/`. T4 adds `models/evidence_link.py` and pure
`core/evidence_links.py` with user-confirmed links and KnowledgeNote export. T5-A adds
`models/core/llm/read_only_assistant.py`, fixed use-case dispatch, centralized
Streamlit state, and one user-stepped view. Preserve its exact three no-argument
read-only tools and budgets. T6-A adds top-level paper/code/assistant navigation,
an independent code workspace, two user goals, and a pure `CodeProjectSummary`
derived from the already indexed project. Preserve the no-PDF entry and do not turn
static entry/import/dependency candidates into execution claims. T6-B adds project-owned maintenance result dataclasses,
`maintenance.py` diagnose/backup/restore coordination, `integration/obsidian/backup.py`
validation and staging, plus an explicit Streamlit check. Preserve no-network/no-key
diagnostics, Markdown-only archives, full prevalidation, absent restore targets, and
non-overwrite. T6-C adds a generated-data evaluation harness outside production;
its automated gates passed and the user explicitly confirmed the desktop/narrow-window
manual checklist. T5-B1 adds project-owned code-change models, pure proposal rules,
strict replacement parsing, use-case confirmation, centralized state, and one narrow
atomic writer. Preserve the exact one-selected-range/recovery/hash-conflict/rollback
contract. `launcher.py` is the sole fixed process wrapper and may only start the
package-owned Streamlit app; it is not user-code execution authority. Do not add
other subprocesses, test execution, dependency installation, multi-file
changes, or arbitrary-path writes without a separately approved T5-BX decision.

## Runtime and Shape

- Target Python 3.12.
- Keep a single local Streamlit application with src-layout.
- Use the established V1 stack: Streamlit, PyMuPDF, `openai` through an OpenAI-compatible provider, python-dotenv, and pytest.
- V1 has no REST backend, database, ORM, background worker, or separate service.
- Use dataclasses for data, protocols only at justified provider boundaries, and plain functions for stateless behavior.
- Prefer the standard library and existing dependencies. Explain why any new dependency is necessary before adding it.

## Incremental Change

- Preserve the working V1.3.2 loop and make the smallest change at the module that
  owns the behavior.
- Do not refactor unrelated modules while optimizing one workflow. Split the work when
  review, regression, or rollback would otherwise become unclear.
- Keep interfaces narrow and responsibilities explicit; do not introduce a framework
  or extension mechanism for a single speculative future implementation.
- Automatic/model-created evidence links, persistence, OCR, REST, other content
  providers, or agent tools stay out of production code until their transition phase
  and architecture changes are explicitly approved.

## Third-party Boundary

External libraries implement capability; ResearchMind owns the models used across
layers.

- Convert PyMuPDF/parser output into project `Document`, `Page`, `TextBlock`,
  `FigureRegion`, or a separately approved internal model before it leaves the PDF
  boundary.
- Never make OpenDataLoader JSON/elements, Docling/Marker objects, or another parser's
  schema the Core or UI contract.
- Convert LLM SDK responses into project `Message` or a validated task result.
- Convert translation-provider responses into the project's translation result and
  error semantics.
- Keep vendor errors, retries, resource handles, and configuration inside their
  infrastructure adapters.

This boundary reduces coupling, permits replacement, and keeps deterministic tests
possible. Do not build a generic adapter framework until more than one real
integration demonstrates a common contract.

## Module Ownership

```text
src/researchmind/
├── config.py                  # only environment/secrets reader
├── launcher.py                # packaged Streamlit console entry only
├── maintenance.py             # explicit T6-B diagnose/backup/restore CLI
├── models/                    # shared pure dataclasses
├── app/
│   ├── app.py                 # Streamlit composition
│   ├── state.py               # only session-state mutation point
│   ├── use_cases.py           # application API and orchestration
│   └── views/                 # display and event delegation
├── core/                      # pure domain rules
├── pdf/                       # PyMuPDF infrastructure
├── code/                      # T3 reads plus sole T5-B1 controlled source writer
├── llm/                       # LLM protocol, prompts, provider, parsing
├── translation/               # independent translation capability
└── integration/obsidian/      # Markdown rendering and Vault writes
```

Do not create parallel `database/`, `notes/`, `services/`, or generic `utils/` modules for V1 behavior already owned above.

## Allowed Dependency Flow

Use concrete import rules instead of a misleading linear layer chain:

```text
app/views → app/use_cases
app/use_cases → core + infrastructure boundaries + models
core → models + standard library
infrastructure → models/protocols + external libraries
models → standard library only
```

- Views never import PyMuPDF, provider SDKs, translation providers, or Vault writers.
- Views never implement parsing, context assembly, prompting, knowledge capture, or file-writing rules.
- Only `state.py` mutates `st.session_state`; views use its functions.
- Application use cases coordinate Domain and Infrastructure. This orchestration is not a Domain responsibility.
- `core/` remains pure and framework-independent. It does not import Streamlit, provider SDKs, PyMuPDF, or file-system integrations.
- `models/` imports no project layer and performs no I/O.
- Infrastructure modules do not call each other across product responsibilities unless the architecture explicitly requires it. In V1, `LlmTranslationProvider` may depend on the `LlmProvider` protocol; PDF never calls LLM, translation, or Obsidian.

## Application Contracts

Treat functions in `app/use_cases.py` as V1's application API. UI behavior should compose or extend these use cases rather than reaching around them:

- `open_pdf`, `get_page_view`, `search_text`, `create_selection`
- `get_configuration_report`
- `open_code_project`, `get_code_file`, `create_code_symbol_selection`,
  `create_code_line_selection`
- `translate_selection`, `explain_selection`, `ask_followup`
- `preview_code_context`, `explain_code_selection`
- `propose_code_change`, `apply_code_change_proposal`,
  `rollback_applied_code_change`
- `create_evidence_link`, `add_evidence_link`
- `convert_selection_to_latex`, `preview_latex_context`
- `capture_knowledge`, `save_note_to_vault`

Keep signatures typed and return plain project models or small view/application dataclasses such as `OpenedDocument`, `PageView`, and `TextMatch`. Do not introduce REST-shaped DTOs until a REST API is actually requested.

## Domain Models and Rules

Represent shared concepts with dataclasses, not ad-hoc dictionaries:

- `Document`, `Page`, `TextBlock`
- `ReadingSelection`, with a source-typed locator; V1 source is PDF
- `ResearchContext`
- `Conversation`, `Message`
- `KnowledgeNote`
- `CodeProject`, `CodeFile`, `CodeSymbol`, `CodeProjectSummary`, `CodeSelection`,
  `CodeContext`
- `CodeFileSnapshot`, `CodeChangeProposal`, `CodeChangeReceipt`,
  `CodeChangeRollbackReceipt`, `CodeChangeAuditEvent`
- `PaperEvidenceReference`, `CodeEvidenceReference`, `EvidenceLink`
- `ConfigurationCheck`, `ConfigurationReport`, `MarkdownBackupResult`,
  `MarkdownRestoreResult`

Use the current names. Do not reintroduce the old `Paper`, `Selection`, or `Note`
model names. Do not replace the implemented T3/T4 project models with AST/vendor
nodes or untyped locator dictionaries.

Domain behavior belongs in small pure functions:

- `core/selection.py`: locate normalized selected text in the current page first, then the document; failure to locate returns an empty locator without blocking translation/explanation.
- `core/research_context.py`: assemble selected text, nearby blocks, document metadata, current question, and budgeted history.
- `core/conversation.py`: keep recent history within configuration budgets.
- `core/evidence_links.py`: validate both locators, create user-confirmed links, and
  reject duplicate claims without I/O.
- `core/code_changes.py`: validate one selected Python range and source snapshot, build
  one syntax-checked bounded candidate and relative-path diff, and update the in-memory
  project model without I/O.
- `app/use_cases.py::capture_knowledge`: assemble a `KnowledgeNote`; Markdown rendering and writing remain in Obsidian integration.

## ResearchContext and Prompts

Every explanation and follow-up use case must build a fresh `ResearchContext` before invoking `LlmProvider`. Use relevant nearby text blocks rather than sending the whole PDF. Apply configured context and history budgets without crashing on oversized input.

Every code explanation builds a fresh `CodeContext` from one explicit `CodeSelection`.
It sends only relative path/line/symbol provenance, selected code, bounded neighboring
lines, and the question. Keep it separate from ResearchContext: an EvidenceLink
connects provenance and capture, not prompt payloads.

`llm/prompts.py` owns explanation/follow-up prompt builders for concept, math,
algorithm, contextual, follow-up, and selection-to-LaTeX tasks. Each builder accepts
`ResearchContext` and returns `list[ChatMessage]`.

Treat paper text and conversation history as untrusted data:

- delimit paper material inside `<paper_context>...</paper_context>`;
- state in the system prompt that the enclosed text is data, not instructions;
- treat prior model responses as data as well;
- never give a prompt unrestricted file, tool, or execution authority. T5-A dispatches
  only its fixed read-only actions; T5-B1 model output is an untrusted replacement
  proposal and cannot write until the application use case receives explicit consent.

## LLM Boundary

Application code depends on the protocol, never a concrete SDK client:

```python
class LlmProvider(Protocol):
    def complete(self, messages: list[ChatMessage], **kwargs: object) -> str: ...
```

- Construct providers in `llm/factory.py` from typed configuration.
- V1's required implementation is `llm/providers/openai_compatible.py`, covering OpenAI-compatible remote services and local endpoints such as Ollama.
- Add `AnthropicProvider` only when requested and its dependency is justified.
- Keep retry, timeout, SDK calls, and provider-error mapping inside the provider boundary.
- Parse responses centrally; map empty or malformed responses to `LlmBadResponseError` and API failures to `LlmApiError`.
- `llm/latex.py` accepts exactly one bounded `<latex>...</latex>` expression body.
  Reject display delimiters, document commands, macro definitions, links, file I/O,
  external resources, and unsupported environments before UI rendering or capture.
- A new provider normally requires its implementation plus minimal factory/config registration; it must not change Domain or UI behavior.

## Translation Boundary

Translation answers “what does this text mean in another language?”; explanation answers “what does this mean in this paper?”. Keep them separate.

```python
class TranslationProvider(Protocol):
    def translate(self, text: str, target_language: str) -> str: ...
```

- Translation accepts selected text and target language, not PDF objects or a full `ResearchContext`.
- V1 has exactly one implementation: `translation/providers/llm_translation.py`, reusing `LlmProvider`.
- Keep its translation prompt within the translation provider and apply the same untrusted-input defense.
- Map provider failures to `TranslationError` at the translation boundary.
- Do not build multi-provider selection machinery until a second implementation is requested.

## PDF Boundary

- Keep every PyMuPDF import and operation inside `pdf/`.
- Validate file extension, PDF magic bytes, existence, and the configured size limit (50 MB by default) before parsing.
- Return document/page/block models and page-image data; never leak PyMuPDF objects into UI or Domain APIs.
- Convert missing, corrupt, or unreadable file failures to project-defined PDF exceptions such as `PdfExtractionError`.
- Preserve the V1 page-image + extracted-text-panel approach. Page-level highlighting,
  OCR, table recognition, automatic page-wide formula recognition, and image-formula
  conversion remain out of scope. The V1.3.2 LaTeX use case operates only on a
  user-confirmed text selection and does not change PDF extraction.

## Knowledge and Obsidian Boundary

- `capture_knowledge` assembles source text, translation, validated LaTeX, selected
  questions/answers, user notes, tags, and provenance into `KnowledgeNote`.
- `integration/obsidian/markdown.py` renders readable, traceable Markdown containing document title, author, page number, and source quote.
- `integration/obsidian/vault.py` is the only Vault writer.
- Read the Vault path and output subdirectory from config, add the date prefix, sanitize filenames, reject traversal, write only `.md`, append a sequence for collisions, and never overwrite existing notes.
- Surface configuration and I/O failures; do not silently discard knowledge.

## Configuration, Errors, and Privacy

- Only `config.py` reads environment variables or Streamlit secrets. Pass typed settings to consumers.
- Never hardcode, log, commit, or include API keys in exceptions. Do not log complete LLM request payloads.
- Never execute LLM-produced LaTeX or pass it to a shell/compiler. Render only the
  validated expression through Streamlit and emit it as bounded display math in
  Markdown.
- Never import, eval, exec, test, or install dependencies for an opened code project.
  Standard-library AST is a parse boundary, not execution authority. The only source
  write is `code/change_writer.py`: one validated selected UTF-8 Python range, exact
  source-hash match, recovery copy, atomic replacement, and external-edit-safe
  rollback after separate user confirmations. It must reject absolute/traversal paths,
  symlinks, stale index/source, non-ordinary files, budget/syntax failures, and never
  delete the recovery artifact.
- Diagnostics may coordinate configuration and Vault validation but must not read
  environment values outside `config.py`, call a provider, expose keys/absolute Vault
  paths, or mutate directories.
- Backup/restore stays inside `integration/obsidian/`: archive only ordinary `.md`,
  validate manifest/path/size/hash before writes, stage locally, and reject any
  existing destination rather than merging.
- Keep local paper processing free of telemetry; only a user-invoked configured LLM/translation call sends the minimum required context over the network.
- Catch expected exceptions at the boundary that understands them. Never use bare `except:` or `except Exception: pass`.
- Unexpected failures should retain useful non-secret context and reach the UI as understandable errors.

## Code Quality

- Type all public functions and non-trivial internals.
- Give each function one responsibility and a concrete name.
- Split modules by ownership when they become hard to understand; do not split solely to meet a line-count rule.
- Prefer explicit control flow over metaprogramming, service locators, plugin frameworks, or premature generalization.
- Add comments for intent and constraints, not narration of obvious syntax.

## Finish Check

Before handing off a code change, confirm that UI calls only use cases, Domain stays
pure, models use current names, explanation and LaTeX conversion are
ResearchContext-grounded, translation is independent, LaTeX is validated and never
executed, evidence links keep both locators and an honest generation method, Vault
writes are isolated and non-overwriting, secrets/config are
  centralized, any T5-B1 write keeps its one-range confirmation/recovery/conflict
  guarantees, third-party types do not escape their boundary, the change is limited to
an approved current scope, errors are explicit, dependencies are justified, and the
relevant regression tests were actually run under the `testing-review` workflow.
