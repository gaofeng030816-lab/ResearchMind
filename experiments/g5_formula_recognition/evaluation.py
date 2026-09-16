"""Clean-room quality metrics for bounded image-to-LaTeX recognizers."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any

from researchmind.llm.errors import LlmBadResponseError
from researchmind.llm.latex import parse_latex_response


DEFAULT_MANIFEST = Path(__file__).with_name("corpus.json")
TOKEN_PATTERN = re.compile(
    r"\\\\|\\[A-Za-z]+|\\.|[A-Za-z]+|\d+(?:\.\d+)?|[{}_^&]|[^\s]"
)
MATRIX_ENVIRONMENTS = frozenset(
    {"matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix"}
)
GREEK_COMMANDS = frozenset(
    {
        "\\alpha", "\\beta", "\\gamma", "\\delta", "\\theta",
        "\\lambda", "\\mu", "\\pi", "\\rho", "\\sigma",
        "\\phi", "\\omega", "\\Omega", "\\varepsilon",
    }
)
ADOPTION_THRESHOLDS = {
    "coverage": 0.85,
    "strict_valid_rate": 1.0,
    "normalized_exact_rate": 0.75,
    "mean_token_similarity": 0.95,
    "structural_exact_rate": 0.90,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    result = evaluate_predictions(
        load_manifest(args.manifest),
        json.loads(args.predictions.read_text(encoding="utf-8")),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["adoption_thresholds_met"] else 2


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cases = manifest.get("cases")
    if manifest.get("schema_version") != 1 or not isinstance(cases, list):
        raise ValueError("Unsupported G5 corpus manifest")
    if len(cases) != 20:
        raise ValueError("The G5 corpus must contain exactly 20 formula crops")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(cases) or len(set(ids)) != len(ids):
        raise ValueError("The G5 corpus needs unique case ids")
    return manifest


def evaluate_predictions(
    manifest: dict[str, Any],
    prediction_document: object,
) -> dict[str, Any]:
    cases = manifest["cases"]
    predictions = _prediction_map(prediction_document)
    case_ids = {case["id"] for case in cases}
    if predictions.keys() != case_ids:
        raise ValueError(
            "Prediction ids must exactly match the corpus; "
            f"missing={sorted(case_ids - predictions.keys())}, "
            f"unknown={sorted(predictions.keys() - case_ids)}"
        )

    rows: list[dict[str, Any]] = []
    category_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        prediction = predictions[case["id"]]
        row = _score_case(case, prediction)
        rows.append(row)
        for category in case["categories"]:
            category_rows[category].append(row)

    summary = _summarize(rows)
    threshold_checks = {
        name: summary[name] >= threshold
        for name, threshold in ADOPTION_THRESHOLDS.items()
    }
    return {
        "schema_version": 1,
        "case_count": len(rows),
        "metrics": summary,
        "thresholds": ADOPTION_THRESHOLDS,
        "threshold_checks": threshold_checks,
        "adoption_thresholds_met": all(threshold_checks.values()),
        "categories": {
            name: _summarize(items)
            for name, items in sorted(category_rows.items())
        },
        "cases": rows,
        "notes": [
            "Whitespace, left/right sizing commands, and braces around a one-token script are normalized only for scoring.",
            "A passing syntax check is not mathematical correctness.",
            "The gate requires local and remote candidates to use the same crops.",
        ],
    }


def tokenize_latex(expression: str) -> tuple[str, ...]:
    tokens = TOKEN_PATTERN.findall(expression.strip())
    filtered = tuple(
        token for token in tokens if token not in {"\\left", "\\right"}
    )
    return _collapse_single_token_script_braces(filtered)


def _collapse_single_token_script_braces(
    tokens: tuple[str, ...],
) -> tuple[str, ...]:
    """Treat one-token braced and unbraced scripts as scoring equivalents."""

    result: list[str] = []
    index = 0
    while index < len(tokens):
        if (
            index + 3 < len(tokens)
            and tokens[index] in {"_", "^"}
            and tokens[index + 1] == "{"
            and tokens[index + 3] == "}"
            and tokens[index + 2] not in {"{", "}"}
            and (
                tokens[index + 2].startswith("\\")
                or len(tokens[index + 2]) == 1
            )
        ):
            result.extend((tokens[index], tokens[index + 2]))
            index += 4
            continue
        result.append(tokens[index])
        index += 1
    return tuple(result)


def normalize_latex(expression: str) -> str:
    return " ".join(tokenize_latex(expression)).replace("\\dfrac", "\\frac").replace(
        "\\tfrac", "\\frac"
    )


def token_similarity(reference: str, prediction: str) -> float:
    left = tokenize_latex(reference)
    right = tokenize_latex(prediction)
    length = max(len(left), len(right))
    if length == 0:
        return 1.0
    return round(1.0 - _levenshtein(left, right) / length, 6)


def structural_signature(expression: str) -> Counter[str]:
    tokens = tokenize_latex(expression)
    signature: Counter[str] = Counter()
    command_features = {
        "\\int": "integral",
        "\\iint": "integral",
        "\\iiint": "integral",
        "\\oint": "contour_integral",
        "\\sum": "sum",
        "\\prod": "product",
        "\\lim": "limit",
        "\\frac": "fraction",
        "\\dfrac": "fraction",
        "\\tfrac": "fraction",
        "\\sqrt": "root",
        "\\tag": "equation_number",
    }
    for token in tokens:
        if token in command_features:
            signature[command_features[token]] += 1
        if token == "_":
            signature["subscript"] += 1
        elif token == "^":
            signature["superscript"] += 1
        elif token == "&":
            signature["alignment_column"] += 1
        elif token == "\\\\":
            signature["alignment_row"] += 1
        elif token in GREEK_COMMANDS:
            signature["greek"] += 1

    for match in re.finditer(r"\\begin\{([^{}]+)\}", expression):
        environment = match.group(1)
        if environment in MATRIX_ENVIRONMENTS:
            signature["matrix"] += 1
        elif environment in {"aligned", "alignedat", "cases", "split"}:
            signature[f"environment:{environment}"] += 1
    return signature


def _score_case(case: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    status = prediction["status"]
    latex = prediction.get("latex")
    valid = False
    invalid_reason: str | None = None
    exact = False
    similarity = 0.0
    structure_exact = False
    if status == "ok":
        try:
            parse_latex_response(f"<latex>{latex}</latex>")
            valid = True
        except LlmBadResponseError as error:
            invalid_reason = str(error)
        if valid:
            reference = case["reference_latex"]
            exact = normalize_latex(reference) == normalize_latex(latex)
            similarity = token_similarity(reference, latex)
            structure_exact = (
                structural_signature(reference) == structural_signature(latex)
            )
    return {
        "id": case["id"],
        "status": status,
        "strict_valid": valid,
        "normalized_exact": exact,
        "token_similarity": similarity,
        "structural_exact": structure_exact,
        "invalid_reason": invalid_reason,
        "recognizer": prediction["recognizer"],
        "model_revision": prediction["model_revision"],
        "execution": prediction["execution"],
        "elapsed_ms": prediction["elapsed_ms"],
    }


def _prediction_map(document: object) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Unsupported prediction document")
    values = document.get("predictions")
    if not isinstance(values, list):
        raise ValueError("Predictions must be a list")
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("Each prediction must be an object")
        case_id = value.get("case_id")
        status = value.get("status")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Each prediction needs a case_id")
        if case_id in result:
            raise ValueError(f"Duplicate prediction: {case_id}")
        if status not in {"ok", "unreadable", "error"}:
            raise ValueError(f"Invalid status for {case_id}")
        latex = value.get("latex")
        if status == "ok" and (not isinstance(latex, str) or not latex.strip()):
            raise ValueError(f"Successful prediction {case_id} needs LaTeX")
        if status != "ok" and latex is not None:
            raise ValueError(f"Non-success prediction {case_id} cannot contain LaTeX")
        for field in ("recognizer", "model_revision", "execution"):
            if not isinstance(value.get(field), str) or not value[field].strip():
                raise ValueError(f"Prediction {case_id} needs {field}")
        if value["execution"] not in {"local", "remote"}:
            raise ValueError(f"Prediction {case_id} has invalid execution mode")
        elapsed = value.get("elapsed_ms")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise ValueError(f"Prediction {case_id} needs non-negative elapsed_ms")
        result[case_id] = value
    return result


def _summarize(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    total = len(rows)
    ok = sum(row["status"] == "ok" for row in rows)
    valid = sum(row["strict_valid"] for row in rows)
    return {
        "total": total,
        "successful": ok,
        "coverage": round(ok / max(total, 1), 6),
        "strict_valid_rate": round(valid / max(ok, 1), 6),
        "normalized_exact_rate": round(
            sum(row["normalized_exact"] for row in rows) / max(total, 1), 6
        ),
        "mean_token_similarity": round(
            sum(row["token_similarity"] for row in rows) / max(total, 1), 6
        ),
        "structural_exact_rate": round(
            sum(row["structural_exact"] for row in rows) / max(total, 1), 6
        ),
        "mean_elapsed_ms": round(
            sum(float(row["elapsed_ms"]) for row in rows) / max(total, 1), 3
        ),
    }


def _levenshtein(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_token in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_token in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_token != right_token),
                )
            )
        previous = current
    return previous[-1]


if __name__ == "__main__":
    raise SystemExit(main())
