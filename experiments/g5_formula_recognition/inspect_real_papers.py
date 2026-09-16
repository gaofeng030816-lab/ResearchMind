"""Build a local, path-free inspection set from explicitly approved PDFs.

This helper never calls a provider.  PDF bytes and rendered crops remain below the
chosen output directory, which is expected to be the experiment's ignored .build
directory.  The JSON report contains hashes and bounded geometry, not extracted
document text or absolute source paths.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Sequence

from researchmind.pdf import detect_formula_regions, open_pdf, render_formula_crop


SOURCE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
DEFAULT_MAX_CROPS_PER_PAPER = 60


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paper",
        action="append",
        required=True,
        metavar="SOURCE_ID=PDF_PATH",
        help="Repeat once for each explicitly approved local PDF.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--max-crops-per-paper",
        type=int,
        default=DEFAULT_MAX_CROPS_PER_PAPER,
    )
    args = parser.parse_args(argv)

    papers = tuple(parse_paper_spec(value) for value in args.paper)
    if len({source_id for source_id, _ in papers}) != len(papers):
        parser.error("Each paper needs a unique source id.")
    if args.max_crops_per_paper < 1 or args.max_crops_per_paper > 200:
        parser.error("--max-crops-per-paper must be between 1 and 200.")

    report_path = args.report or args.output_dir / "inspection.json"
    report = inspect_papers(
        papers,
        output_dir=args.output_dir,
        max_crops_per_paper=args.max_crops_per_paper,
    )
    _write_json_atomically(report_path, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


def parse_paper_spec(value: str) -> tuple[str, Path]:
    source_id, separator, raw_path = value.partition("=")
    normalized_id = source_id.strip().casefold()
    if not separator or not SOURCE_ID_PATTERN.fullmatch(normalized_id):
        raise argparse.ArgumentTypeError(
            "Paper must use a safe SOURCE_ID=PDF_PATH value."
        )
    path = Path(raw_path.strip())
    if not raw_path.strip():
        raise argparse.ArgumentTypeError("Paper path must not be empty.")
    return normalized_id, path


def inspect_papers(
    papers: Sequence[tuple[str, Path]],
    *,
    output_dir: Path,
    max_crops_per_paper: int = DEFAULT_MAX_CROPS_PER_PAPER,
) -> dict[str, Any]:
    if not papers:
        raise ValueError("At least one approved paper is required.")
    if max_crops_per_paper < 1 or max_crops_per_paper > 200:
        raise ValueError("Crop limit must be between 1 and 200.")

    output_dir.mkdir(parents=True, exist_ok=True)
    paper_rows: list[dict[str, Any]] = []
    total_candidates = 0
    total_crops = 0
    for source_id, source_path in papers:
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise ValueError("Paper source id is unsafe.")
        opened = open_pdf(source_path)
        all_regions = [
            region
            for page_number in range(1, opened.document.num_pages + 1)
            for region in detect_formula_regions(opened, page_number)
        ]
        ranked_regions = sorted(
            all_regions,
            key=lambda item: (
                -item.detector_confidence,
                item.page_number,
                item.bbox[1],
                item.bbox[0],
            ),
        )[:max_crops_per_paper]

        crop_dir = output_dir / source_id / "crops"
        crop_dir.mkdir(parents=True, exist_ok=True)
        candidates: list[dict[str, Any]] = []
        for index, region in enumerate(ranked_regions, start=1):
            crop = render_formula_crop(opened, region)
            crop_name = f"{source_id}-{index:03d}-p{region.page_number:03d}.png"
            crop_path = crop_dir / crop_name
            crop_path.write_bytes(crop.png_bytes)
            candidates.append(
                {
                    "candidate_id": f"{source_id}-{index:03d}",
                    "page_number": region.page_number,
                    "bbox": [round(value, 3) for value in region.bbox],
                    "kind": region.kind,
                    "source_kind": region.source_kind,
                    "detector_origin": region.detector_origin,
                    "detector_confidence": round(region.detector_confidence, 4),
                    "signals": list(region.signals),
                    "crop_file": crop_path.relative_to(output_dir).as_posix(),
                    "crop_sha256": crop.sha256,
                    "crop_byte_count": len(crop.png_bytes),
                    "crop_width_px": crop.width_px,
                    "crop_height_px": crop.height_px,
                }
            )

        byte_count = source_path.stat().st_size
        paper_rows.append(
            {
                "source_id": source_id,
                "source_filename": source_path.name,
                "source_sha256": opened.content_sha256,
                "source_byte_count": byte_count,
                "page_count": opened.document.num_pages,
                "detected_candidate_count": len(all_regions),
                "rendered_candidate_count": len(candidates),
                "candidates": candidates,
            }
        )
        total_candidates += len(all_regions)
        total_crops += len(candidates)

    return {
        "schema_version": 1,
        "purpose": "local_real_paper_formula_detection_and_annotation",
        "network_used": False,
        "source_paths_stored": False,
        "source_text_stored": False,
        "papers": paper_rows,
        "summary": {
            "paper_count": len(paper_rows),
            "page_count": sum(row["page_count"] for row in paper_rows),
            "detected_candidate_count": total_candidates,
            "rendered_candidate_count": total_crops,
        },
    }


def _write_json_atomically(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
