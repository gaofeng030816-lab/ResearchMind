---
name: project-planner
description: Plan meaningful ResearchMind features and architecture changes against the current V1 product loop. Use before a new feature, a cross-module change, an architecture decision, or when requirements are materially ambiguous; skip for trivial, well-contained edits.
---

# Project Planner

Plan the smallest coherent change that advances ResearchMind's research-reading and knowledge-capture workflow. Use `docs/architecture.md` as the source of truth for current V1 boundaries, module ownership, data flow, and selected technologies.

## Product Test

Start by identifying where the request fits this loop:

```text
local PDF → reading/selection → translation or ResearchContext-grounded AI
→ follow-up conversation → KnowledgeNote → Markdown → Obsidian Vault
```

The PDF reader is an entry point, not the whole product. The durable outcome is traceable knowledge in the user's Obsidian Vault. Zotero owns literature management and Obsidian owns long-term knowledge organization; plans must not quietly reproduce either product.

The long-term Paper ↔ Mathematics ↔ Code ↔ Notes direction is context, not V1 scope. Do not include future integrations or abstractions merely because they could become useful later.

## Planning Workflow

Before proposing implementation:

1. Inspect `AGENTS.md`, `docs/architecture.md`, relevant source, tests, dependency configuration, and any task-specific documentation.
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
- `core/`: pure ResearchContext, selection, and conversation rules.
- `models/`: shared dataclasses with no project-layer imports.
- `pdf/`: all PyMuPDF use, rendering, extraction, search, and PDF boundary errors.
- `llm/`: provider protocol/factory, explanation prompts, response parsing, and LLM errors.
- `translation/`: independent text-to-text translation protocol, service, provider, and errors.
- `integration/obsidian/`: Markdown rendering and the only Vault write path.
- `config.py`: the only environment/secrets reader.

Important constraints:

- Explanation and follow-up use cases build a `ResearchContext` before calling the LLM.
- Translation remains separate from explanation and accepts text rather than PDF objects.
- `capture_knowledge` assembles `KnowledgeNote`; Obsidian integration alone renders and writes it.
- Conversations and opened documents remain in memory in V1.
- Notes are saved as non-overwriting, traceable Markdown in the configured Vault.
- V1 has no REST backend, database, ORM, Zotero integration, advanced RAG, vector store, or agentic workflow.

## Plan Content

For a meaningful feature, give the user a concise plan covering:

- **Goal and scope:** the user problem, success condition, assumptions, and exclusions.
- **Current fit:** reusable modules and behavior already present.
- **Changes:** files/modules to create or modify and the responsibility of each.
- **Data flow:** actual models and boundaries involved, including `ResearchContext` or `KnowledgeNote` when relevant.
- **Dependencies:** preferably none; justify any addition and identify the architecture decision if it changes the chosen stack.
- **Verification:** unit, integration, or Streamlit smoke checks plus important error cases.
- **Risks:** data loss, privacy, prompt injection, PDF limitations, state/rerun behavior, and boundary violations that genuinely apply.
- **Order:** a small sequence that produces testable increments.

## Architecture Changes

Changing Streamlit, the no-database decision, process topology, persistence ownership, public use-case contracts, or major module boundaries is an architecture decision. Before making it:

1. Show the concrete requirement the current architecture cannot meet.
2. Compare the smallest viable alternatives and trade-offs.
3. Explain migration and testing impact.
4. Obtain user confirmation.

Do not present a large rewrite as ordinary feature work.

## Completion Check

A plan is ready when its user outcome is explicit, it fits the V1 loop, module ownership and data flow are unambiguous, dependencies are justified, verification covers the changed behavior, and future work has not leaked into the implementation scope.
