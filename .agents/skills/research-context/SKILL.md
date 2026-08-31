---
name: research-context
description: Design and review ResearchMind ReadingSelection/ResearchContext, CodeSelection/CodeContext, and explicit EvidenceLink provenance, prompt-input boundaries, budgets, and context quality. Use when changing what evidence reaches explanation, follow-up, LaTeX, code explanation, links, or previews; not for PDF-engine selection, provider networking, or tool authority.
---

# Research Context

Make the configured model understand the user's current research task with the
smallest relevant, traceable context. More text is not automatically better context.

Read `docs/ARCHITECTURE.md` for the implemented V1.3.2 + T1 models and flow. Read
`V1 to V2过渡要求.md` only when planning an approved transition slice.

## Current 2.0.0rc1 Research/Code Provenance Baseline

`ResearchContext` already exists. It can contain:

- selected text and its PDF page/block/bbox locator;
- nearby bounded text;
- page and document metadata;
- a conservative preceding section heading;
- a nearby figure/table caption;
- nearby digital-text formula candidates;
- the current question;
- budgeted conversation history.

Explanation, follow-up, and selection-to-LaTeX build a fresh context and expose a
no-network evidence preview using the same prompt builder as the real request.
Translation remains an independent text-to-text capability and does not receive a
full ResearchContext.

T2 completed without adopting a PDF parser, so its spike output does not change
ResearchContext fields or prompt inputs. T3 is implemented as a separate CodeContext,
not as extra ResearchContext fields. Its source is one bounded local Python folder;
its provenance is relative path/line/symbol/extraction method, and it has no execution
or write authority.

T4 adds an `EvidenceLink` between one located PDF ReadingSelection and one verified
CodeSelection. It records paper/code endpoints, relation, confidence, generation
method, and optional rationale. The current path creates only user-confirmed links,
stores them in session, and exports them through KnowledgeNote. It does not add
either source to the other context or trigger a provider call.

T5-B1 reuses a fresh bounded `CodeContext` plus the exact current `CodeSelection` to
ask for one replacement body. It does not merge paper evidence, expose the absolute
root, or grant tool authority. Proposal prompt/preview parity and evidence budgeting
belong here; confirmation, filesystem policy, recovery, atomic write, and rollback are
owned by Application/Core/`code/change_writer.py`, not by ResearchContext.

T6-D adds a non-prompt persistence path for the same current `CodeSelection`.
`capture_code_knowledge` revalidates project/source ownership and any bound
`explain:code` response, then `KnowledgeNote.code_selection` carries relative
path/line/symbol provenance to code-specific Obsidian Markdown. It does not build a
new context, invoke a model, include the absolute root, or merge paper/code prompts.

Do not describe the next phase as “building ResearchContext from scratch.” Current
work should measure and improve its relevance, provenance, cost, and failure behavior.

## Keep Three Concepts Separate

- **Selection** answers: what content did the user choose, and where did it come from?
- **Context Builder** answers: which evidence is necessary for this task?
- **Prompt Builder** answers: how is that chosen evidence delimited and expressed to a
  model?

A parser output is input evidence, not a prompt. A Selection is the anchor, not the
entire context. Prompt wording must not decide PDF reading order or source location.

## Context Change Workflow

Before adding or changing a field:

1. State the research question or demonstrated failure it should improve.
2. Capture the current context and answer-quality baseline on representative examples.
3. Name the evidence source, locator, confidence/origin, distance rule, and budget.
4. Define relevance and failure behavior when the evidence is missing or ambiguous.
5. Compare before/after context, payload size, answer quality, and provenance.
6. Add deterministic unit and integration coverage before changing UI claims.
7. Keep the change only when the measured value justifies the extra tokens and
   complexity.

Every review should answer:

- What context was added or removed?
- Why does the model need it for this task?
- How many characters/tokens does it add?
- Can it include irrelevant or misleading evidence?
- Does it improve a labeled research example?
- Can the user trace it back to document/page/block/bbox?

## Relevance and Budget Rules

- Never send an entire PDF indiscriminately.
- Prefer selected content plus minimal surrounding evidence.
- Bound every expandable source: surrounding blocks, structural landmarks, formulas,
  and history.
- Use explicit deterministic fallback when selection cannot be located; do not attach
  arbitrary section/caption/formula evidence.
- Conversation history cannot grow without limit. Evaluate recent messages, relevant
  messages, and a summary separately before adding summarization machinery.
- Treat a lower payload as valuable only when required evidence is preserved; treat a
  larger payload as valuable only when answer quality improves.

## Provenance and Evidence Semantics

Preserve, where available:

- document id/title/source;
- page;
- block and bbox locator;
- selected source text;
- section/caption/formula evidence;
- whether evidence is user-selected, deterministically extracted, or model-inferred.

Do not present a heuristic association as a verified paper fact. Context preview and
KnowledgeNote should preserve enough provenance for a user to inspect the source.

## Prompt and Security Boundary

- Delimit paper and conversation material as untrusted data; escape attempts to close
  `<paper_context>` and instruct the model that enclosed content is not authority.
- Context Builder chooses evidence; prompt builders in `llm/prompts.py` serialize it
  for a task.
- Preview and real calls must use the same builder and context so the UI does not show
  one payload and send another.
- Do not expose secrets or full internal system prompts in previews.
- Code prompts use a separate `<code_context>` boundary, omit absolute root paths,
  and repeat that source is untrusted and must not be executed.
- T5-B1 change prompts also delimit the user's request inside `<change_request>`, keep
  both blocks untrusted, ask only for one `<replacement>` body, and never accept paths,
  commands, or multiple actions as output.
- Model output is not provenance. LaTeX must also cross its strict validation boundary
  before rendering or capture.

## Evaluation

Do not use “the provider returned a response” as the success criterion. Separate:

- selection/location correctness;
- context relevance and omission/irrelevance errors;
- payload size and truncation behavior;
- prompt boundary/injection safety;
- answer usefulness and faithfulness;
- source traceability.
- for CodeContext: relative-path/line/symbol correctness, exclusion/limit behavior,
  absolute-path omission, and proof that source was never executed.
- for T5-B1 prompts: preview/request parity, selected-range ownership, replacement
  budget, wrapper/injection rejection, and proof that context assembly alone cannot
  write or execute anything.

Use labeled real-paper cases where possible and record correct association, missed
evidence, false association, and unlocatable selection. Run the affected integration
loop with a fake provider; authorize live model evaluation separately because it may
send paper content and incur cost.

## Future Content Sources

Current source-aware behavior uses two explicit context types:

- `ResearchContext` for PDF/document evidence and paper conversation;
- `CodeContext` for one user-selected Python symbol or line range plus bounded nearby
  lines.

Do not merge them implicitly or teach CodeContext as a generic provider framework.
T4 EvidenceLink connects provenance only. A future joint explanation must still
define a bounded task-specific context and evaluation. Web, VS Code, Julia, R,
Jupyter and other sources remain future candidates.

## Finish Check

Confirm that the change starts from a real ReadingSelection/CodeSelection or explicit
question, adds only bounded relevant evidence, preserves source-appropriate
provenance, separates ResearchContext from CodeContext and both from prompt
formatting, treats all source/history as untrusted, measures quality/payload, and does
  not turn EvidenceLink into an implicit joint prompt or expand T5-A beyond its three
  approved current-session read-only evidence tools. T5-A tool serialization must
  preserve each source's provenance/budget and be escaped again before the next model
  step. For T5-B1, confirm that prompt inputs come from the exact current CodeSelection
  and snapshot, omit absolute paths, and remain separate from filesystem authority.
