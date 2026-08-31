---
name: project-planner
description: Classify and plan meaningful ResearchMind V1.3.2 optimizations, spikes, approved V1-to-V2 transition slices, and architecture decisions. Use for cross-module work, major dependencies, measurable UX or quality changes, or materially ambiguous scope; skip trivial contained edits and unapproved future implementation.
---

# Project Planner

Plan the smallest coherent change that advances ResearchMind's research-reading and knowledge-capture workflow while preserving the verified V1.3.2 baseline. Use `docs/ARCHITECTURE.md` as the source of truth for current behavior. For explicit transition work, also read `V1 to V2过渡要求.md`; its roadmap requires an approved stage before implementation.

Current gate (2026-08-31): T5-A/T5-B1 and T6-A–T6-D are completed at the local
internal `2.0.0rc1` / `269 passed, 1 skipped` source baseline. The installed launcher,
diagnostics, recovery, security, bounded code-index performance, and user-confirmed
paper/independent-code/T5-B1 journeys passed. Code → Obsidian is now implemented as
an explicit preview/save path for the current verified selection with relative
path/line/symbol provenance; it has no execution or source-write authority. PDF
reader-region mouse-wheel interaction remains a scoped CCv2 spike candidate. No
package upload or public release is authorized. T3 implements one bounded
local-folder, Python-first, read-only CodeContext with file/line/symbol provenance,
standard-library AST, an evidence preview, and no execution/write authority. T4
adds user-confirmed, in-memory paper/mathematics/algorithm-to-code links with both
locators, relation, confidence, generation method, and KnowledgeNote export. T5-A
implements only three current-session, no-argument read-only evidence tools, one model
step per user click, strict action parsing, hard budgets, and metadata-only audit.
T6-A retains Streamlit, a single process, and in-memory state while making Code a
peer workspace that requires no PDF and offers beginner-learning and
static-reproduction goals backed by `CodeProjectSummary`. T6-B adds explicit
non-network configuration diagnostics, Markdown-only manifest/SHA-256 backup,
restore into an absent Vault subdirectory, and clean-install/wheel rollback evidence.
T6-C automated privacy, dependency-vulnerability, performance, restart/error-recovery,
and regression gates passed; the user explicitly confirmed its desktop/narrow-window
manual checklist. Record that as user-confirmed manual evidence, not automated browser
evidence. T5-B1 implements only one selected Python line-range replacement with a
relative-path diff, per-action consent, recovery copy, SHA-256 conflict checks, atomic
apply, external-edit-safe rollback, and metadata-only audit. Shell, tests, dependency
installation, arbitrary paths, multi-file changes, and background execution remain
unapproved T5-BX scope.

## Product Test

Start by identifying where the request fits this loop:

```text
local PDF → reading/selection → translation, constrained LaTeX, or ResearchContext-grounded AI
→ follow-up conversation → KnowledgeNote → Markdown → Obsidian Vault
```

Completed T3/T6-A also have a deliberately separate, non-persistent path:

```text
choose the Code workspace without a PDF → one local folder → static Python index
→ beginner or static-reproduction goal → project summary → explicit CodeSelection
→ bounded CodeContext preview → non-executing code explanation
→ optional code KnowledgeNote preview → explicit Obsidian Markdown save
```

T4 may connect the provenance of these paths through an `EvidenceLink`, but does not
combine their LLM prompts. Plan any joint explanation as a separate future use case
with its own budget and evaluation.

T5-A may inspect those sources sequentially, but only through the approved fixed
tools. T5-B1 adds a separate, explicit propose → diff preview → confirm → recover →
atomic apply/rollback path for one selected Python range. It is not permission for
arbitrary source access, automatic links, background loops, shell/tests, dependency
installation, Vault writes, or multi-file edits. Read
`docs/T5_B_PERMISSION_DECISION.md` and
`docs/T5_B1_CONTROLLED_CODE_WRITE_VALIDATION.md` before planning adjacent work; obtain
a separate T5-BX decision before any execution authority.

Treat T6-A reproduction support as static orientation, not proof of reproducibility.
Any plan that reads new manifest/config/data documentation, installs dependencies, or
runs code/tests is separate scope. A source fix may use T5-B1 only when it is exactly
one current selected Python range and satisfies its full confirmation/recovery
contract; anything broader needs a new permission decision.

Treat T6-B backup as a targeted supplement to whole-Vault backup, not a general Vault
sync or migration system. Plans must preserve its Markdown-only, no-secret,
prevalidated, absent-target, non-overwriting contract. Package rollback does not
authorize reverting or rewriting user data.

The PDF reader is an entry point, not the whole product. The durable outcome is traceable knowledge in the user's Obsidian Vault. Zotero owns literature management and Obsidian owns long-term knowledge organization; plans must not quietly reproduce either product.

The long-term Paper ↔ Mathematics ↔ Code ↔ Notes direction is context, not blanket
V1 scope. V1.3.2 includes only selection-driven LaTeX conversion grounded in the
current ResearchContext and persisted with provenance. Distinguish it from image
formula OCR, page-wide recognition, TeX document compilation, automatic Paper ↔ Code
discovery, and joint paper/code prompting, which remain future work.

## Optimization Stage Rules

Classify the task before planning:

- **bug fix**: demonstrated behavior violates the current contract;
- **optimization**: current behavior works but has a measurable user or quality cost;
- **spike**: an isolated experiment that answers a dependency or architecture question;
- **new feature**: a new user capability within an approved scope;
- **architecture decision**: changes framework, persistence, process topology, public
  contracts, module boundaries, or tool authority.

V1.3.2 optimization uses:

```text
preserve → observe → measure → improve → verify
```

Before proposing implementation, state:

- **Problem** and the affected user workflow;
- **Current behavior** with evidence;
- **Expected behavior** and a before/after measure;
- **Affected modules** and explicit exclusions;
- **Risk**, including regression and data/privacy risks;
- **Test plan**, rollback, and definition of done.

Prefer one independently testable slice. Do not combine a Selection improvement with
an unrelated parser, persistence, UI-framework, or provider rewrite. If the work
depends on OpenDataLoader-PDF, Docling, Marker, OCR, a new PDF engine, database,
editor integration, RAG framework, or tool runtime, plan an isolated `experiments/`
spike first unless an approved evidence record already exists.

## Planning Workflow

Before proposing implementation:

1. Inspect `AGENTS.md`, `docs/ARCHITECTURE.md`, relevant source, tests, dependency configuration, and any task-specific documentation. For transition tasks, confirm the roadmap stage and approval state.
2. Restate the user-visible outcome and identify ambiguities that would materially change the result.
3. Map the work to the current modules and reuse existing models, protocols, and use cases.
4. Trace the data from UI input through application orchestration, domain rules, infrastructure, and user-visible output or Vault persistence.
5. Define verification at the same time as implementation, including failure paths.
6. Exclude unrelated cleanup and future-scope ideas from the implementation; mention them separately only if they affect the decision.

Make reasonable assumptions for ordinary details and state them. Ask for user confirmation only when the plan would change an established architecture choice or when a missing choice materially changes product behavior. A feature that fits the documented architecture does not need a separate approval gate before implementation.

## Architecture Fit

Use these ownership rules when assigning changes:

- `app/views/`: display and event delegation only.
- `app/state.py`: the only Streamlit session-state mutation point.
- `app/use_cases.py`: application API and orchestration between domain and infrastructure.
- `core/`: pure ResearchContext/CodeContext, selection, evidence-link, and conversation rules.
- `models/`: shared dataclasses with no project-layer imports.
- `pdf/`: all PyMuPDF use, rendering, extraction, search, and PDF boundary errors.
- `code/`: approved T3 local-folder limits, exclusions, UTF-8 reads, standard-library
  AST conversion, and CodeProject errors. `code/change_writer.py` is the sole T5-B1
  source-writer exception and may replace only one validated selected Python range;
  no module imports or executes source, runs tests, or installs dependencies.
- `llm/`: provider protocol/factory, explanation and LaTeX prompts, constrained
  LaTeX response parsing, and LLM errors.
- `translation/`: independent text-to-text translation protocol, service, provider, and errors.
- `integration/obsidian/`: Markdown rendering and the only Vault write path.
- `config.py`: the only environment/secrets reader.

Important constraints:

- Explanation and follow-up use cases build a `ResearchContext` before calling the LLM.
- LaTeX conversion builds the same bounded `ResearchContext`, returns one validated
  expression body, and remains traceable to the current selection.
- Translation remains separate from explanation and accepts text rather than PDF objects.
- `capture_knowledge` assembles `KnowledgeNote`; Obsidian integration alone renders and writes it.
- Conversations and opened documents remain in memory in V1.
- Notes are saved as non-overwriting, traceable Markdown in the configured Vault.
- A formula-preview feature should reuse Streamlit math rendering and Obsidian
  display math. Adding TeX Live or a compiler is an architecture/dependency decision,
  not a default implementation step.
- The T3 CodeContext and PDF ResearchContext stay separate. T4 EvidenceLink connects
  source provenance only; it is not an implicit prompt merge or model-authored fact.
- The current baseline has no REST backend, database, ORM, Zotero integration,
  advanced RAG, vector store, executable/background agent, or general-purpose tool
  runtime.

## Plan Content

For a meaningful feature, give the user a concise plan covering:

- **Goal and scope:** the user problem, success condition, assumptions, and exclusions.
- **Classification and gate:** bug, optimization, spike, feature, or architecture
  decision; identify the active/approved transition stage when applicable.
- **Current fit:** reusable modules and behavior already present.
- **Changes:** files/modules to create or modify and the responsibility of each.
- **Data flow:** actual models and boundaries involved, including `ResearchContext` or `KnowledgeNote` when relevant.
- **Dependencies:** preferably none; justify any addition and identify the architecture decision if it changes the chosen stack.
- **Verification:** unit, integration, or Streamlit smoke checks plus important error cases.
- **Before/after:** the observable UX, quality, latency, accuracy, token, or reliability
  criterion that decides whether the change helped.
- **Risks:** data loss, privacy, prompt injection, PDF limitations, state/rerun behavior, and boundary violations that genuinely apply.
- **Order and rollback:** a small sequence that produces testable increments and can
  be abandoned without damaging the working baseline.

## Architecture Changes

Changing Streamlit, the no-database decision, process topology, persistence ownership, public use-case contracts, or major module boundaries is an architecture decision. Before making it:

1. Show the concrete requirement the current architecture cannot meet.
2. Compare the smallest viable alternatives and trade-offs.
3. Explain migration and testing impact.
4. Obtain user confirmation.

Do not present a large rewrite as ordinary feature work.

## Completion Check

A plan is ready when its classification and phase authority are explicit, the
user-visible problem and before/after measure are concrete, it fits the current loop,
module ownership and data flow are unambiguous, dependencies are justified,
regression and rollback are covered, and future work has not leaked into the active
scope.
