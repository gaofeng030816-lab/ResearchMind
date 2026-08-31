# T2 PDF / Mathematics parser spike

This experiment compares ResearchMind's current PyMuPDF boundary with candidate
parser capabilities without changing production dependencies or models.

The versioned `corpus.json` contains filenames, SHA-256 digests, categories, and
sample pages only. It deliberately contains no user-specific absolute paths and no
copies of the papers. Run the current baseline by mapping every id to a lawful local
copy:

```powershell
& .\.venv\Scripts\python.exe `
  experiments\pdf_parser_spike\benchmark_current.py `
  --sample code_security=D:\path\2408.02509v1.pdf `
  --sample tidy_data=D:\path\tidy-data.pdf `
  --sample statistical_learning=D:\path\统计学习方法.pdf `
  --sample chinese_scan=D:\path\chinese_scan.pdf `
  --sample pdfua_invoice=D:\path\PDFUA-Ref-2-02_Invoice.pdf
```

The command prints JSON to stdout and never calls an LLM, OCR service, hybrid
backend, or network API. Timing is a local smoke measurement, not a universal
benchmark. `peak_python_bytes` covers Python-tracked allocations only; native
PyMuPDF memory is not included.

OpenDataLoader-PDF results and the adoption decision are recorded in
`docs/T2_PDF_MATHEMATICS_EVIDENCE.md`. Candidate output must not enter `src/` until
that record explicitly adopts it and defines conversion into ResearchMind models.
