---
name: research-library
description: Design, implement, migrate, and review ResearchMind's V3 local paper/code working library, click-import storage, SQLite repositories, durable note drafts, and optional Zotero links. Use for schema, transactions, deduplication, managed files, restart persistence, deletion, backup/recovery, or Zotero source mapping; not for PDF extraction, LLM prompts, or Obsidian rendering.
---

# Research Library

Build a small local working library that gives ResearchMind stable paper/code IDs and
cross-session state without replacing Zotero or Obsidian.

Read docs/ARCHITECTURE.md for implemented G1/G2 ownership and the relevant V3
decision records for accepted evidence. G2 metadata/source linking is implemented,
and the user-approved Windows single-attachment copy is implemented via
/file/view/url plus locked local read handles. The user confirmed G2 manual acceptance on 2026-09-04; G2 is Completed.
G3 and G4 are Completed. The user confirmed G4 manual acceptance on 2026-09-09.
Schema v3 has separate NoteDraft/EvidenceSnapshot tables, optimistic revisions,
source-state checks, use cases, and backup/restore. G4 binds exact managed paper
revisions to explicit source/translation evidence, exposes the persistent basket,
restores drafts across sessions and invalidates an export preview when durable or
source state changes. Preserve G1 file ownership/recovery and G2 source-link semantics;
do not broaden to Web API or sync. G5 is Completed without a schema migration: only
explicitly accepted formula LaTeX may reuse the existing EvidenceSnapshot table.
Raw crops, recognizer responses and unaccepted candidates remain session-only.

## Product Boundary

The ResearchMind library may own:

- imported paper and code workspace records;
- validated managed-file references, hashes, sizes, and media/language metadata;
- ResearchMind-specific source links and processing status;
- explicit draft notes and selected evidence needed before Obsidian export;
- optional links to Zotero items and their provenance/version snapshot.

It does not own citation formatting, bibliography management, Zotero collections as a
replacement, Obsidian backlinks, or the user's long-term knowledge graph.

## Recommended Ownership

- models: implemented LibraryRecord, AssetReference, ZoteroSourceLink, NoteDraft and
  EvidenceSnapshot;
- core: pure validation, deduplication, state transition, and deletion rules;
- database: sqlite3 connection, schema, migrations, transactions, and repository
  implementations;
- integration/zotero: adopted Local API GET calls and vendor-to-project mapping;
- app/use_cases.py: import, list/open, link, draft, and delete orchestration;
- app/views and app/state.py: display/events and session state only.

The database never imports Streamlit, PyMuPDF, Zotero SDK objects, LLM code, or Vault
writers.

## SQLite Contract

- Prefer Python's sqlite3; do not add an ORM or server without a new architecture
  decision.
- Use parameterized SQL, explicit transactions, foreign-key enforcement, a schema
  version, and project exceptions.
- Keep migrations ordered, deterministic, idempotence-aware, and tested from each
  supported prior version.
- Define recovery before migration. Never claim a SQL rollback can undo an already
  finalized external file operation.
- Store metadata, stable IDs, hashes, versions, and relative managed-file paths. Keep
  PDFs and source trees as files rather than database blobs.
- Do not expose raw connections, rows, or SQLite exceptions outside database.

## Import and Managed Files

Browser uploads provide untrusted names and bytes. Validate extension/type, magic,
size, encoding or parseability as appropriate, resource limits, and SHA-256 before a
record becomes usable.

Use this safe order unless the approved decision says otherwise:

    validate → hash/deduplicate → stage in managed storage
    → database transaction → atomic finalize → verify consistency

Document compensation when the database and file-system steps cannot be one atomic
transaction. Use safe internal names and relative paths; display names remain metadata.

For directory upload, preserve only validated relative structure, reject traversal,
symlinks, hidden/secret/vendor paths according to code policy, and enforce project
count/size limits.

## Identity and Deduplication

- Give each ResearchMind item a stable internal ID independent of its title/path.
- Use content hashes for exact asset duplicates.
- Preserve source-specific keys for Zotero links; do not merge records only by title,
  DOI, or filename without an explicit conflict workflow.
- A new revision may share logical identity while having a new asset hash. Define
  which selections/drafts become stale.
- Show duplicate/link decisions to the user; never silently discard distinct files.

## Deletion Semantics

Keep separate actions:

- remove a link/source association;
- remove a library record while retaining an external file;
- delete a ResearchMind-managed copy after explicit confirmation;
- export/save a note to Obsidian.

Never delete an externally owned PDF, code folder, Zotero attachment, or Vault note as
a side effect of a catalog operation. Check dependencies and explain what will remain.

## Zotero Boundary

G2 uses the read-only Zotero Local API, explicitly enabled in both applications.
Keep its fixed loopback endpoint, disabled proxies, rejected redirects, bounded
responses and GET-only transport. Never read Zotero's SQLite database directly.

Never follow HTTP redirects. The approved copy reads only a selected /file/view/url
inside ZOTERO_ATTACHMENT_ROOT after scoped confirmation. local_files.py owns
Windows handle locks and rejects network paths/drives, traversal, reparse points
and hardlinks; other systems fail closed. Recheck source/version/URL before and after
reading, then use G1 validation/storage. Paths are ephemeral, never durable metadata.
Manual upload plus linking remains the fallback. Zotero-Server-ID requires Zotero 10+.

Preserve local server ID, library/item key, object version, source mode, and last
observed metadata. Partition durable source links by server ID. Browsing remains
session-only; do not create a whole-library cache. Treat unavailable/disabled
Zotero as an optional integration error, not a ResearchMind startup failure.

A metadata source link does not prove two PDF files are identical. Existing source
links must not silently retag another attachment as imported. Keep unlink explicit;
require it before deleting a linked paper's managed copies.

Web API access is a later optional mode with explicit credentials, network visibility,
pagination/rate handling, and a separate gate. Do not add Zotero write/sync behavior
unless specifically approved.

## Draft Persistence

Persist only explicit NoteDraft content and selected evidence, not every chat turn.
Keep draft revision/stale status. Editing and previewing a draft do not write the
Vault; final save continues through integration/obsidian, requires a still-current
revision/SHA-256-bound preview and remains non-overwriting. The database never stores
the resulting Vault path as ownership of that external note.

## Security and Recovery

- Keep the database and managed storage outside the user's Vault and code roots unless
  configuration explicitly chooses a safe dedicated location.
- Validate configured roots without logging sensitive absolute paths.
- Use least-authority file operations, atomic replace/rename where practical, and
  bounded backups.
- Never store API keys in the database or export them with library backups.
- Treat database text and imported metadata as untrusted in UI, Markdown, and prompts.

## Verification

Use temporary databases/storage/Vaults. Cover schema creation, migrations, rollback,
foreign keys, duplicate and revision cases, interrupted import, path traversal,
corruption, restart persistence, deletion semantics, backup/restore, stale selections,
Zotero server partitions, unavailable/403/malformed fake API behavior, and invariants
that external files and Vault notes are untouched.

## Finish Check

Confirm stable identity, explicit ownership, safe import order, deterministic
migrations, recoverable failure, honest deduplication, clear deletion behavior,
optional Zotero provenance, explicit-only draft persistence, no secrets, no raw vendor
types outside boundaries, and actual restart/recovery test evidence.
