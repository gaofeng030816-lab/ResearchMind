---
name: python-engineering
description: Implement an explicitly approved ResearchMind V3 Python slice while preserving the accepted V2 behavior, module ownership, project models, error semantics, privacy, and beginner-readable code. Use after the relevant V3 architecture or dependency gate is closed; do not use it to bypass a gate.
---

# Python Engineering

Build explicit, typed, testable Python for one approved V3 slice. Read
docs/ARCHITECTURE.md for current code and V2 to V3过渡要求.md for the active gate.
The accepted 3.0.0rc1 V3 internal candidate is the current implementation baseline;
the accepted 2.0.0rc1 V2 behavior remains an independent historical regression baseline.

## Runtime and Shape

- Keep Python 3.12, one local Streamlit process, src-layout, dataclasses, plain
  functions, and narrow protocols at real external boundaries.
- Keep Streamlit, PyMuPDF, the OpenAI-compatible provider, python-dotenv, pytest, and
  all V2 safety contracts unless an approved decision changes one of them.
- Prefer the standard library. V3 persistence evaluates sqlite3 before an ORM or
  database server.
- No microservices, background workers, shell execution, dependency installation,
  code execution, or broader source-write authority is implied by V3.

## Ownership

Current modules keep their V2 responsibilities:

- app/views displays data and delegates events;
- app/state.py is the only Streamlit session-state mutation point;
- app/use_cases.py is the application API and orchestration boundary;
- core contains pure rules;
- models contains shared dataclasses and no I/O;
- pdf owns PyMuPDF and any adopted PDF/formula adapters;
- code owns bounded source discovery, parsing, and the existing narrow Python writer;
- llm and translation own provider networking and response parsing;
- integration/obsidian remains the only Vault writer;
- config.py remains the only environment/secrets reader.

V3-G1/G2 adopted the following persistence shape:

- database owns sqlite3 connections, schema versions, migrations, transactions, and
  repository implementations;
- models owns LibraryRecord, AssetReference, ZoteroSourceLink, NoteDraft,
  EvidenceSnapshot and the session-only NoteDraftPreview; completed G4 persists only
  explicitly created drafts/evidence in schema v3, while conversation/session objects
  remain transient;
- core owns pure import, deduplication, deletion-state, and draft-selection rules;
- integration/zotero owns the optional Zotero HTTP boundary and vendor JSON mapping.

Completed G4 also keeps deterministic draft rendering and Vault I/O separate:
app/use_cases.py reloads the current revision/evidence/source states, the Markdown
renderer creates one exact preview, and integration/obsidian alone performs exclusive
file creation. Never let a View write Markdown directly or let an unsaved/stale/
hash-mismatched preview reach the writer.

Do not create generic services, managers, repositories, adapters, or utilities without
a demonstrated second use. Third-party objects and Streamlit UploadedFile values must
not become project contracts.

## V3 Input Boundaries

### Browser file import

Views may read an UploadedFile into validated name/bytes input, then call a use case.
The use case and lower layers receive project values, not Streamlit types. Revalidate
extension, magic bytes, size, relative names, duplicate hashes, and storage limits
server-side. A browser upload does not prove or expose the original operating-system
path.

### SQLite

Use parameterized SQL, explicit transactions, foreign-key enforcement, schema
versioning, and project exceptions. Store metadata, identifiers, hashes, and relative
managed-file references; do not put whole PDFs or repositories in SQLite blobs.
Migrations must be deterministic, tested from every supported version, and leave a
recoverable pre-migration copy or documented rollback path.

### Zotero

Keep Zotero optional and default-off. Convert adopted Local API responses inside
integration/zotero; preserve the fixed loopback GET-only boundary and reject
redirects. Web API remains unapproved. Never read Zotero's SQLite directly.
The approved Windows copy uses /file/view/url plus integration/zotero/local_files.py.
Require configured-root and per-selection consent; keep all ancestor/file handles
open without write/delete sharing through the bounded read. Reject aliases/network
locations and recheck metadata/URL. Non-Windows or unconfigured roots fail closed.
Never restore the obsolete HTTP-200 PDF prototype or follow redirects.
Preserve server/library/item identity and version; a source link is not content-hash
evidence. Do not silently update an attachment identity without its explicit action.

### PDF and formula interaction

Keep viewer events, PDF extraction, and formula recognition separate. A CCv2/pdf.js
selection event becomes a project ReadingSelection only after page/text/geometry and
document-revision validation. Formula model output is an untrusted candidate that
must cross strict LaTeX validation and explicit user edit/acceptance before capture.
The completed G5 implementation keeps FormulaRegion/FormulaCrop/FormulaCandidate in
models, local detection/cropping in pdf, provider networking in llm, transient raw
bytes/candidates in app/state.py, and orchestration/revalidation in app/use_cases.py.
Do not persist raw crops or unaccepted output, reuse consent across hashes, or add a
local model/weight without a new dependency gate.

### Multilingual code

Preserve CodeProject, CodeSelection, CodeContext, limits, relative-path provenance,
and no execution. G6 adopted Python standard-library AST, separate C/Java/Julia
Tree-sitter adapters, and a conservative R lexical adapter. Vendor nodes exist only
inside code/tree_sitter_parser.py and map to project CodeSymbol data. Keep language
and extraction_method through files, selections, contexts, prompts, evidence and
Markdown. Parser errors degrade to explicit text selection. Do not add runtime
grammar downloads, language packs, compilation, dependency resolution or execution.
Adding languages does not extend T5-B1 beyond the approved Python range.

### Editable notes

Separate selection, draft, preview, and Vault save:

    user chooses evidence → NoteDraft → editable Markdown
    → rendered preview → explicit save through integration/obsidian

Do not append every chat message automatically. Editing a draft must not write a
Vault file. Persisting a local draft and exporting final Markdown are different use
cases with different errors and state invalidation.

## Dependency Flow

Use these concrete rules:

    app/views → app/use_cases
    app/use_cases → core + infrastructure + models
    core → models + standard library
    infrastructure → models/protocols + owned third-party library
    models → standard library only

Database and integrations do not call views. PDF does not call translation, LLM,
database, or Obsidian. Zotero does not write the Vault. Obsidian does not query
SQLite. Application use cases coordinate these boundaries.

## Errors, Privacy, and Data Safety

- Translate vendor/database errors into project exceptions at the owning boundary.
- Never log keys, full prompts, absolute private paths, PDF/code contents, or Zotero
  credentials.
- Show when selected text or formula crops will leave the machine.
- Treat uploaded names, PDF text, code, Zotero metadata, Markdown, model output, and
  component events as untrusted.
- Use temporary/staged files plus atomic rename for managed-file writes; never
  overwrite or delete an external source as a side effect of removing a catalog row.
- Preserve the V2 Obsidian non-overwrite and T5-B1 recovery/hash/confirmation rules.

## Implementation Loop

1. Confirm the active V3 gate and its decided contracts.
2. Add a failing focused test or migration fixture.
3. Add project models and pure rules before infrastructure wiring when needed.
4. Implement the narrow owned boundary and use-case orchestration.
5. Add state/view behavior last; follow the installed Streamlit Skill for every UI or
   CCv2 change.
6. Run focused, integration, Streamlit, and full-regression checks required by the
   gate; review the final diff.

## Finish Check

Confirm that no planned stage is presented as implemented, V2 paths still work,
models remain vendor-free, views call only use cases, persistence and external
integrations are isolated, upload/path and deletion behavior are safe, context is
bounded and traceable, notes require explicit selection/save, code is never executed,
dependencies were gate-approved, and actual test evidence is reported.
