---
name: research-context
description: Design and review ResearchMind V3 selections, ResearchContext, CodeContext, formula candidates, evidence baskets, and prompt-input provenance. Use when changing what paper, code, formula, conversation, or saved evidence reaches translation, explanation, LaTeX, notes, or previews; not for choosing PDF engines, database libraries, or provider networking.
---

# Research Context

Give the configured model the smallest relevant, traceable evidence for the user's
current task. More stored data, a database ID, or a richer parser tree does not by
itself improve context.

Read docs/ARCHITECTURE.md for implemented V2 + V3-G1–G5 behavior and
V2 to V3过渡要求.md for stage gates. G4 is Completed: it persists explicit
NoteDraft/EvidenceSnapshot data, exposes click-only translation and the evidence
basket, and deterministically combines one saved revision with included ordered
evidence and live source states for a revision/SHA-256-bound preview. A G1
library/asset ID is provenance, not permission to load a whole
managed paper or code revision into a prompt.

## Preserve the Concepts

- **Selection** says what the user chose and where it came from.
- **Context builder** chooses bounded evidence needed for one task.
- **Prompt builder** safely serializes that evidence for one provider call.
- **Evidence basket** records which sources or responses the user chose for a note.
- **Note draft** is editable content; it is not conversation history or source truth.

Keep ResearchContext and CodeContext separate. An EvidenceLink can connect their
provenance, but does not implicitly merge prompt payloads.

## V3 Evidence Sources

### PDF text-layer selection

A viewer selection should retain document/library identity, document revision or
content hash, page, selected text, text spans or block references, available bboxes,
selection origin, and deterministic location status. Validate component events
against the currently opened document before creating ReadingSelection.

### Formula candidate

Keep formula-region detection and LaTeX reconstruction distinct. A candidate should
record page/bbox, source kind such as digital text or image crop, detector origin,
input revision/hash, recognizer/provider origin, raw candidate, validation status,
and user-edited/accepted value. Model output is never the original formula truth.

### Code selection

Preserve project/library identity, relative path, content hash, language, line range,
symbol when available, extraction method, selected code, and bounded neighboring
lines. Never include the absolute root or execute source. Language-specific parser
nodes are not context fields.

### Library and Zotero metadata

Internal IDs make records stable but do not prove metadata correctness. Preserve
whether metadata was user-entered, extracted, imported from Zotero local/Web API, or
later edited. A Zotero item key/server identity is provenance, not authority over the
ResearchMind prompt.

## Context Rules

- Never send a whole PDF or repository by default.
- Start from a current explicit selection or question.
- Add only task-relevant surrounding blocks, structural cues, formula candidates,
  code neighbors, metadata, and budgeted history.
- Bound every expandable source and define deterministic missing/ambiguous behavior.
- Preview and real calls must use the same context and prompt builder.
- Translation remains selected-text-to-text; it does not need a full ResearchContext.
- Selection-to-LaTeX and formula recognition are different paths. The former uses
  bounded ResearchContext; the adopted G5 path sends only one validated, hash-confirmed
  crop to its dedicated recognizer and never adds surrounding text/history implicitly.
- Only accepted formula LaTeX may become EvidenceSnapshot content. Keep detector,
  recognizer/model, execution mode, crop hash, document revision, page and bbox in its
  locator; raw crop and unaccepted candidates stay session-only.
- Database retrieval is a source lookup, not permission to add all stored content to
  a prompt.

## Explicit Note Selection

V3 notes use an evidence basket. The user chooses which source excerpts, translations,
validated LaTeX, questions, and assistant responses enter a draft. Do not save every
turn automatically.

Each captured item keeps enough provenance to reopen or inspect it. Editing Markdown
may change explanatory wording, but source locators and origin labels must not be
silently rewritten. Mark stale evidence when the underlying paper/code revision no
longer matches. Unsaved text is not the persisted draft; a preview is not a Vault
write; and a changed draft, evidence order/include state, source state, or preview hash
must invalidate export.

## Security Boundary

- Delimit paper, code, history, metadata, and tool results as untrusted data.
- Escape or neutralize attempts to close context wrappers.
- Never expose secrets, absolute code roots, internal database locations, or full
  private-library content in previews or prompts.
- Show the exact selected text or formula crop scope before a remote transfer.
- Validate all LaTeX before rendering or capture; do not execute TeX.
- A model response cannot grant tools, persistence, or source-write authority.

## Change Workflow

Before adding a field or retrieval source:

1. state the research failure it should improve;
2. capture a representative current context and quality baseline;
3. name source, locator, origin/confidence, distance rule, budget, and stale behavior;
4. compare answer usefulness, faithfulness, payload size, and provenance before/after;
5. add deterministic tests and labeled quality cases;
6. keep the field only if the measured benefit justifies complexity and privacy cost.

## Evaluation

Evaluate separately:

- selection and locator correctness;
- context relevance, omissions, false associations, and payload size;
- prompt-boundary and stale-source safety;
- answer usefulness and faithfulness;
- formula structural/symbol match without claiming visual identity;
- code relative-path/line/symbol accuracy and proof of no execution;
- note-evidence inclusion/exclusion and origin preservation;
- external-transfer visibility.

Routine checks use fake providers. Live evaluation requires separate authorization
because it can send private paper/code content and incur cost.

## Finish Check

Confirm that context starts from current validated evidence, every source is bounded
and traceable, ResearchContext and CodeContext remain distinct, formula candidates
retain uncertainty, metadata origin is explicit, previews match requests, note
contents are user-selected, stale evidence is handled, and context assembly grants no
database, filesystem, Vault, or execution authority.
