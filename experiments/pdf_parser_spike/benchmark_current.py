"""Measure the current ResearchMind PDF boundary on the versioned T2 corpus."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
import tracemalloc
from collections import Counter
from pathlib import Path

from researchmind.app.use_cases import open_pdf
from researchmind.config import Settings
from researchmind.pdf import render_page_image


DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS_PATH,
        help="Versioned corpus manifest.",
    )
    parser.add_argument(
        "--sample",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Map one manifest id to a local PDF; repeat for every document.",
    )
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    sample_paths = _parse_sample_paths(args.sample)
    documents = corpus["documents"]
    required_ids = {document["id"] for document in documents}
    missing_ids = sorted(required_ids - sample_paths.keys())
    unknown_ids = sorted(sample_paths.keys() - required_ids)
    if missing_ids or unknown_ids:
        parser.error(
            f"sample ids mismatch; missing={missing_ids or 'none'}, "
            f"unknown={unknown_ids or 'none'}"
        )

    results = {
        "schema_version": 1,
        "engine": "researchmind-pymupdf",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pymupdf": importlib.metadata.version("PyMuPDF"),
        },
        "capability_boundary": {
            "text_blocks_and_bbox": True,
            "embedded_raster_regions": True,
            "formula_text_candidates": True,
            "semantic_tables": False,
            "ocr": False,
            "image_formula_to_latex": False,
            "vector_chart_understanding": False,
        },
        "documents": [
            _benchmark_document(document, sample_paths[document["id"]])
            for document in documents
        ],
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def _parse_sample_paths(values: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values:
        sample_id, separator, path_text = value.partition("=")
        if not separator or not sample_id.strip() or not path_text.strip():
            raise ValueError(f"Invalid --sample value: {value!r}")
        if sample_id in parsed:
            raise ValueError(f"Duplicate --sample id: {sample_id}")
        parsed[sample_id] = Path(path_text)
    return parsed


def _benchmark_document(spec: dict[str, object], path: Path) -> dict[str, object]:
    actual_sha256 = _sha256(path)
    if actual_sha256.casefold() != str(spec["sha256"]).casefold():
        raise ValueError(f"SHA-256 mismatch for sample {spec['id']}")

    tracemalloc.start()
    started = time.perf_counter()
    opened = open_pdf(path, settings=Settings())
    parse_seconds = time.perf_counter() - started
    _, peak_python_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    role_counts = Counter(
        block.role
        for page in opened.pages
        for block in page.blocks
    )
    render_results = []
    for page_number in spec["sample_pages"]:
        render_started = time.perf_counter()
        image_png = render_page_image(opened, page_number, zoom=1.0)
        render_results.append(
            {
                "page_number": page_number,
                "seconds": round(time.perf_counter() - render_started, 6),
                "png_bytes": len(image_png),
            }
        )

    total_pages = opened.document.num_pages
    return {
        "id": spec["id"],
        "filename": spec["filename"],
        "sha256_matches": True,
        "categories": spec["categories"],
        "total_pages": total_pages,
        "pages_with_text": sum(bool(page.text.strip()) for page in opened.pages),
        "total_text_characters": sum(len(page.text) for page in opened.pages),
        "total_blocks": sum(len(page.blocks) for page in opened.pages),
        "role_counts": dict(sorted(role_counts.items())),
        "figure_regions": sum(len(page.figures) for page in opened.pages),
        "parse_seconds": round(parse_seconds, 6),
        "parse_seconds_per_page": round(parse_seconds / total_pages, 6),
        "peak_python_bytes": peak_python_bytes,
        "render_samples": render_results,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


if __name__ == "__main__":
    raise SystemExit(main())
