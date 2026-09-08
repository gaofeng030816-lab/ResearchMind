"""Pure, separately testable input boundary for the adopted PDF.js viewer."""

from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256

MAX_VIEWER_PDF_BYTES = 10 * 1024 * 1024
MAX_SAFE_SEQUENCE = 2**53 - 1


@dataclass(frozen=True)
class PageTurn:
    """A validated one-page wheel request from the browser viewer."""

    sequence: int
    target_page: int


@dataclass(frozen=True)
class ShortcutToggle:
    """A validated request to toggle the ResearchMind AI panel."""

    sequence: int


def make_payload(
    pdf_bytes: bytes,
    *,
    page: int,
    page_count: int,
    scale: float,
    instance: str,
    loaded_revision: object = "",
) -> dict[str, object]:
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("A digital PDF byte stream is required")
    if not 0 < len(pdf_bytes) <= MAX_VIEWER_PDF_BYTES:
        raise ValueError("Browser text-layer PDF exceeds the 10 MiB limit")
    if type(page_count) is not int or page_count < 1:
        raise ValueError("Page count must be a positive integer")
    if type(page) is not int or not 1 <= page <= page_count:
        raise ValueError("Page must be within the trusted document bounds")
    if type(scale) not in (int, float) or not 0.5 <= float(scale) <= 2.5:
        raise ValueError("Scale must be between 0.5 and 2.5")
    if not isinstance(instance, str) or not 0 < len(instance) <= 128:
        raise ValueError("Component instance is required")
    revision = "sha256:" + sha256(pdf_bytes).hexdigest()
    safe_loaded_revision = (
        loaded_revision
        if isinstance(loaded_revision, str) and len(loaded_revision) <= 96
        else ""
    )
    encoded_pdf = (
        ""
        if safe_loaded_revision == revision
        else b64encode(pdf_bytes).decode("ascii")
    )
    return {"pdf_base64": encoded_pdf,
            "revision": revision, "loaded_revision": safe_loaded_revision,
            "page": page, "page_count": page_count, "scale": float(scale),
            "instance": instance, "max_selection_chars": 8000}


def validate_page_turn(
    event: object,
    *,
    revision: str,
    instance: str,
    current_page: int,
    page_count: int,
    last_sequence: int,
) -> PageTurn:
    """Validate an untrusted wheel event against trusted server-side state."""

    keys = {
        "version", "revision", "instance", "page", "sequence", "delta", "source",
    }
    if not isinstance(event, dict) or set(event) != keys:
        raise ValueError("Invalid page-turn envelope")
    if type(event["version"]) is not int or event["version"] != 1:
        raise ValueError("Unsupported page-turn version")
    if event["revision"] != revision:
        raise ValueError("Stale PDF revision")
    if event["instance"] != instance:
        raise ValueError("Stale component instance")
    if type(current_page) is not int or type(page_count) is not int:
        raise ValueError("Trusted page state is invalid")
    if not 1 <= current_page <= page_count:
        raise ValueError("Trusted page state is out of bounds")
    if type(event["page"]) is not int or event["page"] != current_page:
        raise ValueError("Stale PDF page")
    sequence = event["sequence"]
    if (
        type(last_sequence) is not int
        or last_sequence < 0
        or type(sequence) is not int
        or not last_sequence < sequence <= MAX_SAFE_SEQUENCE
    ):
        raise ValueError("Stale or invalid page-turn sequence")
    delta = event["delta"]
    if type(delta) is not int or delta not in (-1, 1):
        raise ValueError("Page turn must move exactly one page")
    if event["source"] != "wheel":
        raise ValueError("Unsupported page-turn source")
    target_page = current_page + delta
    if not 1 <= target_page <= page_count:
        raise ValueError("Page turn exceeds document bounds")
    return PageTurn(sequence=sequence, target_page=target_page)


def validate_shortcut_toggle(
    event: object,
    *,
    last_sequence: int,
) -> ShortcutToggle:
    """Validate ResearchMind's fixed, non-configurable keyboard shortcut."""

    keys = {"version", "sequence", "shortcut", "source"}
    if not isinstance(event, dict) or set(event) != keys:
        raise ValueError("Invalid shortcut envelope")
    if type(event["version"]) is not int or event["version"] != 1:
        raise ValueError("Unsupported shortcut version")
    sequence = event["sequence"]
    if (
        type(last_sequence) is not int
        or last_sequence < 0
        or type(sequence) is not int
        or not last_sequence < sequence <= MAX_SAFE_SEQUENCE
    ):
        raise ValueError("Stale or invalid shortcut sequence")
    if event["shortcut"] != "Ctrl+Shift+A" or event["source"] != "keyboard":
        raise ValueError("Unsupported shortcut")
    return ShortcutToggle(sequence=sequence)
