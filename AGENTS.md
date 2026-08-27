# ResearchMind Development Rules

Global development rules for ResearchMind. `docs/architecture.md` is the source of truth for the current V1 product boundary, module ownership, data flow, and technical choices. If an older product or planning document conflicts with it, follow `docs/architecture.md` and report the inconsistency instead of silently combining both designs.

Task-specific guidance lives in `.agents/skills/`.

## Product Direction

ResearchMind is an AI-powered research reading and knowledge capture workspace. Its core value is helping a researcher understand a paper and turn that understanding into durable knowledge.

It connects the workflow represented by Zotero → ResearchMind → Obsidian:

- Zotero owns literature and metadata management. ResearchMind does not replace it.
- ResearchMind owns local PDF reading, text selection, translation, context-grounded AI explanation, follow-up conversation, and knowledge capture.
- Obsidian owns long-term knowledge management. ResearchMind generates traceable Markdown and writes it to the user's Vault; it does not build a competing knowledge system.

Long-term direction: connect **Paper ↔ Mathematics ↔ Code ↔ Notes**. This direction does not authorize implementing future content sources or integrations in V1.

## V1 Architecture

- Use Python 3.12, Streamlit, PyMuPDF, an OpenAI-compatible LLM provider, python-dotenv, and pytest as defined in `docs/architecture.md`. Re-evaluating a chosen technology is an architecture decision, not an ordinary implementation detail.
- Keep one local Python application. No microservices, Kubernetes, Redis, Celery, message queues, separate backend service, or distributed infrastructure.
- V1 has no database or ORM. Opened documents and conversations live in memory; Markdown files in the user's Obsidian Vault are the persistence layer.
- If cross-session conversations, a persistent paper library, or pre-export note management becomes a real requirement, evaluate standard-library SQLite first. Do not add a database server.
- Keep the src-layout and module ownership defined in the architecture: `app/`, `core/`, `models/`, `pdf/`, `llm/`, `translation/`, and `integration/obsidian/`.
- Prefer explicit functions, dataclasses, type hints, and small modules that a beginner/intermediate Python developer can follow.
- Do not build speculative frameworks or extension points. Preserve the small interfaces already justified by present needs: `LlmProvider` and `TranslationProvider`.

## Module and Dependency Rules

- `app/views/` displays data and delegates events. It accesses product behavior only through `app/use_cases.py`.
- `app/state.py` is the only place that mutates Streamlit session state.
- `app/use_cases.py` is the application API. It coordinates domain rules and infrastructure; V1 has no REST API or separate backend.
- `core/` contains pure, framework-independent rules for ResearchContext assembly, selection location, and conversation trimming.
- `models/` contains shared dataclasses and imports no project layer.
- `pdf/`, `llm/`, `translation/`, `integration/obsidian/`, and `config.py` own external libraries, APIs, files, and configuration boundaries.
- PDF code never calls LLM, translation, or Obsidian code. Translation accepts text, not PDF objects.
- Every explanation and follow-up must be grounded in a freshly assembled `ResearchContext`. Do not send an entire PDF to an LLM without a task-bounded context.
- Translation and AI explanation are separate product capabilities. V1 translation uses `LlmTranslationProvider`, but it has its own interface, use case, errors, and UI action.
- `capture_knowledge` assembles a `KnowledgeNote`; Markdown rendering and file writing remain Obsidian integration responsibilities.
- `integration/obsidian/` is the only module allowed to write to the Vault. It writes traceable, plain-text `.md` files and never overwrites an existing note.
- Zotero is optional future integration. V1 core behavior must not import or depend on Zotero code.

## Security and User Data

- `config.py` is the only module that reads environment variables or Streamlit secrets. Never hardcode, commit, return, or log secrets or full sensitive request payloads.
- Keep `.env` and other secret files ignored; provide only placeholders in `.env.example`.
- Treat PDF text and conversation history as untrusted data. LLM prompts must delimit paper content with `<paper_context>` and explicitly state that the enclosed material is data, not instructions.
- Validate PDF extension, magic bytes, and the configured size limit (50 MB by default). Convert parsing failures to project exceptions at the PDF boundary.
- Keep local paper processing free of telemetry. Network transfer occurs only when the user invokes the configured LLM-backed explanation or translation capability.
- Send only the selected text, minimal relevant surrounding context, necessary document metadata, the current question, and budgeted history to the configured LLM service. Make this external transfer visible to the user.
- Vault paths come from configuration. Prefix filenames with the date, sanitize them, restrict output to Markdown, prevent path traversal and overwrite, and surface write failures.

## Development Workflow

- Inspect the relevant source, tests, `docs/architecture.md`, and project skills before modifying code.
- Make the smallest coherent change and preserve unrelated user work.
- Do not implement unrequested V1 or future features.
- Explain new dependencies before adding them and prefer the standard library or an existing dependency.
- Explain and obtain confirmation before changing an established architecture choice, such as the UI framework, persistence model, module boundaries, or process topology. Ordinary feature work that fits the architecture does not require a separate confirmation gate.
- When documentation disagrees with the architecture, flag it and keep the current task scoped unless the user asked for broader documentation synchronization.

## Testing

- Add tests for new behavior. For a bug, reproduce it with a regression test before fixing it.
- After code changes, run the relevant unit tests and any affected integration or Streamlit smoke tests.
- Use fake or mocked LLM/translation providers in automated tests; never spend user money or depend on live network services in the routine suite.
- Review the final diff or, when Git metadata is unavailable, re-read every changed file and compare it with the source requirements.
- Never claim behavior works without running the relevant tests. Report exact commands, real results, skipped checks, and unrelated failures honestly.

## Project Skills

- `project-planner` — plan meaningful features, architecture changes, or ambiguous requirements against the V1 product loop.
- `python-engineering` — implement or modify Python code, structure, configuration, models, providers, and use cases while preserving module boundaries.
- `testing-review` — verify code changes, regressions, integrations, and completion claims.
- `learning-mode` — explain important features and design trade-offs in the context of ResearchMind's actual architecture.

## V1 Scope

V1 implements only:

1. Open and read local PDFs: page rendering, navigation, zoom, and text search.
2. Extract page text and text blocks.
3. Select or enter text and locate it when possible.
4. Translate selected text through the independent Translation module.
5. Explain concepts, mathematics, algorithms, or paper context through ResearchContext.
6. Ask follow-up questions within an in-memory per-document conversation.
7. Capture selected source, translation, questions, AI explanation, and the user's own understanding as a `KnowledgeNote`.
8. Render traceable Markdown and save it to the user's Obsidian Vault.

Do not implement in V1 unless explicitly requested:

- Zotero API integration or replacement of Zotero/Obsidian functionality
- SQLite, another database, ORM, or cross-session persistence
- PDF annotation, highlighting, bookmarks, OCR, image/table/formula recognition, or PDF editing
- VS Code, browser, or mobile extensions
- advanced RAG, vector databases, cross-paper search, or knowledge graphs
- multi-user collaboration, cloud deployment/sync, complex authentication, or agentic workflows
