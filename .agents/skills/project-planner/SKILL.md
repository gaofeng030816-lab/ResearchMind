---
name: project-planner
description: Plan and gate ResearchMind V3 features, architecture decisions, dependency spikes, and cross-module changes while preserving the accepted V2 baseline. Use for persistence, Zotero, PDF interaction, formula recognition, multilingual code, adaptive UI, or any materially ambiguous slice; skip trivial contained fixes.
---

# Project Planner

Plan the smallest independently verifiable step toward ResearchMind V3. Preserve the
accepted 2.0.0rc1 V2 baseline and do not turn a roadmap entry into permission to
adopt a dependency or change architecture.

## Sources and Current Gate

- docs/ARCHITECTURE.md describes what is implemented now and remains the code
  source of truth.
- V2 to V3过渡要求.md describes approved V3 requirements, stage order, decision
  points, and entry/exit evidence.
- V1 to V2过渡要求.md and V2 validation records are historical baselines.

V3-G0 and V3-G1 are completed. G1 adopted standard-library sqlite3, explicit
RESEARCHMIND_DATA_DIR, managed PDF/Python assets, immutable revisions, separated
remove/delete, and verified backup/restore. Preserve that contract instead of
re-planning persistence from scratch. V3-G2 is Completed following the user's
2026-09-04 manual acceptance confirmation: GET-only metadata browsing and schema v2 source links are implemented.
The user approved single-PDF reads inside a configured attachment directory on
2026-09-04. Windows copying now uses /file/view/url, scoped consent, locked ancestor/
file handles, and G1 validation/storage. HTTP redirects remain rejected.
Manual evidence is the user's explicit acceptance, not agent-observed live execution.
G3 is Completed. After its isolated corpus, reconciliation, interaction, performance,
license and wheel evidence, the user reported physical-trackpad acceptance and
approved production CCv2/pdf.js adoption on 2026-09-07. The production path uses
hash-bound local bytes, a 10 MiB viewer limit, server-side PyMuPDF text/geometry
reconciliation, stale/duplicate rejection, and the V2 image/text fallback. Formal
Edge acceptance passed 8/8 with no page errors or external requests; the combined
regression is 486 passed / 1 environment skip. Read
docs/V3_G3_PDF_WORKSPACE_SPIKE.md before planning changes to that contract.
G4 is Completed following the user's 2026-09-09 manual acceptance. It implements
schema-v3 NoteDraft/EvidenceSnapshot persistence, exact transfer preview, click-only
translation, managed-source binding, an explicit persistent evidence basket, editable
Markdown, explicit local save, revision/SHA-256-bound preview and confirmed exact-byte
non-overwriting Vault output. Its final evidence is 42 focused checks, 425 production
tests / 1 environment skip, 524 tests / 1 skip with G3 experiments, and Edge 152 8/8
with no page errors or external requests. Read
docs/V3_G4_NOTE_COMPOSER_DECISION.md before changing this contract. G5 is Completed.
It adopted local revision-bound detection/crop, a provider-neutral FormulaRecognizer,
the configured OpenAI-compatible single-crop adapter, exact remote-transfer consent,
editable strict LaTeX and optional accepted-formula evidence. The legacy GPL runtime
was rejected and pix2tex/local weights remain deferred. Its low real normalized-exact
score forbids source-recovery claims. Read
docs/V3_G5_FORMULA_RECOGNITION_DECISION.md before changing this contract. G6 is
Completed under the user-approved hybrid scheme: Python AST, separate C/Java/Julia
Tree-sitter wheels, and a conservative R lexical adapter. Read
docs/V3_G6_MULTILINGUAL_CODE_DECISION.md before changing it. G7 and V3 internal
acceptance are Completed as 3.0.0rc1 following explicit user confirmation on
2026-09-21. No primary V3 gate is Active. Any later feature, public release, dependency
or permission expansion requires a new named gate. Read
docs/V3_G7_HARDENING_ACCEPTANCE.md. Zotero Web API/sync remains unapproved.

## Product Test

Place every request in this target loop:

    library/import
    → paper-only or paper+code workspace
    → explicit text/code/formula selection
    → translation or bounded AI explanation
    → user-chosen evidence basket
    → editable Markdown draft and preview
    → explicit non-overwriting Obsidian save

ResearchMind may maintain a local working library, but Zotero still owns literature
management and Obsidian still owns long-term notes. A V3 plan must not quietly rebuild
Zotero citation management or Obsidian knowledge organization.

## Classification

Classify the task before planning:

- **bug fix**: current implemented behavior violates its contract;
- **optimization**: implemented behavior has a measurable usability, quality, or
  performance cost;
- **spike**: isolated evidence for a dependency or interaction decision;
- **feature**: new behavior inside an already approved V3 stage and architecture;
- **architecture decision**: changes persistence, UI/component boundary, process
  topology, module ownership, public use-case contracts, external data ownership, or
  code authority.

Use observe → define → measure → compare → improve → verify for optimizations. Use a
spike before adding Zotero clients, PDF/OCR engines, formula models, Tree-sitter and
language grammars, or a new frontend/build chain.

## Planning Workflow

1. Read the current architecture, the active V3 gate, relevant source/tests, and the
   domain Skill.
2. State the user-visible outcome, current evidence, and what remains unchanged.
3. Trace data through View → use case → Core/models → infrastructure → persistence or
   external output.
4. Compare the smallest credible alternatives for every architecture choice.
5. Define fixtures, failure paths, privacy behavior, rollback, and completion evidence
   before implementation.
6. Keep one primary gate active; split unrelated persistence, PDF, formula, code, and
   UI changes.

## V3 Architecture Questions

Plans must explicitly answer the applicable questions:

- **Library:** Which data is durable, who owns files, how are duplicates detected,
  what is deletion versus unlinking, and how do migrations recover?
- **Zotero:** Local read-only API, Web API, or neither? How are server/library/item
  identities and stale versions represented without making Zotero mandatory?
- **Upload:** Browser uploads provide bytes and relative names, not a trusted original
  path. Where are validated files stored and how are limits enforced?
- **PDF interaction:** Does native Streamlit suffice, or is a CCv2/pdf.js text layer
  needed? How are selection text, page, spans/bboxes, scroll ownership, and debounce
  verified?
- **Formula:** Is the source digital text, a cropped image, or both? What metric and
  corpus justify a recognizer, and what user editing/acceptance step handles errors?
- **Code:** Which parser adapter covers each language, what parity is required with
  current Python behavior, and how is no-execution authority proved?
- **Notes:** Which evidence is explicitly selected, what is editable, what is stored
  locally, and when is the only Vault write allowed?
- **UI:** What does paper-only, paper+code, AI shortcut, and note-composer state look
  like on desktop and narrow screens?

## Plan Content

A meaningful plan includes:

- goal, stage/gate, assumptions, exclusions, and observable success;
- affected models/modules and dependency direction;
- actual input-to-output data flow and persistence lifetime;
- candidate dependencies and an isolated adoption test;
- unit, integration, Streamlit/AppTest, browser-manual, corpus-quality, security, and
  migration checks in proportion to the change;
- before/after metrics, failure UX, rollback, and evidence required to close the gate.

Do not bundle a SQLite schema, Zotero sync, new PDF component, formula provider, and
multi-language parser into one implementation step. Establish stable library IDs and
file ownership before features that persist selections, links, or drafts.

## Architecture Change Rule

Before changing Streamlit, the no-database V2 decision, module boundaries, process
topology, external file ownership, or code write/execute authority:

1. show the requirement the V2 architecture cannot meet;
2. compare the smallest alternatives and their migration/maintenance cost;
3. define regression and rollback impact;
4. obtain the specific gate confirmation recorded in V2 to V3过渡要求.md.

## Finish Check

A plan is ready when the active stage and permission are explicit, current and target
behavior are not confused, ownership and data lifetime are unambiguous, dependencies
are evidence-gated, privacy and deletion are addressed, verification is measurable,
and future stages have not leaked into the active slice.
