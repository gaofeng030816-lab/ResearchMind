# V3-G4 note-composer browser acceptance

This directory contains the repeatable real-browser check used to close V3-G4. It is
an acceptance harness, not a runtime dependency and not a second note implementation.

`browser_acceptance.cjs` drives the production Streamlit app with Microsoft Edge and
expects an already running isolated instance containing one managed synthetic PDF.
Arguments are the Playwright module path, loopback origin, disposable Vault path, and
JSON report path. The harness:

- opens the managed paper and creates an explicit text selection;
- proves selection, evidence capture, local draft save, and preview do not write the
  Vault;
- proves unsaved editing cannot export an older preview;
- confirms one explicit Vault export contains the saved body and source provenance;
- starts a separate browser context and reopens the durable draft;
- rejects/records external requests and records page errors.

The 2026-09-09 acceptance used Edge 152.0.4191.66 on `127.0.0.1:8514`, passed 8/8
checks, and observed zero page errors and zero external requests. The synthetic PDF,
temporary SQLite data, report, logs, temporary Vault, and server process were deleted
after the user confirmed G4 acceptance. The durable evidence is recorded in
`docs/V3_G4_NOTE_COMPOSER_DECISION.md`.

Do not point this harness at a user's real library or Vault. Do not click translation
unless a fake provider is installed. The script does not authorize G5 formula work,
network use, or changes to the Obsidian writer contract.
