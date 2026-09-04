# T6-C local performance benchmark

This benchmark uses only generated PDF, Python, and Markdown data in a system
temporary directory. It does not read `.env`, call an LLM, use the network, inspect
a user's repository, or write to a real Vault.

Run the release-gate workload from the repository root:

```powershell
& .\.venv\Scripts\python.exe .\evaluations\t6_c\benchmark.py
```

The default workload covers 100 extracted PDF pages, the approved 2,000-file code
limit, and 1,000 Markdown notes. Limits are user-wait-time guardrails rather than a
claim about every computer. A failed limit blocks T6-C completion until it is
investigated and rerun on the same machine.

The 2,000-file code workload and 1,000-note backup deliberately exercise hard/bulk
limits. Their blocking limits are 20 and 10 seconds on the T6-C Windows reference
machine; a code-index result above 10 seconds remains a documented optimization
signal even when it stays below the release-blocking limit.

Each operation is timed without `tracemalloc`, then repeated under `tracemalloc` for
an independent Python-allocation peak. This prevents memory-profiler overhead from
being reported as user-visible latency. Backup and restore use separate temporary
archive/target names for the second pass.
