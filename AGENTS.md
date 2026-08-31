# ResearchMind Development Rules

Global development rules for ResearchMind. `docs/ARCHITECTURE.md` is the source of
truth for the currently implemented product boundary, module ownership, data flow,
and technical choices. `V1 to V2过渡要求.md` governs future transition stages and
their entry/exit gates; it does not override current architecture or authorize a
planned feature by itself. If an older product or planning document conflicts with
the architecture, follow `docs/ARCHITECTURE.md` for current code and report the
inconsistency instead of silently combining designs.

Task-specific guidance lives in `.agents/skills/`.

## Product Direction

ResearchMind is an AI-powered research reading and knowledge capture workspace. Its core value is helping a researcher understand a paper and turn that understanding into durable knowledge.

It connects the workflow represented by Zotero → ResearchMind → Obsidian:

- Zotero owns literature and metadata management. ResearchMind does not replace it.
- ResearchMind owns local PDF reading, text selection, translation, context-grounded AI explanation, follow-up conversation, and knowledge capture.
- Obsidian owns long-term knowledge management. ResearchMind generates traceable Markdown and writes it to the user's Vault; it does not build a competing knowledge system.

Long-term direction: connect **Paper ↔ Mathematics ↔ Code ↔ Notes**. V1.3.2
advances Paper ↔ Mathematics ↔ Notes through selection-driven,
ResearchContext-grounded LaTeX conversion. Completed T3 adds one separately selected,
read-only Python `CodeContext` source. Completed T4 adds explicit, user-confirmed
paper/mathematics/algorithm-to-code evidence links that can be captured in a
`KnowledgeNote` and exported to Obsidian. It does not automatically associate sources,
merge paper and code prompts, or authorize OCR or code execution/writes. Completed
T5-A adds only three current-session, no-argument, read-only evidence tools with
user-confirmed continuation; it does not authorize background autonomy or T5-B
write/execute tools. Completed T6-A makes Code a peer top-level workspace that works
without an opened PDF and presents separate beginner-learning and static-reproduction
goals. This improves navigation and explanation only; it does not add dependency
installation, shell/test execution, source writes, or reproduction guarantees.
Completed T6-B adds explicit local configuration diagnostics plus verified,
Markdown-only backup and restore into a new Vault subdirectory. Diagnostics never
call the network or expose credentials/absolute Vault paths; backup does not include
secrets, PDFs, code, images, or arbitrary Vault data.
T6-C is Completed: automated privacy, dependency-vulnerability, performance, and
error-recovery evidence passed, and the user explicitly confirmed the manual T6-C
gate. The earlier browser-control runtime failure remains recorded rather than being
rewritten as automated evidence. Completed T5-B1 adds exactly one source-write
capability: a model may propose replacement text for the current selected range in
one existing indexed Python file; the user must inspect a diff and separately confirm
apply or rollback. Recovery copies, raw SHA-256 conflicts, syntax/size/changed-line
limits, atomic replacement, and session-only metadata audit are mandatory. T5-B1
does not authorize Shell, tests, imports, execution, installation, Git, arbitrary
paths, multiple files, source creation/deletion/rename, or autonomous loops.
Completed T6-D freezes local internal version `2.0.0rc1` and adds one optional
Code-to-Obsidian capture path before the freeze: the current verified `CodeSelection`,
current question, selection-bound explanation, user notes, and tags can be previewed
as code-specific Markdown and explicitly saved through the existing non-overwriting
Vault writer. It stores project name plus relative path/line/symbol provenance, never
the absolute code root, and grants no source-write or execution authority.

## Current Development Stage

ResearchMind has a working and automatically verified V1.3.2 internal baseline. It is
in **V1 Optimization / V2 Preparation**, not initial V1 construction and not a public
release stage.

The current baseline already includes PDF reading/search, copy-friendly text blocks,
selection location, translation, ResearchContext-grounded explanation/follow-up,
context evidence preview, conservative formula text candidates, constrained
selection-to-LaTeX, KnowledgeNote, and non-overwriting Obsidian Markdown export.

T0 through T5, T5-B1, and T6-A/T6-B/T6-C completed by 2026-08-30. The current incremental baseline includes a
versioned real-paper corpus, one-click text/formula block selection, page/block/bbox
provenance through ResearchContext and KnowledgeNote, a five-document PDF evidence
spike, and the approved local-folder/Python-first CodeContext slice. The T3 slice
indexes at most 2,000 Python files / 20 MB / 1 MB per file, uses standard-library AST
without import or execution, preserves relative-path/line/symbol provenance, previews
the bounded request, and keeps state in memory. T4 links one located PDF selection to
one current CodeSelection only after an explicit user action; every link records both
locators, relation, confidence, and generation method, remains in memory, and becomes
durable only inside exported Markdown. T5-A lets a model request only the current
paper context, current code context, or current evidence links, one step per explicit
user click, with 3-tool/4-LLM limits, strict text actions, visible pending results,
session-only metadata audit, and no write/execute authority. T6-A retains Streamlit,
one Python process, and in-memory state while adding three peer workspaces. Its code
workspace works without a PDF, offers beginner and static-reproduction goals, and
derives a `CodeProjectSummary` from the already indexed project without additional
file reads or execution. T6-B adds `ConfigurationReport`, explicit Streamlit/CLI
diagnostics, manifest/SHA-256 Markdown archives, prevalidated non-overwriting restore,
and verified clean-install/current-wheel/baseline-wheel cycles. T6-C adds only an
evaluation harness and evidence: source-ownership/security review, dependency audit,
bounded synthetic performance measurements, restart recovery, and a user-confirmed
manual gate with the earlier automated-browser block retained. T5-B1 adds strict
proposal parsing, pure candidate/diff validation, the narrow `code/change_writer.py`
boundary, explicit application-layer confirmation, recovery and safe rollback,
without execution authority. T6-D is Completed as local internal release-candidate
closure at `2.0.0rc1`; no package upload, public release, remote push, or public tag
is authorized. Its package, installed launcher, diagnostics, recovery, security,
and repeated performance checks passed. The user explicitly confirmed the paper,
independent-code, and T5-B1 manual journeys on 2026-08-31. The verified source baseline
is 269 passing tests with one
environment skip for symlink creation and no broken installed
requirements and no known audited dependency vulnerabilities after upgrading the
local virtual environment to pip 26.2.1.
Planned OCR, automatic Paper ↔ Code association, persistence, UI replacement, or
additional tool-using assistants require
the preceding gate to close and, where applicable, a specific architecture or
permission decision. Blanket roadmap approval does not choose code sources, UI,
persistence, or write/execute authority.

Current optimization order:

1. continue ResearchContext, CodeContext, T5-A answer-quality, and T6-A beginner/
   reproduction usability evaluation;
2. evaluate T4 link usefulness and provenance on representative paper/code pairs;
3. run T5-B1 with representative disposable Python projects and improve only from
   observed proposal/diff/recovery usability or safety failures;
4. evaluate persistence only if real cross-session use demonstrates the need;
5. run the scoped CCv2 spike for PDF-reader-region mouse-wheel page changes without
   hijacking ordinary page scrolling;
6. if execution becomes necessary, obtain a separate T5-BX sandbox Spike decision.

The user-requested Code → Obsidian note flow is implemented in the internal candidate.
PDF-reader-region mouse-wheel page changes remain a scoped CCv2 spike candidate with
debounce/no-scroll-hijack checks; they are not implemented current scope.

## V1 Architecture

- Use Python 3.12, Streamlit, PyMuPDF, an OpenAI-compatible LLM provider, python-dotenv, and pytest as defined in `docs/ARCHITECTURE.md`. Re-evaluating a chosen technology is an architecture decision, not an ordinary implementation detail.
- Keep one local Python application. No microservices, Kubernetes, Redis, Celery, message queues, separate backend service, or distributed infrastructure.
- V1 has no database or ORM. Opened documents and conversations live in memory; Markdown files in the user's Obsidian Vault are the persistence layer.
- If cross-session conversations, a persistent paper library, or pre-export note management becomes a real requirement, evaluate standard-library SQLite first. Do not add a database server.
- Keep the src-layout and module ownership defined in the architecture: `app/`, `core/`, `models/`, `pdf/`, `code/`, `llm/`, `translation/`, `integration/obsidian/`, and the narrow T6-B `maintenance.py` entry.
- Prefer explicit functions, dataclasses, type hints, and small modules that a beginner/intermediate Python developer can follow.
- Do not build speculative frameworks or extension points. Preserve the small interfaces already justified by present needs: `LlmProvider` and `TranslationProvider`.
- Use Streamlit's built-in math rendering and Obsidian display-math Markdown for
  validated expressions. Do not add TeX Live, a subprocess compiler, or another
  runtime dependency unless a separately approved requirement needs TeX documents
  rather than formula preview.

## Module and Dependency Rules

- `app/views/` displays data and delegates events. It accesses product behavior only through `app/use_cases.py`.
- `app/state.py` is the only place that mutates Streamlit session state.
- `app/use_cases.py` is the application API. It coordinates domain rules and infrastructure; V1 has no REST API or separate backend.
- `core/` contains pure, framework-independent rules for ResearchContext and
  CodeContext assembly, `CodeProjectSummary` derivation, explicit evidence links,
  T5-A session/budget transitions, T5-B1 candidate/diff/hash/limit validation,
  selection location, and conversation trimming.
- `models/` contains shared dataclasses and imports no project layer.
- `pdf/`, `code/`, `llm/`, `translation/`, `integration/obsidian/`, and `config.py`
  own external libraries, APIs, files, and configuration boundaries.
- PDF code never calls LLM, translation, or Obsidian code. Translation accepts text, not PDF objects.
- `code/` is default-read-only infrastructure. Its reader applies the approved
  exclusions and limits, reads UTF-8 Python source, and converts standard-library AST
  results to project models. The only source writer is `code/change_writer.py`, which
  may modify one current selected existing `.py` only after an application-layer
  confirmation, recovery copy, and raw SHA-256 check. It never imports, executes,
  tests, installs, creates/deletes/renames source, or performs multi-file writes.
- Every explanation and follow-up must be grounded in a freshly assembled `ResearchContext`. Do not send an entire PDF to an LLM without a task-bounded context.
- Selection-to-LaTeX conversion is also LLM-backed and must use a freshly assembled
  `ResearchContext`. `llm/prompts.py` owns its prompt, `llm/latex.py` owns strict
  response parsing, and `app/use_cases.py` owns orchestration.
- Code explanation must use a freshly assembled bounded `CodeContext`.
  `ResearchContext` and `CodeContext` remain separate; T4 links provenance but does
  not combine paper and code prompts. `llm/prompts.py` owns `<code_context>`
  serialization and
  `app/use_cases.py` owns orchestration.
- Evidence links are project-owned dataclasses created by pure `core/` rules. The
  production T4 path creates only `user_confirmed` links from one located PDF
  `ReadingSelection` to one verified `CodeSelection`. Deterministic or model-inferred
  origins may be represented but must remain visibly labeled and cannot be generated
  by this user-confirmed path.
- Translation and AI explanation are separate product capabilities. V1 translation uses `LlmTranslationProvider`, but it has its own interface, use case, errors, and UI action.
- `capture_knowledge` assembles a `KnowledgeNote`, including a copy of current
  evidence links; Markdown rendering and file writing remain Obsidian integration
  responsibilities.
- `capture_code_knowledge` validates that the current `CodeSelection` still belongs
  to the indexed project and source, accepts only a selection-bound `explain:code`
  response plus the question that produced it, and creates a code-shaped
  `KnowledgeNote`. Code-note rendering uses
  project name, relative path, line range, symbol/extraction method and an indented
  code block; it never emits PDF page fields or the absolute project root.
- `integration/obsidian/` is the only module allowed to write to the Vault. It writes traceable, plain-text `.md` files and never overwrites an existing note.
- `maintenance.py` coordinates explicit local diagnose/backup/restore commands. It
  reads settings only through `config.py` and delegates Vault inspection/writes to
  `integration/obsidian/`; it is not a generic shell or migration framework.
- Zotero is optional future integration. V1 core behavior must not import or depend on Zotero code.

## Security and User Data

- `config.py` is the only module that reads environment variables or Streamlit secrets. Never hardcode, commit, return, or log secrets or full sensitive request payloads.
- Keep `.env` and other secret files ignored; provide only placeholders in `.env.example`.
- Configuration reports may state whether a Key/model/Vault is configured but never
  contain credential values or absolute Vault paths. Diagnostics do not call the
  provider, create directories, or prove API connectivity.
- Treat PDF text, code source, and conversation history as untrusted data. LLM prompts
  delimit paper content with `<paper_context>` and code with `<code_context>`, and
  explicitly state that enclosed material is data, not instructions.
- Treat LLM-produced LaTeX as untrusted output. Accept one bounded expression body,
  reject display delimiters, document commands, macro definitions, links, file I/O,
  external resources, and unsupported environments before rendering or persistence.
- Validate PDF extension, magic bytes, and the configured size limit (50 MB by default). Convert parsing failures to project exceptions at the PDF boundary.
- Keep local paper processing free of telemetry. Network transfer occurs only when the user invokes the configured LLM-backed explanation or translation capability.
- Send only the selected text, minimal relevant surrounding context, necessary document metadata, the current question, and budgeted history to the configured LLM service. Make this external transfer visible to the user.
- For code explanation, send only the user-selected code, bounded neighboring lines,
  relative path/line/symbol provenance, and current question after a visible preview.
  Never send the absolute project path or entire repository by default.
- Exclude hidden/VCS/environment/cache/build/vendor directories and known secret-file
  names from code indexing. Do not follow symlinks outside the selected root. Code
  stays in memory by default and is never executed. T5-B1 is the only modification
  path: exact selected file/range, one strict replacement, diff, per-action consent,
  `.researchmind-recovery/`, atomic replace, and external-edit-safe rollback.
- Evidence links never trigger an LLM call. Preserve both source locators, relation,
  confidence, and generation method; never relabel model inference as user-confirmed
  or deterministic fact.
- T5-A exposes only `inspect_paper_context`, `inspect_code_context`, and
  `inspect_evidence_links`. They accept no model arguments, read only current session
  objects through use cases, and never open arbitrary paths. Each new provider call
  requires a user click; enforce 3 tool / 4 LLM and character budgets, reject unknown
  or repeated actions, escape tool results as untrusted data, and keep audit payloads
  to metadata only.
- T5-B1 uses a separate strict `<replacement>` protocol. Reject wrapper expansion,
  paths/commands/multiple actions, blank/NUL/over-20,000-character output, more than
  400 changed lines, over-1-MiB candidates, stale selection/index/source, invalid
  UTF-8/Python, symlinks, traversal, and hash conflicts before a source mutation.
  Proposal generation never writes. Apply and rollback each require a fresh user
  confirmation through `app/use_cases.py`; audit is session-only metadata without
  source, request text, absolute root, or API Key.
- Code-note preview and Vault save are separate explicit actions. Re-selection,
  re-explanation, apply, or rollback invalidates the preview. Saving uses only the
  existing Obsidian Markdown writer and does not call an LLM or write code source.
- Vault paths come from configuration. Prefix filenames with the date, sanitize them, restrict output to Markdown, prevent path traversal and overwrite, and surface write failures.
- T6-B targeted backups include only ordinary Markdown under the configured
  ResearchMind output directory plus a versioned manifest with relative paths, sizes,
  and SHA-256. Reject symlinks, traversal, duplicate/encrypted/unsupported members,
  manifest/size/hash mismatch, and resource-limit violations before restore writes.
- Restore only to an absent subdirectory with an existing parent, stage inside the
  Vault, and rename after validation. Never merge or overwrite existing notes.

## Preserve Working V1

- Treat the verified V1.3.2 loop as a regression baseline. Optimize incrementally and
  preserve unrelated working behavior.
- Do not rewrite stable code for aesthetic reasons, replace a major framework without
  evidence, reorganize the whole repository, add complex infrastructure, or combine
  unrelated refactors with one optimization.
- Before a large or risky change, state the concrete problem, current and expected
  behavior, affected modules, risks, test and regression plan, rollback, and
  definition of done.
- Keep changes understandable to a single learning developer. Avoid speculative
  abstractions and enterprise-scale process that the personal local application does
  not need.

## Optimization-first Development

Classify work as a bug fix, optimization, spike, new feature, or architecture
decision. For non-trivial optimization, follow:

```text
observe → define → measure → compare → improve → verify
```

Record a before/after criterion that measures the user problem rather than only
checking that code runs. Prefer a smaller solution when it meets the criterion.
Future-work ideas stay outside the active change.

## Spike Before Major Dependency

- Evaluate major candidate technologies in an isolated `experiments/` spike before
  they enter production code. This includes OpenDataLoader-PDF, Docling, Marker,
  OCR/new PDF engines, Zotero/VS Code integrations, persistence systems, embedding or
  RAG frameworks, and agent tool runtimes.
- A spike answers a named technical question and records representative inputs,
  output quality, performance/memory, Windows/local deployment, privacy/network
  behavior, dependency/license/maintenance cost, integration effort, and impact on
  V1. It is not a production feature.
- Adoption requires evidence and an approved architecture change when it affects the
  selected stack or module boundaries.

## External Dependency Boundary

- Third-party libraries provide capability; ResearchMind owns its domain models and
  error semantics. Convert vendor outputs at their infrastructure boundary.
- Do not let PyMuPDF objects, parser-specific JSON/elements, LLM SDK responses, or
  translation SDK responses propagate through Core, UI, or persistence.
- OpenDataLoader-PDF remains a candidate/reference, not a project dependency, until an
  isolated spike and explicit adoption decision say otherwise.

## Development Workflow

- Inspect the relevant source, tests, `docs/ARCHITECTURE.md`, and project skills before modifying code.
- For transition work, inspect `V1 to V2过渡要求.md` and verify that the requested
  phase is approved; a roadmap entry alone is not permission to implement it.
- Make the smallest coherent change and preserve unrelated user work.
- Do not implement unrequested V1 or future features.
- Explain new dependencies before adding them and prefer the standard library or an existing dependency.
- Explain and obtain confirmation before changing an established architecture choice, such as the UI framework, persistence model, module boundaries, or process topology. Ordinary feature work that fits the architecture does not require a separate confirmation gate.
- When documentation disagrees with the architecture, flag it and keep the current task scoped unless the user asked for broader documentation synchronization.
- After an important change, explain the actual data flow, key Python/software
  engineering ideas, important limitations, and 3–5 useful files for the learning
  developer to read.

## Testing

- Regression-first: every change must protect the existing
  open → read/search/select → translate/LaTeX/explain → follow-up → KnowledgeNote →
  Markdown → Vault loop to the degree affected by the change.
- Add tests for new behavior. For a bug, reproduce it with a regression test before fixing it.
- After code changes, run the relevant unit tests and any affected integration or Streamlit smoke tests.
- Use fake or mocked LLM/translation providers in automated tests; never spend user money or depend on live network services in the routine suite.
- Test LaTeX prompts, strict parsing, rejected TeX capabilities, UI rendering, and
  Obsidian display-math output with fake providers; never invoke a TeX compiler in
  routine V1.3.2 tests.
- Test evidence-link locator validation, duplicate protection, generation labels,
  session behavior, KnowledgeNote copying, and Obsidian Markdown export without a
  network provider.
- Test that the code workspace opens without a PDF, both T6-A goals remain available,
  static project summaries omit absolute paths, and navigation preserves the
  established paper and assistant flows.
- Test Code-to-Obsidian capture for current-selection/source ownership, stale-response
  and question rejection, relative locator rendering, absolute-root omission,
  preview-before-save,
  selection/change invalidation, temporary-Vault non-overwrite, and unchanged PDF
  KnowledgeNote Markdown.
- Test T6-B diagnostics for optional warnings, invalid configuration, no secret/path
  leakage, no directory creation, and explicit Streamlit execution. Test backup/
  restore manifests, checksums, traversal/tampering rejection, resource bounds,
  absent-target enforcement, CLI behavior, and unchanged existing notes in temp
  Vaults only.
- Test T5-A strict actions, prompt injection, fixed tool availability, repeated/unknown
  requests, call/output budgets, provider/tool errors, user stop, state invalidation,
  and Streamlit start/continue behavior with fake providers.
- Test T5-B1 strict protocol/injection, selection and project ownership, line/size/
  syntax limits, no-confirmation and cancel zero writes, relative diff/no absolute
  path leakage, recovery non-overwrite, atomic failure, stale hashes, symlink/path
  rejection, external-edit-safe rollback, metadata-only audit, and Streamlit apply/
  rollback with fake providers and disposable projects only. Never execute the code.
- Review the final diff or, when Git metadata is unavailable, re-read every changed file and compare it with the source requirements.
- Never claim behavior works without running the relevant tests. Report exact commands, real results, skipped checks, and unrelated failures honestly.
- Treat API connectivity and research-answer/context quality as different checks. An
  HTTP success is not evidence that ResearchContext is relevant or the answer is
  traceable.

## Project Skills

- `project-planner` — classify and scope V1.3.2 optimization or approved transition
  work, choose spikes, and define before/after evidence and completion.
- `python-engineering` — implement incremental Python changes while preserving module,
  project-model, dependency, and error boundaries.
- `testing-review` — verify regressions, integrations, evaluations, and completion
  claims against the working V1.3.2 loop.
- `learning-mode` — explain important features and trade-offs from actual implemented
  code while distinguishing current, experimental, and planned behavior.
- `pdf-research` — guide PDF viewer/parser decisions, extraction-quality evaluation,
  and isolated PDF technology spikes.
- `research-context` — guide Selection, context assembly, prompt-input boundaries,
  provenance, budgets, and ResearchContext quality evaluation.

Do not create additional domain skills merely because a future area is mentioned.
Add one only after the area has a distinct, stable, repeated workflow that cannot be
expressed clearly by these six.

## Current Implemented Scope: 2.0.0rc1 Local Internal Candidate

V1 implements only:

1. Open and read local PDFs: page rendering, navigation, zoom, and text search.
2. Extract page text and text blocks.
3. Select or enter text and locate it when possible.
4. Translate selected text through the independent Translation module.
5. Explain concepts, mathematics, algorithms, or paper context through ResearchContext.
6. Convert user-selected mathematical text into a constrained LaTeX expression through
   the configured LLM, preview it locally, and keep the source selection traceable.
7. Ask follow-up questions within an in-memory per-document conversation.
8. Capture selected source, translation, validated LaTeX, questions, AI explanation,
   and the user's own understanding as a `KnowledgeNote`.
9. Render traceable Markdown, including optional display math, and save it to the
   user's Obsidian Vault.
10. Open one explicitly selected local folder and statically index bounded UTF-8
    Python source using the standard-library AST.
11. Select a Python symbol or line range with relative-path/line provenance, preview
    a bounded `CodeContext`, and explicitly request a non-executing AI explanation.
12. Explicitly confirm a link from one located paper, mathematics, or algorithm
    selection to one code selection; keep the link in session memory and include its
    relation, confidence, generation method, and both locators in KnowledgeNote
    Markdown.
13. Ask one current-session research question through the T5-A assistant, which can
    request only current bounded paper context, current bounded code context, or
    current evidence links; show each result before the user explicitly continues,
    enforce 3-tool/4-LLM budgets, and keep the final answer/session audit separate
    from Conversation, KnowledgeNote, Vault, and code.
14. Enter a peer code workspace without opening a PDF, choose a beginner-learning or
    static-reproduction goal, inspect an in-memory `CodeProjectSummary`, and continue
    through the existing bounded selection/preview/non-executing explanation path.
    Entry points, imports, third-party dependencies, and problem files are static
    candidates, not evidence that the project has run or can be reproduced.
15. Explicitly run a local, non-network configuration report and create/verify a
    Markdown-only ResearchMind backup. Restore a valid archive only into a new Vault
    subdirectory after manifest, path, size, and SHA-256 checks; never include secrets
    or overwrite existing data.
16. For the current `CodeSelection` only, explicitly request one bounded Python
    replacement proposal, inspect its relative-path unified diff, and separately
    confirm apply or rollback with a recovery copy and SHA-256 conflict protection.
    This does not execute code, tests, Shell, installers, Git, or multiple files.
17. From the independent code workspace, explicitly preview and save one current
    code selection as code-specific Obsidian Markdown with project name, relative
    path, line/symbol provenance, current question, optional bound explanation, user
    notes, and tags. This does not require a PDF, expose the absolute root, call a
    model, modify source, or create a code-note database.

Do not implement in V1 unless explicitly requested:

- Zotero API integration or replacement of Zotero/Obsidian functionality
- SQLite, another database, ORM, or cross-session persistence
- PDF annotation, highlighting, bookmarks, OCR, image/table recognition, automatic
  page-wide formula recognition, image-formula-to-LaTeX conversion, or PDF editing
- arbitrary TeX document compilation, user-defined macros, file/network access from
  LaTeX, or treating LLM reconstruction as ground truth
- VS Code, browser, or mobile extensions
- automatic Paper ↔ Code links; code generation/modification beyond T5-B1's current
  selected existing Python range; dependency installation, test/shell execution, or
  any additional code tool authority without a separate permission/sandbox decision
- advanced RAG, vector databases, cross-paper search, or knowledge graphs
- multi-user collaboration, cloud deployment/sync, complex authentication, background
  autonomous workflows, arbitrary write agents, or unapproved T5-BX execution agents
