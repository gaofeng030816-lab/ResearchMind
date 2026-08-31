---
name: learning-mode
description: Explain ResearchMind code, architecture, data flow, tests, and trade-offs to a learning Python developer after important V1.3.2 or approved transition work, clearly separating implemented behavior, isolated experiments, and planned V2 ideas.
---

# Learning Mode

Help the developer understand not only what changed, but how it supports ResearchMind's product goal: understand a paper and turn that understanding into durable, traceable knowledge.

Use `docs/ARCHITECTURE.md` as the source of truth for current code. Use
`V1 to V2过渡要求.md` only to explain transition intent and gate status. Clearly
distinguish:

- **implemented and verified** behavior;
- **implemented but not manually verified** behavior;
- **isolated spike/experiment** results;
- **approved but not implemented** work;
- **proposed future** Paper ↔ Mathematics ↔ Code ↔ Notes ideas.

Never teach a planned model, provider, database, parser, or agent tool as though it
exists in the repository.

Current gate (2026-08-31): teach T1 Selection/provenance, T3 static Python
CodeContext, and T4 user-confirmed evidence links as implemented; teach T2 as a
completed isolated decision that retained PyMuPDF. Teach T5-A as implemented and
verified: three current-session no-argument read-only evidence tools, one model step
per user click, visible pending results, hard budgets, strict protocol, and
metadata-only audit. Teach T6-A as implemented and verified: three
peer top-level workspaces, a code entry independent from PDF, beginner and
static-reproduction goals, and a pure `CodeProjectSummary`. Teach the T6-C visual
check as user-confirmed manual evidence, not automated browser evidence. Teach T6-B as implemented and verified: explicit no-network
configuration diagnostics, Markdown-only manifest/SHA-256 backup, restore into a new
subdirectory, clean installation, and wheel rollback with unchanged external notes.
Teach T6-C automated privacy, dependency-vulnerability, performance, restart, and
regression evidence as implemented and verified. T6-D then optimized the initially
failing 21.19-second 2,000-file index to repeated 3.43/3.66-second passes without
lowering limits. Teach its desktop/narrow-window checklist as explicitly
user-confirmed manual evidence, not automated browser evidence. Teach T5-B1 as
implemented and verified: one selected Python range, strict replacement output,
relative-path diff, per-action consent, recovery copy, SHA-256 conflict protection,
atomic apply, safe rollback, and metadata-only audit. Arbitrary Shell/test/install,
multi-file, or background authority remains unapproved T5-BX scope. Teach T6-D as
Completed for the local internal `2.0.0rc1` candidate: wheel/install/launcher/
diagnostics/recovery/security automation passes, and the user explicitly confirmed
the paper, independent-code, and T5-B1 manual journeys on 2026-08-31. Teach
Code → Obsidian notes as implemented: current selection plus optional bound explanation
and user notes becomes relative-provenance Markdown only after preview and explicit
Vault save; it does not require PDF or write/execute source. Teach mouse-wheel page
change only as a future CCv2 spike candidate. Do not teach T6-D as a public release.

## Teaching Priorities

Explain the parts that improve the developer's judgment:

- the user problem and where it sits in the reading-to-knowledge loop;
- data flow across actual modules and models;
- why a responsibility belongs to UI, Application, Domain, or Infrastructure;
- how `ReadingSelection`, `ResearchContext`, `Conversation`, and `KnowledgeNote` connect;
- how `CodeProject`, `CodeProjectSummary`, `CodeSelection`, and `CodeContext` form a
  separate, in-memory, non-executing path that does not require a PDF;
- how `capture_code_knowledge`, `KnowledgeNote.code_selection`, code-specific Markdown,
  dedicated state invalidation, and the existing Vault writer turn one current code
  selection into durable knowledge without persisting an absolute project root;
- how `CodeFileSnapshot`, `CodeChangeProposal`, and apply/rollback receipts turn one
  untrusted model suggestion into a user-controlled, recoverable source change;
- why entry points, imported modules, dependency candidates, and problem files are
  static reading clues rather than proof that a research result has been reproduced;
- why configuration readiness, API connectivity, and successful research answers are
  three different claims;
- how manifest/checksum verification detects damage while absent-target restore and
  staging prevent T6-B from silently overwriting a user's Vault;
- how `PaperEvidenceReference`, `CodeEvidenceReference`, and `EvidenceLink` preserve
  two locators and distinguish a user-confirmed claim from model inference;
- how `ReadOnlyAssistantSession`, pure Core state transitions, strict action parsing,
  fixed use-case dispatch, and Streamlit confirmation separate model choice from
  actual authority;
- why V1.3.2 LaTeX conversion is an LLM interpretation of selected text, not evidence
  that the PDF's original two-dimensional formula was recovered exactly;
- why Translation is separate from AI Explanation;
- provider interfaces, dependency injection, pure functions, dataclasses, configuration, and boundary errors when they genuinely appear;
- privacy, prompt injection, PDF limitations, Streamlit reruns, and Vault safety when relevant;
- alternatives considered and the concrete trade-off that selected the current design.
- the before/after measure, regression evidence, and remaining manual or environment
  limitation for an optimization.

Skip line-by-line narration, obvious syntax, generic Python tutorials unrelated to the work, and future systems that were not implemented.

## Explanation Order

For a non-obvious concept, teach in this order:

1. **Intuition:** the practical problem in plain language.
2. **Small example:** a minimal example independent of the full application.
3. **ResearchMind use:** point to the real module, model, or data flow.
4. **Formal name:** name the concept after the developer can recognize it.
5. **Trade-off:** state what the approach buys and what it does not solve.

Example for dependency injection:

> The explain use case should not know whether the reply comes from OpenAI, DeepSeek, or local Ollama. It receives something that follows `LlmProvider` and calls `complete()`.
>
> A small analogy is a function that accepts any object with a `send()` method instead of constructing a specific email service itself.
>
> In ResearchMind, `app/use_cases.py` coordinates the request, `llm/factory.py` selects the provider, and tests pass a fake provider. This is dependency injection through a protocol. It makes provider swapping and deterministic tests easy, at the cost of one small interface and factory boundary.

## Use the Real Product Flow

When explaining a multi-module feature, trace only the path that actually ran. A representative V1 chain is:

```text
local PDF
→ pdf/ (PyMuPDF rendering and text blocks)
→ ReadingSelection
→ app/use_cases.py
→ core/research_context.py
→ llm/prompts.py + LlmProvider
→ Conversation/Message in memory
→ KnowledgeNote
→ integration/obsidian/markdown.py
→ integration/obsidian/vault.py
→ non-overwriting Markdown in the user's Vault
```

For translation, show the shorter independent path:

```text
selected text → translate_selection
→ TranslationProvider/LlmTranslationProvider
→ translated Message
```

For selection-to-LaTeX, show the bounded path:

```text
selected formula text → ResearchContext → build_latex_prompt
→ LlmProvider → strict LaTeX parser → convert:latex Message
→ Streamlit math preview → KnowledgeNote → Obsidian display math
```

For T3 code explanation, show the separate path:

```text
local folder → code/ limits and UTF-8 read → standard-library AST → CodeSymbol
→ explicit CodeSelection → core/code_context.py → <code_context> preview/prompt
→ LlmProvider → code-only Message in Streamlit session state
```

For T5-B1 controlled replacement, show the write path and its stop points:

```text
current CodeSelection + exact CodeFileSnapshot + user request
→ bounded CodeContext/change prompt → strict <replacement> parser
→ pure candidate/syntax/diff validation → visible relative-path diff
→ explicit apply confirmation → recovery copy → hash check → atomic replace
→ receipt; separate rollback confirmation → external-edit check → safe restore
```

Emphasize that proposal generation does not write, confirmation is enforced in the
application layer, recovery is retained, and the product never runs the changed code.

T4 does not insert ResearchContext into the code prompt. Teach its separate,
no-network capture path:

```text
located ReadingSelection + current CodeSelection
→ pure evidence-link validation → user_confirmed EvidenceLink in session
→ KnowledgeNote → traceable Obsidian Markdown
```

Do not insert SQLite, REST, Zotero API, vector search, a TeX compiler, or an agent
workflow into a V1 explanation unless the work actually introduced an approved
architecture change. Open documents and conversations are in memory; Obsidian
Markdown is the persistence layer.

## Architecture Explanations

Make ownership concrete:

- Views show data and delegate actions; `state.py` centralizes Streamlit state changes.
- Use cases describe what the user can do and coordinate pure rules with external systems.
- Core functions make decisions without knowing Streamlit, PyMuPDF, an SDK, or the Vault path.
- Infrastructure modules isolate replaceable or failure-prone external details;
  `code/change_writer.py` is the sole T5-B1 source-write exception.
- Models are shared vocabulary and contain no I/O.

Emphasize that ResearchContext is the connection layer, not a synonym for “send the whole paper.” It packages the current selection, nearby context, document metadata, current question, and budgeted history so the AI answers the research task at hand.

Explain product boundaries when they motivated a design: PDF reading is an entry point, Zotero remains the literature manager, and Obsidian remains the long-term knowledge system.

## Learning Summary After Important Work

Use a proportional five-part summary after an important feature or cross-module change:

### What Changed

Describe the user-visible problem, before/after outcome, modules/models changed, and
what was deliberately left unchanged.

### How It Works

Trace the concrete input-to-output path with actual file names. State what remains in memory and what is persisted.

### Important Concepts

Teach only the two or three concepts that matter most, using intuition → example → ResearchMind use → formal name → trade-off.

### Why This Design

Connect the choice to V1 constraints. Name realistic alternatives and why they were not selected now; avoid claiming they are universally bad.

### What to Learn Next

Recommend 3–5 actual files worth reading, in a useful order, and give one specific,
achievable exercise such as tracing a use case, writing a pure-function regression
test, inspecting a provider adapter, or comparing a context preview with its prompt.
Also name the one concept the developer should understand before the next approved
stage.

## Proportionality and Honesty

- A trivial edit gets a sentence, not the five-part template.
- A new module or cross-module feature gets the full summary.
- State assumptions, known extraction/model limitations, and untested behavior plainly.
- Explain interfaces, providers, dependency injection, domain models, adapters, DTOs,
  parsers, context, state, streaming, or async only when they appear in the code or
  approved design; pair the term with a concrete ResearchMind example.
- Never say an abstraction makes future changes “free”; explain which files still change, such as provider implementation plus factory/config registration.
- Prefer one deep, accurate explanation over a catalog of terms.
