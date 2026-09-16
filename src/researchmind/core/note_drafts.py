"""Pure validation rules for durable note drafts and evidence snapshots."""

from __future__ import annotations

import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import re

from researchmind.models import EvidenceSnapshot, NoteDraft


MAX_DRAFT_TITLE_CHARS = 200
MAX_DRAFT_MARKDOWN_CHARS = 250_000
MAX_EVIDENCE_CONTENT_CHARS = 100_000
MAX_EVIDENCE_SOURCE_LABEL_CHARS = 500
MAX_EVIDENCE_LOCATOR_BYTES = 8_192
MAX_EVIDENCE_LOCATOR_DEPTH = 6
MAX_EVIDENCE_LOCATOR_ITEMS = 64
MAX_EVIDENCE_ITEMS_PER_DRAFT = 200
MAX_INTERNAL_ID_CHARS = 128
MAX_SELECTION_ID_CHARS = 128

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DRAFT_STATUSES = {"active", "archived"}
_EVIDENCE_KINDS = {
    "source_text",
    "translation",
    "latex",
    "question",
    "answer",
    "code",
}
_EVIDENCE_ORIGINS = {
    "browser_selection",
    "translation_provider",
    "latex_conversion",
    "user_question",
    "assistant_response",
    "code_selection",
    "user_entry",
}
_PATH_KEYS = {"path", "relative_path", "file_path"}


def validate_note_draft(draft: NoteDraft) -> None:
    """Reject a draft that cannot be stored or safely presented."""

    _validate_internal_id(draft.id, label="Draft ID")
    _validate_optional_internal_id(draft.record_id, label="Record ID")
    _validate_optional_internal_id(draft.asset_id, label="Asset ID")
    if draft.asset_id is not None and draft.record_id is None:
        raise ValueError("A draft asset requires its library record identity.")
    _validate_text(
        draft.title,
        label="Draft title",
        maximum=MAX_DRAFT_TITLE_CHARS,
        allow_blank=False,
    )
    _validate_text(
        draft.body_markdown,
        label="Draft Markdown",
        maximum=MAX_DRAFT_MARKDOWN_CHARS,
        allow_blank=True,
    )
    if draft.status not in _DRAFT_STATUSES:
        raise ValueError("Draft status is invalid.")
    _validate_positive_integer(draft.revision, label="Draft revision")
    _validate_timestamp(draft.created_at, label="Draft created time")
    _validate_timestamp(draft.updated_at, label="Draft updated time")
    if draft.updated_at < draft.created_at:
        raise ValueError("Draft updated time precedes its creation time.")


def validate_evidence_snapshot(snapshot: EvidenceSnapshot) -> None:
    """Reject evidence that is unbounded, untraceable, or malformed."""

    _validate_internal_id(snapshot.id, label="Evidence ID")
    _validate_internal_id(snapshot.draft_id, label="Draft ID")
    _validate_optional_internal_id(
        snapshot.source_record_id,
        label="Source record ID",
    )
    _validate_optional_internal_id(
        snapshot.source_asset_id,
        label="Source asset ID",
    )
    if (
        snapshot.source_asset_id is not None
        and snapshot.source_record_id is None
    ):
        raise ValueError(
            "An evidence asset requires its library record identity."
        )
    if snapshot.source_asset_id is not None and (
        snapshot.source_revision is None
        or snapshot.source_sha256 is None
    ):
        raise ValueError(
            "Managed evidence requires its source revision and SHA-256."
        )
    if snapshot.kind not in _EVIDENCE_KINDS:
        raise ValueError("Evidence kind is invalid.")
    if snapshot.origin not in _EVIDENCE_ORIGINS:
        raise ValueError("Evidence origin is invalid.")
    _validate_text(
        snapshot.content,
        label="Evidence content",
        maximum=MAX_EVIDENCE_CONTENT_CHARS,
        allow_blank=False,
    )
    _validate_text(
        snapshot.source_label,
        label="Evidence source label",
        maximum=MAX_EVIDENCE_SOURCE_LABEL_CHARS,
        allow_blank=False,
    )
    _reject_absolute_private_path(snapshot.source_label)
    if not isinstance(snapshot.included, bool):
        raise ValueError("Evidence included state must be a boolean.")
    _validate_nonnegative_integer(
        snapshot.sort_order,
        label="Evidence sort order",
    )
    _validate_timestamp(snapshot.created_at, label="Evidence created time")
    if snapshot.source_revision is not None:
        _validate_positive_integer(
            snapshot.source_revision,
            label="Evidence source revision",
        )
    if (
        snapshot.source_sha256 is not None
        and _SHA256_PATTERN.fullmatch(snapshot.source_sha256) is None
    ):
        raise ValueError("Evidence source SHA-256 is invalid.")
    if snapshot.selection_id is not None:
        _validate_text(
            snapshot.selection_id,
            label="Evidence selection ID",
            maximum=MAX_SELECTION_ID_CHARS,
            allow_blank=False,
        )
    serialize_evidence_locator(snapshot.locator)


def serialize_evidence_locator(locator: dict[str, object]) -> str:
    """Return one canonical bounded JSON locator after structural validation."""

    if not isinstance(locator, dict):
        raise ValueError("Evidence locator must be an object.")
    _validate_locator_value(locator, depth=0)
    try:
        payload = json.dumps(
            locator,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Evidence locator is not valid JSON data.") from exc
    if len(payload.encode("utf-8")) > MAX_EVIDENCE_LOCATOR_BYTES:
        raise ValueError("Evidence locator exceeds the size limit.")
    return payload


def _validate_locator_value(value: object, *, depth: int) -> None:
    if depth > MAX_EVIDENCE_LOCATOR_DEPTH:
        raise ValueError("Evidence locator is nested too deeply.")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Evidence locator contains a non-finite number.")
        return
    if isinstance(value, list):
        if len(value) > MAX_EVIDENCE_LOCATOR_ITEMS:
            raise ValueError("Evidence locator contains too many items.")
        for item in value:
            _validate_locator_value(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_EVIDENCE_LOCATOR_ITEMS:
            raise ValueError("Evidence locator contains too many fields.")
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 64:
                raise ValueError("Evidence locator contains an invalid field name.")
            if key.casefold() in _PATH_KEYS and isinstance(item, str):
                _validate_relative_locator_path(item)
            _validate_locator_value(item, depth=depth + 1)
        return
    raise ValueError("Evidence locator contains an unsupported value.")


def _validate_relative_locator_path(value: str) -> None:
    if "\x00" in value:
        raise ValueError("Evidence locator path contains a null byte.")
    windows = PureWindowsPath(value)
    posix = PurePosixPath(value)
    if windows.is_absolute() or posix.is_absolute() or windows.drive:
        raise ValueError("Evidence locator paths must be relative.")
    if ".." in windows.parts or ".." in posix.parts:
        raise ValueError("Evidence locator paths must not traverse parents.")


def _reject_absolute_private_path(value: str) -> None:
    normalized = value.strip()
    if (
        re.search(r"(?i)(?:^|\s)[a-z]:[\\/]", normalized)
        or normalized.startswith("\\\\")
        or normalized.startswith("//")
        or normalized.startswith("/")
    ):
        raise ValueError(
            "Evidence source labels must not contain absolute private paths."
        )


def _validate_internal_id(value: str, *, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) > MAX_INTERNAL_ID_CHARS
        or _ID_PATTERN.fullmatch(value) is None
    ):
        raise ValueError(f"{label} is invalid.")


def _validate_optional_internal_id(
    value: str | None,
    *,
    label: str,
) -> None:
    if value is not None:
        _validate_internal_id(value, label=label)


def _validate_text(
    value: str,
    *,
    label: str,
    maximum: int,
    allow_blank: bool,
) -> None:
    if not isinstance(value, str) or "\x00" in value:
        raise ValueError(f"{label} is invalid.")
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds the size limit.")
    if not allow_blank and not value.strip():
        raise ValueError(f"{label} must not be blank.")


def _validate_positive_integer(value: int, *, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer.")


def _validate_nonnegative_integer(value: int, *, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer.")


def _validate_timestamp(value: object, *, label: str) -> None:
    offset = getattr(value, "utcoffset", lambda: None)()
    if offset is None:
        raise ValueError(f"{label} must include a timezone.")
