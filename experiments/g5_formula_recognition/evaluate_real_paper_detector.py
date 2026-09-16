"""Compare two path-free detector reports against fixed real-paper annotations."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any, Sequence

from experiments.g5_formula_recognition.inspect_real_papers import (
    _write_json_atomically,
)


DEFAULT_IOU_THRESHOLD = 0.9


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = evaluate_detector(
        _load_json(args.annotations),
        _load_json(args.baseline),
        _load_json(args.candidate),
    )
    _write_json_atomically(args.output, result)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    return 0 if result["optimization_guardrails_met"] else 2


def evaluate_detector(
    annotations: dict[str, Any],
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    *,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> dict[str, Any]:
    if not 0.5 <= iou_threshold <= 1.0:
        raise ValueError("IoU threshold must be between 0.5 and 1.0.")
    _validate_sources(annotations, baseline_report, label="baseline")
    _validate_sources(annotations, candidate_report, label="candidate")
    _validate_annotations_against_baseline(
        annotations,
        baseline_report,
        iou_threshold=iou_threshold,
    )
    candidate_pages = _candidates_by_page(candidate_report)

    recognition_rows = [
        _score_expected_region(
            case,
            candidate_pages,
            expected_detected=True,
            iou_threshold=iou_threshold,
        )
        for case in annotations["recognition_cases"]
    ]
    audit_rows = [
        _score_expected_region(
            case,
            candidate_pages,
            expected_detected=case["expected_detected"],
            iou_threshold=iou_threshold,
        )
        for case in annotations["detector_audit_cases"]
    ]

    baseline_count = _candidate_count(baseline_report)
    candidate_count = _candidate_count(candidate_report)
    recognition_recall = _rate(row["detected"] for row in recognition_rows)
    complete_rows = [row for row in audit_rows if row["expected_detected"]]
    reject_rows = [row for row in audit_rows if not row["expected_detected"]]
    complete_retention = _rate(row["detected"] for row in complete_rows)
    unwanted_rejection = _rate(not row["detected"] for row in reject_rows)
    audit_accuracy = _rate(row["correct"] for row in audit_rows)
    reduction = (
        0.0
        if baseline_count == 0
        else round((baseline_count - candidate_count) / baseline_count, 6)
    )
    guardrails_met = (
        recognition_recall == 1.0
        and complete_retention == 1.0
        and candidate_count <= baseline_count
    )
    return {
        "schema_version": 1,
        "purpose": "real_paper_formula_detector_before_after_evaluation",
        "iou_threshold": iou_threshold,
        "paths_stored": False,
        "source_text_stored": False,
        "optimization_guardrails_met": guardrails_met,
        "metrics": {
            "paper_count": len(annotations["papers"]),
            "recognition_case_count": len(recognition_rows),
            "recognition_case_recall": recognition_recall,
            "audit_case_count": len(audit_rows),
            "audit_accuracy": audit_accuracy,
            "complete_formula_retention": complete_retention,
            "unwanted_candidate_rejection": unwanted_rejection,
            "baseline_candidate_count": baseline_count,
            "candidate_candidate_count": candidate_count,
            "candidate_reduction_rate": reduction,
        },
        "recognition_cases": recognition_rows,
        "audit_cases": audit_rows,
        "remaining_audit_failures": [
            row["id"] for row in audit_rows if not row["correct"]
        ],
        "limitations": [
            "The audit set is deliberately small and is not a population precision estimate.",
            "Detector retention does not prove recognizer LaTeX quality.",
            "No PDF or crop was transmitted while producing this comparison.",
        ],
    }


def _score_expected_region(
    case: dict[str, Any],
    candidate_pages: dict[tuple[str, int], list[dict[str, Any]]],
    *,
    expected_detected: bool,
    iou_threshold: float,
) -> dict[str, Any]:
    candidates = candidate_pages.get((case["source_id"], case["page_number"]), [])
    best_iou = max(
        (_bbox_iou(case["bbox"], item["bbox"]) for item in candidates),
        default=0.0,
    )
    detected = best_iou >= iou_threshold
    return {
        "id": case["id"],
        "expected_detected": expected_detected,
        "detected": detected,
        "correct": detected == expected_detected,
        "best_iou": round(best_iou, 6),
    }


def _validate_sources(
    annotations: dict[str, Any],
    report: dict[str, Any],
    *,
    label: str,
) -> None:
    expected = {
        item["source_id"]: item["source_sha256"]
        for item in annotations.get("papers", [])
    }
    actual = {
        item["source_id"]: item["source_sha256"]
        for item in report.get("papers", [])
    }
    if actual != expected:
        raise ValueError(f"The {label} report does not match the annotated sources.")


def _candidates_by_page(
    report: dict[str, Any],
) -> dict[tuple[str, int], list[dict[str, Any]]]:
    result: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for paper in report["papers"]:
        for candidate in paper["candidates"]:
            result.setdefault(
                (paper["source_id"], candidate["page_number"]), []
            ).append(candidate)
    return result


def _validate_annotations_against_baseline(
    annotations: dict[str, Any],
    baseline_report: dict[str, Any],
    *,
    iou_threshold: float,
) -> None:
    baseline_pages = _candidates_by_page(baseline_report)
    cases = [
        *annotations.get("recognition_cases", []),
        *annotations.get("detector_audit_cases", []),
    ]
    for case in cases:
        candidates = baseline_pages.get(
            (case["source_id"], case["page_number"]), []
        )
        if not candidates:
            raise ValueError(f"Baseline candidate is missing for {case['id']}.")
        best = max(candidates, key=lambda item: _bbox_iou(case["bbox"], item["bbox"]))
        if _bbox_iou(case["bbox"], best["bbox"]) < iou_threshold:
            raise ValueError(f"Baseline geometry does not match {case['id']}.")
        crop_sha256 = case.get("crop_sha256")
        if (
            not isinstance(crop_sha256, str)
            or len(crop_sha256) != 64
            or crop_sha256 != best.get("crop_sha256")
        ):
            raise ValueError(f"Baseline crop hash does not match {case['id']}.")


def _candidate_count(report: dict[str, Any]) -> int:
    return sum(item["detected_candidate_count"] for item in report["papers"])


def _bbox_iou(first: Sequence[float], second: Sequence[float]) -> float:
    intersection_width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    intersection_height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    intersection = intersection_width * intersection_height
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else intersection / union


def _rate(values: Iterable[bool]) -> float:
    items = list(values)
    return 1.0 if not items else round(sum(items) / len(items), 6)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Evaluation inputs must be JSON objects.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
