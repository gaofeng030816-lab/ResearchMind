# ResearchMind evaluation assets

This directory contains small, versioned evaluation inputs rather than copies of
the source papers. Each real-paper entry records a filename and SHA-256 digest so
that a developer who lawfully has the same paper can reproduce the extraction.
Short excerpts are retained only to exercise ResearchMind's deterministic domain
rules.

`v1_baseline/corpus.json` closes the T0 minimum corpus requirement for Selection,
ResearchContext, and formula/LaTeX behavior. Routine tests are offline: they do not
call an LLM, write a Vault, or require the original PDFs.
