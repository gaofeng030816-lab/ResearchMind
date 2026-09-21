# V3-G7 hardening benchmark

This benchmark uses only temporary synthetic data. It creates bounded managed code
records and durable note drafts, lists them, backs up the complete local library,
restores it into an absent directory, and verifies the restored counts.

Run it from the repository root:

```powershell
.\.venv\Scripts\python.exe evaluations\g7\hardening_benchmark.py
```

The limits are local internal-acceptance blockers, not public performance promises.
The benchmark does not read `.env`, user papers, code projects, Zotero, or Obsidian,
and it never uses the network.

## Browser multilingual acceptance

`browser_multilingual_acceptance.cjs` checks the production Streamlit workspace
against a five-file synthetic project. It verifies Python/C/Java/Julia/R selection
provenance, keeps T5-B1 Python-only, checks the graceful Zotero-disabled state, and
fails if the journey observes an external request or page error.

It uses an existing temporary `playwright-core` installation and the installed
Microsoft Edge browser; neither is a ResearchMind runtime dependency:

```powershell
node evaluations\g7\browser_multilingual_acceptance.cjs <playwright-root> <origin> <code-root> <report.json>
```
