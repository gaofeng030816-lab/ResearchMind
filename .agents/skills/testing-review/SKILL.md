---
name: testing-review
description: Verify ResearchMind V3 stages and preserve the accepted V2 baseline with regression-first unit, integration, migration, Streamlit, browser-manual, corpus-quality, security, and recovery evidence. Use for completion claims, architecture gates, database/import/Zotero/PDF/formula/multilingual-code/note changes, and scoped fixes.
---

# Testing and Review

Code is complete only after the changed behavior has been exercised. Inspection does
not replace execution. docs/ARCHITECTURE.md defines implemented behavior;
V2 to V3过渡要求.md defines the active V3 exit evidence.

## Baseline

The accepted local V2 baseline is 2.0.0rc1 with 269 passed and one Windows symlink
environment skip, plus the recorded wheel, launcher, security, recovery, performance,
and user-confirmed journeys. Treat those records as historical evidence; rerun checks
affected by a V3 change and never relabel a manual result as automation.

The implemented V3-G1 increment has a 316-passed full regression with the same one
Windows symlink environment skip. Its durable-library gate additionally protects
schema/migration/foreign-key behavior, managed-file compensation, restart open,
deduplication/revisions, deletion semantics, backup/restore, native upload handoff,
and managed-code read-only behavior. Real browser file selection is still manual
evidence; AppTest must not be described as proving click/drag behavior.

G2's metadata/source-link implementation and automated regression evidence are in
docs/V3_G2_ZOTERO_VALIDATION.md. The approved Windows copy uses /file/view/url and
locked local handles, not the obsolete HTTP-200 PDF prototype. Verify rejected
redirects, network paths/drives, traversal, junctions/hardlinks, concurrent writes/
rename/delete, bounded bytes, source-version/URL changes, consent invalidation,
G1 parser/hash/storage and failed-link compensation. Use only synthetic files.
G2 is Completed: the user confirmed manual acceptance on 2026-09-04; the recorded
regression is 374 passed / 1 environment skip. Keep user-reported manual evidence
separate from agent-observed execution and fake HTTP/AppTest. G3 is also Completed.
Its isolated evidence covers five representative PDFs with 12/12 sampled digital
selections, PyMuPDF reconciliation, cross-line/multi-instance behavior, wheel/
shortcut/layout checks, long-document payload reuse, and an installed experimental
wheel. The user separately reported physical-trackpad acceptance and approved formal
adoption on 2026-09-07. Production Edge acceptance then passed 8/8 with 0 page errors
and 0 external requests; the 1,041,404-byte wheel has exactly one JS/CSS plus manifest
and license, and the combined regression is 486 passed / 1 environment skip. See
docs/V3_G3_PDF_WORKSPACE_SPIKE.md. G4 is Completed after the user's 2026-09-09
acceptance. It adds schema-v3 draft/evidence persistence, exact translation preview,
click-only provider calls, source binding, explicit include/order/remove UI, editable
Markdown, local save, revision/SHA-256-bound preview and confirmed non-overwriting
Vault output. Final evidence is 42 focused checks, 425 production tests / 1 skip,
524 tests / 1 skip with G3 experiments, and Edge 152 8/8 with 0 page errors and
0 external requests. Read docs/V3_G4_NOTE_COMPOSER_DECISION.md for exact scope and
limitations. G5 is Completed with 48 focused checks, 21 Streamlit AppTests,
474 production tests / 1 existing Windows symlink environment skip, and 573 tests /
1 skip with G3 experiments. Its 20 synthetic crops pass all fixed thresholds; 18
authorized real crops are 100% strict-valid, 95.09% token and 100% structural but only
11.11% normalized exact. Preserve that limitation, the three known detector
false/over-merged cases, the one-crop consent boundary and the Edge 152 fake-provider
journey. Read docs/V3_G5_FORMULA_RECOGNITION_DECISION.md.

Protect this loop in proportion to the change:

    open/read/search/select
    → translate or constrained LaTeX or explain/follow-up
    → explicit KnowledgeNote preview
    → non-overwriting Obsidian save

Also protect the completed V3-G4 loop:

    verified ReadingSelection → exact transfer preview → explicit translation
    → explicit evidence basket → explicit local draft save
    → deterministic current-revision preview → confirmed exact-byte Vault save

Also preserve independent code reading, user-confirmed evidence links, T5-A read-only
authority, T5-B1's narrow Python recovery contract, and Code-to-Obsidian capture.

## Verification Loop

1. Review scope, ownership, types, privacy, paths, transactions, errors, and secrets.
2. Run the narrowest focused tests.
3. Run affected integration and migration tests.
4. Run Streamlit AppTest for state, navigation, and native widgets.
5. Use real-browser/manual evidence for CCv2 DOM selection, shortcuts, scroll/wheel,
   responsive layout, and other behavior AppTest cannot prove.
6. Run corpus/benchmark evidence for extraction, formula, parser, or performance claims.
7. Run the affected V2 regression suite, review the final diff, and report exact
   results, skips, and limitations.

Routine tests use fake LLM/translation/formula/Zotero providers, temporary databases,
temporary managed storage, disposable code projects, and temporary Vaults. They never
read the user's real library, Zotero database, Vault, key, private PDF, or repository,
and never call a paid/live network service.

## V3 Gate Coverage

### Local library and import

- schema creation and every supported forward migration;
- transaction rollback, foreign keys, duplicate hash/source key behavior, concurrent
  or interrupted writes, and corrupted/unsupported versions;
- managed-file staging/atomic rename, filename/path traversal, extension/magic/size
  validation, orphan cleanup, and database/file consistency;
- clear unlink, remove-record, and delete-managed-copy semantics;
- restart persistence, backup/restore, and no deletion of externally owned files;
- native single PDF and directory upload flows with server-side revalidation.

### Zotero

- fake local HTTP boundary, disabled-local-API 403, unavailable client, malformed
  responses, version headers, pagination/limits when applicable, and duplicate links;
- partition cached records by Zotero server/library identity;
- read-only local integration first; routine tests do not contact localhost or Web API;
- no Zotero dependency in the core library path and no direct Zotero SQLite access.
- redirects and traversal rejected before a second/unsafe request; fake transport
  remains mandatory even when exercising rejection tests;
- source association is not proof of PDF identity; repeated import and changed
  attachment cases must not silently relabel existing managed content;
- confirmation belongs to the selected source/revision/attachment and target paper;
  failed reads clear stale actions, and managed deletion requires explicit unlink.

### PDF text-layer and adaptive UI

- component event parsing, current-document/revision validation, page/span/bbox
  provenance, rerun hydration, duplicate/stale event rejection, and failure fallback;
- real-browser selection/copy, double-column order, nested scroll ownership, wheel
  debounce/bounds/trackpad, focus, keyboard shortcut suppression while typing, and
  cleanup;
- paper-only full-width, paper+code split, and narrow-screen fallback;
- preserve PyMuPDF parser/search/context behavior until an adoption gate changes it.

### Translation and note composer

- selection translation receives exactly selected text and target language;
- user chooses evidence explicitly; unselected turns never enter the draft;
- Markdown is editable without a write, preview reflects the edited value, stale
  evidence is visible, and only explicit save reaches the existing Vault writer;
- collision non-overwrite, path safety, invalidation, restart behavior, and no false
  success after database/Vault failure.

### Formula recognition

- labeled crops for integrals, sums, limits, fractions, roots, matrices, aligned
  equations, Greek symbols, scripts, and equation numbers;
- detector misses/false positives and structural/symbol match, not only HTTP success;
- strict LaTeX rejection, user edit/acceptance, provenance, crop-only transfer, fake
  provider errors, latency/memory, and no whole-paper upload;
- keep corpus/evaluator code outside production imports; adopted production code must
  continue to pass the same locked-crop and fake-provider boundaries.

### Multilingual code

- temporary Python, C, Java, Julia, and R projects with file limits/exclusions,
  encoding failures, symlink/root containment, relative locators, functions/types/
  methods where the language supports them, and parser errors;
- project-model mapping and Python parity;
- context budget, injection defense, preview/request parity, absolute-path omission,
  and a sentinel proving source was never imported or executed;
- adding languages does not extend T5-B1 writes or authorize shell/tests/installers.

## Evidence Categories

Report these separately:

- API connectivity;
- migration/data integrity;
- selection/location correctness;
- context and answer quality;
- formula/parser quality;
- visual/browser usability;
- privacy/security;
- performance and recovery.

An HTTP success, passing unit test, or screenshot cannot substitute for another
category.

## Documentation and Skill Changes

For documentation-only work, a full pytest run is not mandatory. Validate every
changed Skill with the official quick validator, inspect links/terminology, search for
stale stage claims, and review the Git diff.

## Reporting

End completed work with:

- **Changed:** files and observable behavior;
- **Tested:** exact commands and scope;
- **Result:** real counts/results;
- **Remaining:** skipped, manual, environment, quality, or unrelated limitations.

Leave a gate open when any required migration, privacy, corpus, browser-manual,
security, recovery, or regression evidence is missing.
