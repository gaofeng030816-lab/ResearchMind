# ResearchMind Development Rules

Global rules for ResearchMind. Task-specific workflows live in .agents/skills.

## Authority and Documents

- docs/ARCHITECTURE.md is the source of truth for currently implemented behavior,
  module ownership, data flow, and technical choices.
- V2 to V3过渡要求.md governs V3 requirements, stage order, architecture decisions,
  and entry/exit evidence. A roadmap entry does not by itself adopt a dependency or
  authorize a later stage.
- docs/PRODUCT_SPEC.md describes accepted V2 behavior until a V3 slice is implemented
  and verified.
- V1 to V2过渡要求.md and V1/V2 validation documents are historical records.
- If a planning document conflicts with current architecture, follow
  docs/ARCHITECTURE.md for current code and report the inconsistency.

## Product Direction

ResearchMind is a local AI research reading and knowledge-capture workspace. It
connects Paper ↔ Mathematics ↔ Code ↔ Notes in the Zotero → ResearchMind → Obsidian
workflow.

- Zotero owns literature, bibliographic metadata, citation, and collection management.
- ResearchMind owns a local working library, paper/code reading, explicit selections,
  bounded AI understanding, translation, formula assistance, evidence capture, and
  editable note preparation.
- Obsidian owns long-term knowledge. ResearchMind exports traceable Markdown through
  an explicit non-overwriting save; it does not build a competing knowledge system.

A ResearchMind working library is not a Zotero replacement. It stores stable local
item identities, validated managed assets, ResearchMind-specific state, source links,
and explicit note drafts needed for the research workflow.

## Current Development Stage

The accepted regression baseline is local internal version 2.0.0rc1. V2 Internal
Acceptance closed on 2026-09-01 with 269 passing tests and one Windows symlink
environment skip plus recorded package, launcher, recovery, security, performance,
and user-confirmed journeys. It is not a public release.

V3-G0, V3-G1, V3-G2 and V3-G3 are Completed. V3-G2: the user confirmed its read-only
Local API architecture on 2026-09-02. Schema version 2, optional GET-only loopback
metadata browsing, durable source snapshots, link/unlink UI, and graceful failure
handling are implemented. The user approved selected, approved-directory, read-only
PDF copying on 2026-09-04. The Windows implementation now uses /file/view/url,
not HTTP-200 PDF bytes or followed redirects. ZOTERO_ATTACHMENT_ROOT is required;
each copy needs fresh scoped consent. Held read-only handles reject network drives,
traversal, reparse points, hardlinks and source replacement. Metadata/URL are
rechecked; G1 validates and stores the managed copy. See docs/V3_G2_ZOTERO_VALIDATION.md.

The user confirmed "G2通过验收" on 2026-09-04, closing G2 manual acceptance.
Record this as user-reported acceptance, not a newly agent-observed live test.
The accepted G2 automated baseline is 374 passed / 1 environment skip. V3-G3 is also
Completed, with a current combined regression of 486 passed / 1 environment skip.
Its evidence began with an isolated selection contract, synthetic inline CCv2 harness,
and official-template PDF.js 6.3.289 packaged experiment. Edge 152 passed synthetic
mouse selection, bounded event fields, bitmap stability, page invalidation, two-column
text, focused edge-only wheel pagination, debounce/bounds, selection protection,
input-safe Ctrl+Shift+A, desktop split/600px stacking, and no outbound requests. Five
hash-locked representative PDFs pass 12/12 sampled digital selections with native-copy
parity and server-side PyMuPDF text/geometry reconciliation; a scanned PDF degrades
without inventing a selection. Cross-line copying, two viewer instances and a loaded-
revision handshake pass; a 9.1 MiB, 209-page sample showed about 230/238 ms page changes
and 119,420 bytes settled heap growth in one representative run. The user separately
reported physical-trackpad acceptance and approved production CCv2/pdf.js adoption on
2026-09-07.

Production now owns the bundled component under pdf/viewer_component: unchanged PDFs
up to 10 MiB render locally, untrusted browser events become ReadingSelection only
after current-page PyMuPDF text/geometry reconciliation, and stale/duplicate events are
rejected. The legacy PyMuPDF image/text-block reader remains the graceful fallback.
Paper-only is full width, paper+code uses responsive columns, and input-safe
Ctrl+Shift+A controls the AI panel. A 1,041,404-byte production wheel contains exactly
one JS and one CSS asset, the Streamlit manifest, notices and Apache-2.0 license; it has
no node_modules or source maps. Edge 152 production acceptance passed 8/8 checks with
no page errors or external requests. See docs/V3_G3_PDF_WORKSPACE_SPIKE.md. V3-G4 is
the next planned stage and has not started.
No routine test contacts
localhost; no Zotero write, direct Zotero SQLite read, Web API credential, background
sync, group-library workflow, or whole-library cache is implemented.

Only one primary V3 stage may be Active. Preserve 2.0.0rc1 independently so every V3
slice can be abandoned or rolled back without rewriting the accepted baseline.

## Accepted V2 Boundary

V2 already implements:

- local digital-PDF validation, rendering, navigation, zoom, search, text blocks,
  common double-column ordering, conservative headings/captions/formula-text clues,
  embedded-image preview, and page/block/bbox provenance;
- explicit ReadingSelection, translation, ResearchContext-grounded explanation and
  follow-up, evidence preview, constrained selection-to-LaTeX, KnowledgeNote, and
  non-overwriting Obsidian Markdown;
- independent bounded Python code indexing with standard-library AST, CodeSelection,
  CodeContext, beginner/static-reproduction views, and no execution;
- user-confirmed paper/code EvidenceLinks and fixed T5-A read-only evidence tools;
- T5-B1's only source-write exception: one current existing Python range, strict
  replacement, relative diff, separate apply/rollback confirmation, recovery copy,
  raw SHA-256 conflict check, and atomic replacement;
- optional current CodeSelection → editable inputs → code-specific Markdown preview →
  explicit Obsidian save.

Automatic formula recognition, image-formula OCR, whole-PDF-to-LaTeX, browser text
layer selection, persistence, Zotero integration, and non-Python parsing are not V2
features. Existing formula and wheel/CCv2 work remains isolated evidence until a V3
gate adopts it.

V3-G1 adds persistence only for the paper/code working library and managed asset
metadata. Conversation history, evidence links, selections, explanations, T5-A
sessions, and note drafts remain session-only unless a later gate explicitly adopts
their persistence.

## V3 Requirements and Stage Shape

The approved V3 requirements are:

1. a persistent local paper/code working library and click-based import;
2. optional direct Zotero connection without making Zotero mandatory;
3. browser text-layer word selection and translation;
4. formula-region recognition for common mathematics with editable validated LaTeX;
5. Python, C, Java, Julia, and R code reading through the existing CodeContext shape;
6. explicit evidence selection, editable Markdown draft/preview, and optional
   Obsidian save instead of per-turn automatic capture;
7. paper-only full-width PDF, paper+code split workspace, and shortcut-opened AI;
8. V3 hardening, recovery, privacy, performance, and manual acceptance.

Implement them in the stages defined by V2 to V3过渡要求.md. Overall V3 approval does
not automatically select a database schema, managed storage root, Zotero API mode,
PDF component, formula provider, parser packages, or broader code authority.

## Current and Candidate Technology

Preserve Python 3.12, one local Streamlit process, PyMuPDF, the OpenAI-compatible
provider, python-dotenv, pytest, src-layout, dataclasses, type hints, and beginner-
readable modules unless a specific decision changes them.

Implemented V3-G1/G2/G3 choices:

- standard-library sqlite3 with schema version 2, no ORM or database server;
- ResearchMind-managed PDF/Python files plus metadata/hashes/relative paths in SQLite,
  never PDF/source blobs;
- native st.file_uploader for one PDF and Python directory upload, with server-side
  path, type, magic, size, UTF-8, exclusion, parseability, and hash validation.
- `ZOTERO_LOCAL_API_ENABLED` defaults false; when true, the standard-library client
  sends only explicit GET requests to the fixed `127.0.0.1:23119/api/` boundary;
- HTTP redirects remain rejected. Only the selected /file/view/url result may enter
  integration/zotero/local_files.py after configured-root and scoped consent checks.
  Direct copying is Windows-only; other systems/unconfigured roots keep manual
  upload plus linking. Paths never enter source snapshots or prompts.
  Zotero-Server-ID requires Zotero 10+; missing identity fails closed;
- only the selected personal-library item's bounded metadata and optional PDF source
  snapshot persist; browse results and attachment lists remain session-only.
- Streamlit Custom Components v2 with locally bundled pdfjs-dist 6.3.289 provides the
  adopted browser text layer; PyMuPDF remains the trusted parser/reconciler and
  compatibility renderer. Viewer bytes are hash-bound and capped at 10 MiB; no local
  PDF path or unverified client bbox becomes selection provenance.

Candidates not implemented until later gates close:

- Zotero Web API, group-library product workflow, writes, and sync; never direct
  Zotero SQLite;
- a dedicated formula detector/recognizer boundary operating on selected page regions;
- Tree-sitter plus language grammar packages only after Python/C/Java/Julia/R parity,
  Windows packaging, performance, license, and maintenance evidence.

No microservices, database server, Redis, Celery, queues, Kubernetes, separate backend,
cloud sync, vector database, autonomous background agent, or general tool runtime is
planned.

## Module and Dependency Rules

Current ownership:

- app/views displays and delegates only.
- app/state.py is the only Streamlit session-state mutation point.
- app/use_cases.py is the application API and orchestration boundary.
- core contains pure rules.
- models contains shared dataclasses and imports no project layer.
- pdf, code, llm, translation, integration/obsidian, and config.py own their V2
  external boundaries.
- database owns sqlite3 connections, schema versioning, migrations, transactions,
  repositories, managed-file staging/finalization, and library backup/restore.
- integration/obsidian is the only Vault writer.
- config.py is the only environment/secrets reader.

Current adopted infrastructure ownership:

- integration/zotero owns optional Local API GET calls, vendor mapping, and the
  approved single-file Windows read boundary; it never writes Zotero sources;
- pdf/viewer_component owns the adopted CCv2/pdf.js UI, event validation and PyMuPDF
  reconciliation; app/state.py alone stores transient component events/sequences and
  app/use_cases.py maps verified results into application flow;

After the corresponding later V3 gate is approved:

- pdf may add a formula detector/recognizer adapter, but it still does not own LLM,
  translation, database, or Vault orchestration;
- code may add language parser adapters that map to existing project models, but
  remains non-executing and default read-only.

Allowed flow:

    app/views → app/use_cases
    app/use_cases → core + infrastructure + models
    core → models + standard library
    infrastructure → models/protocols + owned external library
    models → standard library only

Views never pass Streamlit UploadedFile or component/vendor objects into Core.
Convert them to validated project inputs. Third-party PDF/parser/Zotero/LLM objects and
errors never escape their infrastructure boundary.

ResearchContext and CodeContext remain separate. EvidenceLink connects provenance,
not prompts. Any future joint prompt requires a task-specific bounded model and gate.

## Persistence and File Ownership

V3-G1 persistence exists because the cross-session paper/code library requirement is
real. Its implemented contract is:

- stable item/asset/source-link identity;
- schema version 2 with deterministic migration, validation, rollback, and newer/
  corrupt-version rejection;
- an explicit data root containing researchmind.sqlite3, assets/, and private staging;
- exact content-hash duplicate detection and immutable AssetReference revisions;
- validated staging, database transaction, atomic finalization, and compensation;
- soft remove/restore separate from confirmed managed-copy deletion;
- checksummed bounded backup and restore only into an absent separate data directory.

Use parameterized SQL, explicit transactions, foreign keys, and project exceptions.
Do not store keys in SQLite. Do not store whole PDFs or code repositories as database
blobs. Never delete an external PDF, source folder, Zotero attachment, or Vault note
as a side effect of removing a ResearchMind record.

## Import, Zotero, and External Data

Browser uploads provide untrusted bytes and names, not a trusted original OS path.
Validate extension/MIME as a hint, magic bytes, size, count, relative path, encoding
or parseability, hashes, exclusions, and resource limits on the server.

Zotero is optional and defaults off. G2 uses the official local HTTP API, which the
user must enable in Zotero and separately enable in ResearchMind. Preserve
server/library/item identity and versions, partition durable links by server identity,
and degrade cleanly when Zotero is unavailable or disabled. Browse results are not a
whole-library cache. A Web API mode requires explicit network/credential handling and
a later gate. Never read Zotero's database file directly.

## PDF, Selection, Formula, and UI

Keep Viewer, Parser, formula detector, formula recognizer, and document understanding
separate.

Any CCv2/pdf.js production component must:

- use Streamlit Custom Components v2 only;
- validate document revision, page, text, spans/bboxes, and event origin;
- preserve normal scroll ownership and prove wheel debounce/bounds/trackpad behavior;
- scope keyboard shortcuts so they do not fire while typing;
- rehydrate across reruns, reject stale/duplicate events, and clean up listeners.

Formula recognition must operate on a bounded validated region, retain detector and
recognizer provenance, show remote transfer before it happens, and return an
untrusted editable candidate. Strict LaTeX validation and explicit user acceptance are
required before rendering or persistence. Do not promise visual identity with the
original equation or infer whole-PDF conversion.

For Streamlit work, read the installed version-matched developing-with-streamlit Skill
and its relevant references. Prefer native widgets/layout; use CCv2 only when native
Streamlit cannot provide the needed interaction.

## Code Authority

Adding C, Java, Julia, or R means static reading and context only. It does not grant:

- import/eval/exec/subprocess/shell/test/install permissions;
- dependency resolution or reproduction guarantees;
- arbitrary source writes, creation, deletion, rename, or multi-file modification.

Preserve file-count/total/per-file limits, excluded secret/vendor/build paths,
relative-only provenance, symlink/root containment, prompt preview, and no execution.
T5-B1 remains Python-only and one selected existing range unless a separate T5-BX
permission and sandbox gate is approved.
ResearchMind-managed code revisions are read-only: T5-B1 remains available only for
an explicitly opened external local project. A changed managed project must be
imported as a new revision so its database hash cannot silently drift.

## Notes and Obsidian

V3 note flow is:

    explicit evidence choice → editable NoteDraft
    → Markdown preview → explicit non-overwriting Vault save

Do not save every chat turn automatically. Editing or locally persisting a draft is
not a Vault write. Keep source locators/origin labels traceable even when explanatory
Markdown is edited. Only integration/obsidian may write the Vault, and it must retain
path sanitization, traversal rejection, Markdown-only output, collision numbering,
and visible failures.

## Security and Privacy

- Never hardcode, commit, return, or log API keys, Zotero credentials, absolute private
  paths, full sensitive payloads, or database contents.
- Keep .env and Streamlit secrets ignored; use placeholders only.
- Treat PDF/code text, uploaded names, component events, Zotero metadata, database
  text, Markdown, history, and model output as untrusted.
- Delimit prompt evidence, send only selected/bounded context, and show external
  transfer scope. Formula services receive one crop, not a whole paper by default.
- Local processing has no telemetry. Routine tests never use a live API or user data.
- Treat LLM LaTeX and code replacements as untrusted and preserve all existing strict
  parsing, confirmation, recovery, and non-execution rules.

## Spike Before Major Dependency

Keep candidate technology in experiments until adopted. A useful Spike answers a
named question and records representative inputs, baseline comparison, quality and
failure cases, Windows/local packaging, latency/memory, privacy/network behavior,
license/maintenance, internal-model mapping, test strategy, and rollback.

This applies to Zotero clients, CCv2/pdf.js packaging, st.pdf dependencies, OCR/formula
models, OpenDataLoader-PDF/Docling/Marker, Tree-sitter/language grammars, and any new
database or UI framework. Adoption requires the named V3 architecture gate.

## Development Workflow

1. Read the architecture, active V3 stage, relevant source/tests, and applicable
   project Skills.
2. Classify bug/optimization/spike/feature/architecture decision.
3. State current/expected behavior, ownership, risk, privacy, tests, rollback, and
   definition of done.
4. Make the smallest coherent change and preserve unrelated user work.
5. Explain and obtain the specific confirmation before an established architecture,
   dependency, persistence, file-ownership, or permission change.
6. Add tests with the behavior, run the gate's checks, review the final diff, and
   synchronize status/evidence documents.
7. After important work, explain actual data flow, key concepts, limitations, and
   three to five useful files for the learning developer.

Do not rewrite stable V2 code for aesthetics, combine unrelated refactors, claim
planned behavior is implemented, upload/release/push publicly, or infer broader
authority from a stage approval.

## Testing

- Regression-first: protect the accepted PDF → selection → translate/LaTeX/explain →
  follow-up → KnowledgeNote → Markdown → Vault loop and affected code paths.
- Use fake LLM/translation/formula/Zotero providers and temporary databases, managed
  storage, code projects, and Vaults.
- Database work tests creation, every migration, transaction rollback, foreign keys,
  duplicates/revisions, interrupted import, corruption, restart, backup/recovery, and
  deletion semantics.
- PDF/CCv2 work combines deterministic event tests, AppTest, representative PDFs, and
  real-browser manual checks for DOM selection, scroll, wheel, shortcuts, and layout.
- Formula work uses labeled structural/symbol cases and records misses/false positives;
  HTTP success is not recognition quality.
- Multilingual code tests each supported language and proves no execution or absolute
  path leakage.
- Note work tests explicit inclusion/exclusion, editing without save, preview parity,
  stale evidence, restart behavior, and Vault non-overwrite.
- Never claim completion without actual commands/results. Separate API, data-integrity,
  context/answer, formula/parser, visual, security, performance, and recovery evidence.

## Project Skills

- project-planner: V3 classification, stage plans, architecture decisions, and gates.
- python-engineering: approved Python implementation and module boundaries.
- research-context: selections, bounded contexts, evidence, prompts, and drafts.
- pdf-research: viewer/parser/formula evidence and PDF/component Spikes.
- research-library: SQLite, imports, managed files, migrations, deletion, and Zotero.
- testing-review: regression, migration, integration, quality, browser, and gate proof.
- learning-mode: accurate explanations of verified code and approved design.

Do not add another domain Skill unless a distinct stable repeated workflow cannot be
expressed by these seven or the installed Streamlit Skill.
