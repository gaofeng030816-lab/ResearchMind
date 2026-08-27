---
name: learning-mode
description: Explain ResearchMind code, architecture, data flow, and trade-offs to a learning developer after an important feature or when they ask how or why the design works. Ground explanations in the current V1 implementation rather than speculative future architecture.
---

# Learning Mode

Help the developer understand not only what changed, but how it supports ResearchMind's product goal: understand a paper and turn that understanding into durable, traceable knowledge.

Use `docs/architecture.md` as the source of truth. Clearly distinguish current V1 behavior from long-term Paper ↔ Mathematics ↔ Code ↔ Notes ideas.

## Teaching Priorities

Explain the parts that improve the developer's judgment:

- the user problem and where it sits in the reading-to-knowledge loop;
- data flow across actual modules and models;
- why a responsibility belongs to UI, Application, Domain, or Infrastructure;
- how `ReadingSelection`, `ResearchContext`, `Conversation`, and `KnowledgeNote` connect;
- why Translation is separate from AI Explanation;
- provider interfaces, dependency injection, pure functions, dataclasses, configuration, and boundary errors when they genuinely appear;
- privacy, prompt injection, PDF limitations, Streamlit reruns, and Vault safety when relevant;
- alternatives considered and the concrete trade-off that selected the current design.

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

Do not insert SQLite, REST, Zotero API, vector search, or an agent workflow into a V1 explanation unless the work actually introduced an approved architecture change. Open documents and conversations are in memory; Obsidian Markdown is the persistence layer.

## Architecture Explanations

Make ownership concrete:

- Views show data and delegate actions; `state.py` centralizes Streamlit state changes.
- Use cases describe what the user can do and coordinate pure rules with external systems.
- Core functions make decisions without knowing Streamlit, PyMuPDF, an SDK, or the Vault path.
- Infrastructure modules isolate replaceable or failure-prone external details.
- Models are shared vocabulary and contain no I/O.

Emphasize that ResearchContext is the connection layer, not a synonym for “send the whole paper.” It packages the current selection, nearby context, document metadata, current question, and budgeted history so the AI answers the research task at hand.

Explain product boundaries when they motivated a design: PDF reading is an entry point, Zotero remains the literature manager, and Obsidian remains the long-term knowledge system.

## Learning Summary After Important Work

Use a proportional five-part summary after an important feature or cross-module change:

### What Changed

Describe the user-visible outcome and the modules/models changed.

### How It Works

Trace the concrete input-to-output path with actual file names. State what remains in memory and what is persisted.

### Important Concepts

Teach only the two or three concepts that matter most, using intuition → example → ResearchMind use → formal name → trade-off.

### Why This Design

Connect the choice to V1 constraints. Name realistic alternatives and why they were not selected now; avoid claiming they are universally bad.

### What to Learn Next

Give one specific, achievable next step tied to the feature, such as writing a pure-function test, tracing a use case in a debugger, or implementing a fake provider.

## Proportionality and Honesty

- A trivial edit gets a sentence, not the five-part template.
- A new module or cross-module feature gets the full summary.
- State assumptions, known extraction/model limitations, and untested behavior plainly.
- Never say an abstraction makes future changes “free”; explain which files still change, such as provider implementation plus factory/config registration.
- Prefer one deep, accurate explanation over a catalog of terms.
