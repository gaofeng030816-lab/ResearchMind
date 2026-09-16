"""Turn the G5 reference PDF into hash-locked, formula-only PNG crops."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re

import pymupdf
from PIL import Image, ImageOps


DEFAULT_SOURCE = Path(__file__).with_name("corpus_source.json")
DEFAULT_OUTPUT = Path(__file__).with_name("crops")
DEFAULT_MANIFEST = Path(__file__).with_name("corpus.json")
_SAFE_ID = re.compile(r"[a-z0-9_]{1,64}\Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    cases = source.get("cases")
    if source.get("schema_version") != 1 or not isinstance(cases, list):
        raise ValueError("Unsupported G5 source manifest")
    if len(cases) != 20:
        raise ValueError("The G5 adoption corpus must contain exactly 20 cases")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, object]] = []
    with pymupdf.open(args.pdf) as document:
        if document.page_count != len(cases):
            raise ValueError(
                f"Expected {len(cases)} formula pages, got {document.page_count}"
            )
        for page_index, case in enumerate(cases):
            case_id = _case_id(case)
            payload, width, height = _render_tight_crop(document[page_index])
            crop_name = f"{page_index + 1:02d}_{case_id}.png"
            crop_path = args.output_dir / crop_name
            crop_path.write_bytes(payload)
            rendered.append(
                {
                    **case,
                    "page_number": page_index + 1,
                    "crop_file": f"crops/{crop_name}",
                    "crop_sha256": hashlib.sha256(payload).hexdigest().upper(),
                    "crop_width_px": width,
                    "crop_height_px": height,
                }
            )

    manifest = {
        "schema_version": 1,
        "purpose": "license-free synthetic formula-recognizer quality gate",
        "source_tex_sha256": _sha256(Path(__file__).with_name("corpus.tex")),
        "source_pdf_sha256": _sha256(args.pdf),
        "render": {
            "engine": "Tectonic LaTeX to PDF, PyMuPDF to grayscale PNG",
            "zoom": 3.0,
            "ink_threshold": 245,
            "padding_px": 24,
        },
        "cases": rendered,
    }
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rendered)} crops and {args.manifest}")
    return 0


def _case_id(case: object) -> str:
    if not isinstance(case, dict):
        raise ValueError("Each corpus case must be an object")
    value = case.get("id")
    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ValueError("Each corpus case needs a safe lowercase id")
    categories = case.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ValueError(f"Corpus case {value} needs categories")
    reference = case.get("reference_latex")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError(f"Corpus case {value} needs reference LaTeX")
    return value


def _render_tight_crop(page: pymupdf.Page) -> tuple[bytes, int, int]:
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(3.0, 3.0),
        colorspace=pymupdf.csGRAY,
        alpha=False,
    )
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    ink = ImageOps.invert(image).point(lambda value: 255 if value > 10 else 0)
    bbox = ink.getbbox()
    if bbox is None:
        raise ValueError(f"Formula page {page.number + 1} rendered blank")
    left, top, right, bottom = bbox
    padding = 24
    bbox = (
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    )
    crop = image.crop(bbox).convert("RGB")
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), crop.width, crop.height


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


if __name__ == "__main__":
    raise SystemExit(main())

