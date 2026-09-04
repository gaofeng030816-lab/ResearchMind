"""Measure the isolated digital-formula recognizer on versioned local PDFs."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

import pymupdf

if __package__:
    from .formula_geometry import recognize_formula_candidates
    from .formula_vision import detect_embedded_formula_images
else:
    from formula_geometry import recognize_formula_candidates
    from formula_vision import detect_embedded_formula_images


DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument(
        "--sample",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Map one manifest id to a lawful local PDF; repeat for every document.",
    )
    args = parser.parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    samples = _parse_samples(args.sample)
    required_ids = {item["id"] for item in corpus["documents"]}
    if samples.keys() != required_ids:
        parser.error(
            "sample ids mismatch; "
            f"missing={sorted(required_ids - samples.keys()) or 'none'}, "
            f"unknown={sorted(samples.keys() - required_ids) or 'none'}"
        )

    results = {
        "schema_version": 1,
        "engine": "pymupdf-digital-text-geometry-spike",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pymupdf": importlib.metadata.version("PyMuPDF"),
        },
        "capability_boundary": {
            "digital_text_geometry": True,
            "bounded_formula_regions": True,
            "simple_deterministic_latex": True,
            "stacked_fraction_reconstruction": False,
            "matrix_reconstruction": False,
            "ocr": False,
            "image_formula_to_latex": False,
            "network_calls": False,
        },
        "documents": [
            _benchmark_document(item, samples[item["id"]])
            for item in corpus["documents"]
        ],
        "notes": [
            "Counts are observational and are not precision/recall without labels.",
            "No candidate text or absolute local path is stored in this output.",
            "LaTeX-ready means strict-parser-safe deterministic syntax, not semantic ground truth.",
        ],
    }
    print(json.dumps(results, ensure_ascii=True, indent=2))
    return 0


def _parse_samples(values: list[str]) -> dict[str, Path]:
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
    if _sha256(path).casefold() != str(spec["sha256"]).casefold():
        raise ValueError(f"SHA-256 mismatch for sample {spec['id']}")

    started = time.perf_counter()
    pages: list[dict[str, object]] = []
    with pymupdf.open(path) as document:
        for page_number in spec["sample_pages"]:
            page = document[int(page_number) - 1]
            candidates = recognize_formula_candidates(
                page,
                page_number=int(page_number),
            )
            image_candidates = detect_embedded_formula_images(
                page,
                page_number=int(page_number),
            )
            signal_counts = Counter(
                signal for candidate in candidates for signal in candidate.signals
            )
            pages.append(
                {
                    "page_number": page_number,
                    "candidate_count": len(candidates),
                    "kind_counts": dict(
                        sorted(Counter(item.kind for item in candidates).items())
                    ),
                    "latex_ready": sum(
                        item.latex_candidate is not None for item in candidates
                    ),
                    "needs_model": sum(item.needs_model for item in candidates),
                    "mean_confidence": round(
                        sum(item.confidence for item in candidates)
                        / max(1, len(candidates)),
                        3,
                    ),
                    "signal_counts": dict(sorted(signal_counts.items())),
                    "image_formula_candidate_count": len(image_candidates),
                    "image_formula_locators": [
                        {
                            "block_index": item.block_index,
                            "bbox": [round(value, 2) for value in item.bbox],
                            "origin": item.origin,
                        }
                        for item in image_candidates
                    ],
                    "locators": [
                        {
                            "source_lines": [
                                list(source_line)
                                for source_line in item.source_lines
                            ],
                            "bbox": [round(value, 2) for value in item.bbox],
                            "kind": item.kind,
                            "origin": item.origin,
                        }
                        for item in candidates
                    ],
                }
            )
    manual_labels = spec.get("manual_labels")
    detected_display = sum(
        page_result["kind_counts"].get("display", 0)
        for page_result in pages
    )
    detected_images = sum(
        page_result["image_formula_candidate_count"]
        for page_result in pages
    )
    return {
        "id": spec["id"],
        "filename": spec["filename"],
        "sha256_matches": True,
        "manual_labels": spec.get("manual_labels"),
        "manual_label_match": (
            None
            if manual_labels is None
            else {
                "digital_display_formula_regions": (
                    detected_display
                    == manual_labels["digital_display_formula_regions"]
                ),
                "image_formula_regions": (
                    detected_images == manual_labels["image_formula_regions"]
                ),
            }
        ),
        "sample_pages": pages,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


if __name__ == "__main__":
    raise SystemExit(main())
