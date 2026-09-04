---
name: learning-mode
description: Explain ResearchMind V2 and approved V3 architecture, code, data flow, tests, migrations, components, parsers, and trade-offs to a learning developer while clearly separating verified implementation, active stage work, isolated evidence, and future plans.
---

# Learning Mode

Help a beginner/intermediate Python developer understand what ResearchMind actually
does, why the design fits the product, and how to inspect or test it.

Use docs/ARCHITECTURE.md as the implemented source of truth and
V2 to V3过渡要求.md for planned/active V3 stages. Never teach a planned database
table, Zotero adapter, PDF component, formula model, parser, or UI as implemented.

## Status Vocabulary

Always label behavior as one of:

- implemented and verified in accepted V2;
- implemented in the active V3 slice but not fully accepted;
- isolated Spike evidence;
- approved design not yet implemented;
- proposed future work.

The 2.0.0rc1 V2 baseline is implemented and accepted. V3-G0 is governance and design
work; it does not itself add production persistence, Zotero, text-layer selection,
formula OCR, extra languages, or editable drafts.

## Teaching Priorities

Explain:

- the user problem and its place in library → reading/code → understanding → note;
- actual models and module boundaries;
- what stays in session, SQLite, managed files, Zotero, or Obsidian;
- why selection, context, prompt, draft, preview, and save are different steps;
- how a migration changes durable data safely;
- how an adapter converts an external API/parser/component into project models;
- why browser uploads provide bytes rather than a trusted local path;
- why PDF viewing, parsing, formula detection, and formula recognition are separate;
- why Tree-sitter can unify parsing shape without executing code;
- which evidence proves correctness and which limitations remain.

Skip line-by-line narration, generic tutorials, and speculative abstractions.

## Explanation Order

For a non-obvious idea:

1. **Intuition:** the practical problem in plain language.
2. **Small example:** a minimal example independent of the whole app.
3. **ResearchMind path:** real model/module/input/output.
4. **Formal name:** introduce the software term.
5. **Trade-off:** what it buys and what it does not solve.

## Product Flows

Implemented V2 paper path:

    local PDF → pdf/PyMuPDF → ReadingSelection → ResearchContext
    → translation or LLM → Conversation
    → KnowledgeNote → Obsidian Markdown → non-overwriting Vault save

Implemented V2 code path:

    local Python folder → bounded reader + standard-library AST
    → CodeSelection → CodeContext → non-executing explanation
    → optional code KnowledgeNote → Obsidian

Implemented V3-G1 library path:

    browser upload → validated bytes/name → managed file
    → sqlite3 library record/hash/asset revision → reopen by stable ID

Implemented active V3-G2 metadata path, real Zotero manual acceptance still pending:

    explicit enable + click → loopback Local API GET → project item/attachment
    → explicit link to a G1-uploaded PDF → ZoteroSourceLink

Direct attachment import is disabled: official /file returns 302 file://, not PDF
bytes. Reading that local path needs a separate approved boundary. Explain that
fake byte-response tests are a prototype, not verified Zotero PDF import.

Browsing stays in the session. Only chosen source snapshots persist. Explain that
linking metadata is an association, not proof that two PDFs have identical content;
unlinking is separate from deleting any file, and Zotero itself is never written.

Recommended V3 paper interaction path, only after its gate:

    CCv2/pdf.js text-layer event → validated ReadingSelection
    → translate/explain → user adds chosen result to evidence basket
    → editable NoteDraft → preview → explicit Obsidian save

Recommended formula path, only after its gate:

    page region → detector evidence → validated crop
    → formula recognizer candidate → strict LaTeX validation
    → user edit/accept → context/note

Recommended multilingual code path, only after its gate:

    bounded source file → language adapter → project CodeSymbol
    → unchanged CodeSelection/CodeContext → no execution

## Concepts to Teach as V3 Appears

- **SQLite transaction:** a group of database changes that all succeed or all roll
  back; ResearchMind also has file-system staging because SQL cannot roll back a file
  rename by itself.
- **Migration:** a versioned transformation from one supported schema to the next,
  tested with old database fixtures and recovery evidence.
- **Managed asset:** a file copied into ResearchMind-owned storage; deleting its
  catalog record is not automatically permission to delete an external file.
- **Adapter:** a narrow boundary that maps Zotero JSON, Tree-sitter nodes, or CCv2
  events to ResearchMind dataclasses and errors.
- **Provenance:** enough identity and locator data to inspect the original source and
  distinguish user choice, deterministic extraction, imported metadata, and model
  inference.
- **Optimistic/stale validation:** rejecting an event or edit when the source hash or
  revision no longer matches what the user saw.

## Learning Summary After Important Work

Use a proportional summary:

### What changed

State before/after behavior, active gate, files/models changed, and exclusions.

### How it works

Trace the real input-to-output path and say what persists where.

### Important concepts

Teach only two or three relevant ideas using the explanation order above.

### Why this design

Compare realistic alternatives and the concrete ResearchMind trade-off.

### What to learn next

Recommend three to five real files in reading order and one achievable exercise such
as tracing a use case, testing a migration, inspecting an adapter, or comparing a
context preview with the sent prompt.

## Honesty

Do not describe API connectivity as answer quality, static code clues as successful
reproduction, formula LaTeX as original truth, a browser screenshot as interaction
coverage, a database record as source correctness, or an accepted design as working
code. Name manual, environment, privacy, and quality limits plainly.
