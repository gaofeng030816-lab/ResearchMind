---
name: python-engineering
description: Implement or modify ResearchMind Python code, project structure, configuration, models, providers, and use cases while preserving the documented V1 module boundaries and data flow.
---

# Python Engineering

Build explicit, typed, testable Python that a beginner/intermediate developer can understand. Read `docs/architecture.md` before making structural choices; it is the source of truth for V1 technology, ownership, and dependency rules.

## Runtime and Shape

- Target Python 3.12.
- Keep a single local Streamlit application with src-layout.
- Use the established V1 stack: Streamlit, PyMuPDF, `openai` through an OpenAI-compatible provider, python-dotenv, and pytest.
- V1 has no REST backend, database, ORM, background worker, or separate service.
- Use dataclasses for data, protocols only at justified provider boundaries, and plain functions for stateless behavior.
- Prefer the standard library and existing dependencies. Explain why any new dependency is necessary before adding it.

## Module Ownership

```text
src/researchmind/
├── config.py                  # only environment/secrets reader
├── models/                    # shared pure dataclasses
├── app/
│   ├── app.py                 # Streamlit composition
│   ├── state.py               # only session-state mutation point
│   ├── use_cases.py           # application API and orchestration
│   └── views/                 # display and event delegation
├── core/                      # pure domain rules
├── pdf/                       # PyMuPDF infrastructure
├── llm/                       # LLM protocol, prompts, provider, parsing
├── translation/               # independent translation capability
└── integration/obsidian/      # Markdown rendering and Vault writes
```

Do not create parallel `database/`, `notes/`, `services/`, or generic `utils/` modules for V1 behavior already owned above.

## Allowed Dependency Flow

Use concrete import rules instead of a misleading linear layer chain:

```text
app/views → app/use_cases
app/use_cases → core + infrastructure boundaries + models
core → models + standard library
infrastructure → models/protocols + external libraries
models → standard library only
```

- Views never import PyMuPDF, provider SDKs, translation providers, or Vault writers.
- Views never implement parsing, context assembly, prompting, knowledge capture, or file-writing rules.
- Only `state.py` mutates `st.session_state`; views use its functions.
- Application use cases coordinate Domain and Infrastructure. This orchestration is not a Domain responsibility.
- `core/` remains pure and framework-independent. It does not import Streamlit, provider SDKs, PyMuPDF, or file-system integrations.
- `models/` imports no project layer and performs no I/O.
- Infrastructure modules do not call each other across product responsibilities unless the architecture explicitly requires it. In V1, `LlmTranslationProvider` may depend on the `LlmProvider` protocol; PDF never calls LLM, translation, or Obsidian.

## Application Contracts

Treat functions in `app/use_cases.py` as V1's application API. UI behavior should compose or extend these use cases rather than reaching around them:

- `open_pdf`, `get_page_view`, `search_text`, `create_selection`
- `translate_selection`, `explain_selection`, `ask_followup`
- `capture_knowledge`, `save_note_to_vault`

Keep signatures typed and return plain project models or small view/application dataclasses such as `OpenedDocument`, `PageView`, and `TextMatch`. Do not introduce REST-shaped DTOs until a REST API is actually requested.

## Domain Models and Rules

Represent shared concepts with dataclasses, not ad-hoc dictionaries:

- `Document`, `Page`, `TextBlock`
- `ReadingSelection`, with a source-typed locator; V1 source is PDF
- `ResearchContext`
- `Conversation`, `Message`
- `KnowledgeNote`

Use the current names. Do not reintroduce the old `Paper`, `Selection`, or `Note` model names. `CodeElement`, `PaperElement`, and `PaperCodeLink` are future concepts and must not be implemented in V1.

Domain behavior belongs in small pure functions:

- `core/selection.py`: locate normalized selected text in the current page first, then the document; failure to locate returns an empty locator without blocking translation/explanation.
- `core/research_context.py`: assemble selected text, nearby blocks, document metadata, current question, and budgeted history.
- `core/conversation.py`: keep recent history within configuration budgets.
- `app/use_cases.py::capture_knowledge`: assemble a `KnowledgeNote`; Markdown rendering and writing remain in Obsidian integration.

## ResearchContext and Prompts

Every explanation and follow-up use case must build a fresh `ResearchContext` before invoking `LlmProvider`. Use relevant nearby text blocks rather than sending the whole PDF. Apply configured context and history budgets without crashing on oversized input.

`llm/prompts.py` owns explanation/follow-up prompt builders for concept, math, algorithm, contextual, and follow-up tasks. Each builder accepts `ResearchContext` and returns `list[ChatMessage]`.

Treat paper text and conversation history as untrusted data:

- delimit paper material inside `<paper_context>...</paper_context>`;
- state in the system prompt that the enclosed text is data, not instructions;
- treat prior model responses as data as well;
- never give the V1 model tool or execution authority.

## LLM Boundary

Application code depends on the protocol, never a concrete SDK client:

```python
class LlmProvider(Protocol):
    def complete(self, messages: list[ChatMessage], **kwargs: object) -> str: ...
```

- Construct providers in `llm/factory.py` from typed configuration.
- V1's required implementation is `llm/providers/openai_compatible.py`, covering OpenAI-compatible remote services and local endpoints such as Ollama.
- Add `AnthropicProvider` only when requested and its dependency is justified.
- Keep retry, timeout, SDK calls, and provider-error mapping inside the provider boundary.
- Parse responses centrally; map empty or malformed responses to `LlmBadResponseError` and API failures to `LlmApiError`.
- A new provider normally requires its implementation plus minimal factory/config registration; it must not change Domain or UI behavior.

## Translation Boundary

Translation answers “what does this text mean in another language?”; explanation answers “what does this mean in this paper?”. Keep them separate.

```python
class TranslationProvider(Protocol):
    def translate(self, text: str, target_language: str) -> str: ...
```

- Translation accepts selected text and target language, not PDF objects or a full `ResearchContext`.
- V1 has exactly one implementation: `translation/providers/llm_translation.py`, reusing `LlmProvider`.
- Keep its translation prompt within the translation provider and apply the same untrusted-input defense.
- Map provider failures to `TranslationError` at the translation boundary.
- Do not build multi-provider selection machinery until a second implementation is requested.

## PDF Boundary

- Keep every PyMuPDF import and operation inside `pdf/`.
- Validate file extension, PDF magic bytes, existence, and the configured size limit (50 MB by default) before parsing.
- Return document/page/block models and page-image data; never leak PyMuPDF objects into UI or Domain APIs.
- Convert missing, corrupt, or unreadable file failures to project-defined PDF exceptions such as `PdfExtractionError`.
- Preserve the V1 page-image + extracted-text-panel approach. Page-level highlighting, OCR, table recognition, and formula recognition are out of scope.

## Knowledge and Obsidian Boundary

- `capture_knowledge` assembles source text, translation, selected questions/answers, user notes, tags, and provenance into `KnowledgeNote`.
- `integration/obsidian/markdown.py` renders readable, traceable Markdown containing document title, author, page number, and source quote.
- `integration/obsidian/vault.py` is the only Vault writer.
- Read the Vault path and output subdirectory from config, add the date prefix, sanitize filenames, reject traversal, write only `.md`, append a sequence for collisions, and never overwrite existing notes.
- Surface configuration and I/O failures; do not silently discard knowledge.

## Configuration, Errors, and Privacy

- Only `config.py` reads environment variables or Streamlit secrets. Pass typed settings to consumers.
- Never hardcode, log, commit, or include API keys in exceptions. Do not log complete LLM request payloads.
- Keep local paper processing free of telemetry; only a user-invoked configured LLM/translation call sends the minimum required context over the network.
- Catch expected exceptions at the boundary that understands them. Never use bare `except:` or `except Exception: pass`.
- Unexpected failures should retain useful non-secret context and reach the UI as understandable errors.

## Code Quality

- Type all public functions and non-trivial internals.
- Give each function one responsibility and a concrete name.
- Split modules by ownership when they become hard to understand; do not split solely to meet a line-count rule.
- Prefer explicit control flow over metaprogramming, service locators, plugin frameworks, or premature generalization.
- Add comments for intent and constraints, not narration of obvious syntax.

## Finish Check

Before handing off a code change, confirm that UI calls only use cases, Domain stays pure, models use current names, explanation is ResearchContext-grounded, translation is independent, Vault writes are isolated and non-overwriting, secrets/config are centralized, errors are explicit, dependencies are justified, and the relevant tests were actually run under the `testing-review` workflow.
