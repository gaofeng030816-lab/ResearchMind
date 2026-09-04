"""Explicit one-crop live probe for the configured multimodal LLM endpoint."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from openai import DefaultHttpxClient, OpenAI
import pymupdf

from researchmind.config import load_settings

if __package__:
    from .formula_vision import convert_formula_crop, render_formula_crop
else:
    from formula_vision import convert_formula_crop, render_formula_crop


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("X0", "Y0", "X1", "Y1"),
        required=True,
    )
    parser.add_argument(
        "--confirm-external-transfer",
        action="store_true",
        help="Confirm that this exact formula crop may be sent to the provider.",
    )
    args = parser.parse_args()
    if not args.confirm_external_transfer:
        parser.error("--confirm-external-transfer is required for a live request")

    settings = load_settings()
    if not settings.llm_api_key or not settings.llm_model:
        parser.error("LLM_API_KEY and LLM_MODEL must be configured")
    if not args.pdf.is_file():
        parser.error("--pdf must name an existing file")

    with pymupdf.open(args.pdf) as document:
        if args.page < 1 or args.page > document.page_count:
            parser.error("--page is outside the PDF")
        png_bytes = render_formula_crop(
            document[args.page - 1],
            tuple(args.bbox),
        )

    latex = convert_formula_crop(
        completion_create=_build_completion_create(
            api_key=settings.llm_api_key,
            api_key_header=settings.llm_api_key_header,
            base_url=settings.llm_base_url,
        ),
        model=settings.llm_model,
        png_bytes=png_bytes,
    )
    print(
        json.dumps(
            {
                "success": latex is not None,
                "latex": latex,
                "page_number": args.page,
                "bbox": args.bbox,
                "crop_bytes": len(png_bytes),
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


def _build_completion_create(
    *,
    api_key: str,
    api_key_header: str,
    base_url: str,
) -> Callable[..., object]:
    normalized_header = api_key_header.casefold()
    if normalized_header not in {"authorization", "api-key"}:
        raise ValueError("api_key_header must be Authorization or api-key")
    if normalized_header == "authorization":
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=90.0,
            max_retries=0,
        )
    else:
        def add_key(request: Any) -> None:
            request.headers.pop("Authorization", None)
            request.headers[api_key_header] = api_key

        client = OpenAI(
            api_key="custom-header-auth",
            base_url=base_url,
            timeout=90.0,
            max_retries=0,
            http_client=DefaultHttpxClient(
                event_hooks={"request": [add_key]}
            ),
        )
    return client.chat.completions.create


if __name__ == "__main__":
    raise SystemExit(main())
