"""Score the 18-case real-paper formula recognition run."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from statistics import median
from typing import Any, Sequence

from experiments.g5_formula_recognition.evaluation import evaluate_predictions


REAL_PAPER_THRESHOLDS = {
    "coverage": 0.85,
    "strict_valid_rate": 1.0,
    "mean_token_similarity": 0.95,
    "structural_exact_rate": 0.90,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = evaluate_real_paper_predictions(
        _load_json(args.annotations),
        _load_json(args.predictions),
    )
    _write_json_atomically(args.output, result)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    return 0 if result["real_paper_quality_thresholds_met"] else 2


def evaluate_real_paper_predictions(
    annotations: dict[str, Any],
    predictions: dict[str, Any],
) -> dict[str, Any]:
    cases = annotations.get("recognition_cases")
    if annotations.get("schema_version") != 1 or not isinstance(cases, list):
        raise ValueError("Unsupported real-paper annotations.")
    if len(cases) != 18:
        raise ValueError("The real-paper recognition corpus must contain 18 cases.")
    authorization = predictions.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("case_count") != 18:
        raise ValueError("The prediction document lacks the bounded authorization record.")

    scored = evaluate_predictions({"cases": cases}, predictions)
    elapsed = sorted(float(row["elapsed_ms"]) for row in scored["cases"])
    metrics = dict(scored["metrics"])
    metrics.update(
        median_elapsed_ms=round(median(elapsed), 3),
        p95_elapsed_ms=round(_percentile(elapsed, 0.95), 3),
        max_elapsed_ms=round(max(elapsed), 3),
    )
    annotation_status = str(annotations.get("annotation_status", "unknown"))
    human_spot_check_required = annotation_status != "human_verified"
    real_paper_threshold_checks = {
        name: float(metrics[name]) >= threshold
        for name, threshold in REAL_PAPER_THRESHOLDS.items()
    }
    case_sources = {item["id"]: item["source_id"] for item in cases}
    return {
        "schema_version": 1,
        "purpose": "real_paper_remote_formula_recognition_quality",
        "annotation_status": annotation_status,
        "human_spot_check_required": human_spot_check_required,
        "real_paper_quality_thresholds_met": all(
            real_paper_threshold_checks.values()
        ),
        "source_tex_recovery_thresholds_met": scored["adoption_thresholds_met"],
        "metrics": metrics,
        "real_paper_thresholds": REAL_PAPER_THRESHOLDS,
        "real_paper_threshold_checks": real_paper_threshold_checks,
        "source_tex_diagnostic_thresholds": scored["thresholds"],
        "source_tex_diagnostic_checks": scored["threshold_checks"],
        "categories": scored["categories"],
        "papers": {
            source_id: _summarize_rows(
                [row for row in scored["cases"] if case_sources[row["id"]] == source_id]
            )
            for source_id in sorted(set(case_sources.values()))
        },
        "cases": scored["cases"],
        "limitations": [
            "Reference LaTeX is an agent visual first pass until human spot-checking.",
            "The selected 18 crops are a bounded evaluation set, not training data.",
            "Normalized exact is diagnostic for source-notation recovery and is not a real-paper candidate-usability threshold.",
            "A remote comparison does not adopt a local model or replace explicit candidate editing and acceptance.",
        ],
    }


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    total = len(rows)
    return {
        "total": total,
        "successful": sum(row["status"] == "ok" for row in rows),
        "normalized_exact_rate": round(
            sum(row["normalized_exact"] for row in rows) / max(total, 1), 6
        ),
        "mean_token_similarity": round(
            sum(float(row["token_similarity"]) for row in rows) / max(total, 1), 6
        ),
        "structural_exact_rate": round(
            sum(row["structural_exact"] for row in rows) / max(total, 1), 6
        ),
    }


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = max(0, min(len(values) - 1, int(len(values) * quantile + 0.999999) - 1))
    return values[index]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("G5 evaluation inputs must be JSON objects.")
    return value


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
