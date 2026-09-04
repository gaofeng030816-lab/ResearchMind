"""Bounded GET-only client for Zotero's loopback Local API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re
import socket
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from researchmind.integration.zotero.errors import (
    ZoteroApiDisabledError,
    ZoteroIdentityChangedError,
    ZoteroItemNotFoundError,
    ZoteroProtocolError,
    ZoteroUnavailableError,
)
from researchmind.models.zotero import (
    ZoteroAttachment,
    ZoteroConnection,
    ZoteroDownloadedFile,
    ZoteroItem,
)


LOCAL_API_BASE_URL = "http://127.0.0.1:23119/api/"
API_VERSION = 3
MAX_ITEMS = 50
MAX_METADATA_BYTES = 5 * 1024 * 1024
_KEY_PATTERN = re.compile(r"^[A-Z0-9]{8}$")
_NON_BIBLIOGRAPHIC_TYPES = {"attachment", "note", "annotation"}


@dataclass(frozen=True)
class ZoteroHttpResponse:
    """Small transport response detached from urllib vendor objects."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class ZoteroTransport(Protocol):
    """GET-only transport seam used by routine fake tests."""

    def get(
        self,
        relative_url: str,
        *,
        headers: Mapping[str, str],
        max_bytes: int,
    ) -> ZoteroHttpResponse:
        ...


class UrllibZoteroTransport:
    """Standard-library loopback transport with proxies disabled."""

    def __init__(self, *, timeout_seconds: float = 2.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(ProxyHandler({}), _RejectRedirects())

    def get(
        self,
        relative_url: str,
        *,
        headers: Mapping[str, str],
        max_bytes: int,
    ) -> ZoteroHttpResponse:
        parsed = urlsplit(relative_url)
        decoded_path = unquote(parsed.path)
        if (
            parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or decoded_path.startswith("/")
            or "\\" in decoded_path
            or any(part in {".", ".."} for part in decoded_path.split("/"))
            or any(ord(character) < 32 for character in relative_url)
        ):
            raise ZoteroProtocolError(
                "Zotero request path escaped the fixed Local API boundary."
            )
        if max_bytes <= 0:
            raise ZoteroProtocolError("Zotero response size limit must be positive.")
        request = Request(
            LOCAL_API_BASE_URL + relative_url,
            headers=dict(headers),
            method="GET",
        )
        try:
            with self._opener.open(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = _bounded_read(response, max_bytes)
                return ZoteroHttpResponse(
                    status=int(response.status),
                    headers=dict(response.headers.items()),
                    body=body,
                )
        except HTTPError as exc:
            with exc:
                body = _bounded_read(exc, max_bytes)
                return ZoteroHttpResponse(
                    status=int(exc.code),
                    headers=dict(exc.headers.items()),
                    body=body,
                )
        except (TimeoutError, socket.timeout, URLError, OSError) as exc:
            raise ZoteroUnavailableError(
                "Zotero Local API is unavailable on this computer."
            ) from exc


class _RejectRedirects(HTTPRedirectHandler):
    """Never follow an attachment or metadata redirect outside our endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise ZoteroProtocolError(
            "Zotero HTTP redirects are not allowed by the Local API boundary."
        )


class ZoteroLocalApi:
    """Map Zotero API v3 JSON to bounded ResearchMind models."""

    def __init__(
        self,
        *,
        transport: ZoteroTransport | None = None,
    ) -> None:
        self.transport = transport or UrllibZoteroTransport()

    def probe(self) -> ZoteroConnection:
        response = self._get("", expected_server_id=None)
        server_id = _required_header(response.headers, "Zotero-Server-ID")
        api_version_text = _required_header(
            response.headers,
            "Zotero-API-Version",
        )
        try:
            api_version = int(api_version_text)
        except ValueError as exc:
            raise ZoteroProtocolError(
                "Zotero returned an invalid API version."
            ) from exc
        if api_version != API_VERSION:
            raise ZoteroProtocolError(
                "ResearchMind requires Zotero Local API version 3."
            )
        return ZoteroConnection(
            server_id=_bounded_text(
                server_id,
                field_name="Zotero-Server-ID",
                max_length=128,
            ),
            api_version=api_version,
        )

    def list_recent_items(
        self,
        connection: ZoteroConnection,
        *,
        query: str = "",
        limit: int = 20,
    ) -> tuple[ZoteroItem, ...]:
        _validate_connection(connection)
        if limit < 1 or limit > MAX_ITEMS:
            raise ZoteroProtocolError(
                "Zotero browse limit must be between 1 and 50."
            )
        normalized_query = " ".join(query.split())
        if len(normalized_query) > 200:
            raise ZoteroProtocolError(
                "Zotero search text exceeds the 200-character limit."
            )
        parameters: dict[str, object] = {
            "direction": "desc",
            "format": "json",
            "include": "data",
            "limit": limit,
            "sort": "dateModified",
        }
        if normalized_query:
            parameters["q"] = normalized_query
        response = self._get(
            "users/0/items/top?" + urlencode(parameters),
            expected_server_id=connection.server_id,
        )
        payload = _json_array(response.body)
        if len(payload) > limit:
            raise ZoteroProtocolError(
                "Zotero returned more items than the requested limit."
            )
        items = []
        for raw_item in payload:
            item = _map_item(raw_item, connection.server_id)
            if item.item_type not in _NON_BIBLIOGRAPHIC_TYPES:
                items.append(item)
        return tuple(items)

    def list_pdf_attachments(
        self,
        connection: ZoteroConnection,
        item: ZoteroItem,
    ) -> tuple[ZoteroAttachment, ...]:
        _validate_item_for_connection(item, connection)
        prefix = _library_prefix(item.library_type, item.library_id)
        response = self._get(
            f"{prefix}/items/{item.item_key}/children"
            "?format=json&include=data",
            expected_server_id=connection.server_id,
        )
        payload = _json_array(response.body)
        attachments = []
        for raw_item in payload:
            attachment = _map_pdf_attachment(raw_item, item)
            if attachment is not None:
                attachments.append(attachment)
        return tuple(attachments)

    def download_pdf_attachment(
        self,
        connection: ZoteroConnection,
        attachment: ZoteroAttachment,
        *,
        max_size_bytes: int,
    ) -> ZoteroDownloadedFile:
        """Byte-response prototype; official Local API file redirects stay blocked.

        The production UI disables this path pending a local-file-read gate.
        A fake HTTP 200 PDF does not establish real Zotero compatibility.
        """

        _validate_connection(connection)
        _validate_item_key(attachment.item_key)
        if max_size_bytes <= 0:
            raise ZoteroProtocolError(
                "PDF download size limit must be positive."
            )
        response = self._get(
            f"users/0/items/{attachment.item_key}/file",
            expected_server_id=connection.server_id,
            max_bytes=max_size_bytes,
        )
        content_type = _optional_header(
            response.headers,
            "Content-Type",
        )
        if (
            content_type is None
            or content_type.split(";", 1)[0].strip().lower()
            != "application/pdf"
            or not response.body.startswith(b"%PDF-")
        ):
            raise ZoteroProtocolError(
                "The selected Zotero attachment is not a valid PDF response."
            )
        return ZoteroDownloadedFile(
            filename=_safe_pdf_filename(
                attachment.filename,
                attachment.item_key,
            ),
            content=response.body,
        )

    def _get(
        self,
        relative_url: str,
        *,
        expected_server_id: str | None,
        max_bytes: int = MAX_METADATA_BYTES,
    ) -> ZoteroHttpResponse:
        headers = {
            "Accept": "application/json",
            "User-Agent": "ResearchMind/2.0.0rc1",
            "Zotero-Allowed-Request": "1",
            "Zotero-API-Version": str(API_VERSION),
        }
        if expected_server_id is not None:
            headers["Zotero-Server-ID"] = expected_server_id
        response = self.transport.get(
            relative_url,
            headers=headers,
            max_bytes=max_bytes,
        )
        if len(response.body) > max_bytes:
            raise ZoteroProtocolError(
                "Zotero response exceeds the configured size limit."
            )
        if response.status == 403:
            raise ZoteroApiDisabledError(
                "Zotero Local API is disabled. Enable it in Zotero settings."
            )
        if response.status == 412:
            raise ZoteroIdentityChangedError(
                "ResearchMind reached a different Zotero database."
            )
        if response.status == 404:
            raise ZoteroItemNotFoundError(
                "The selected Zotero item or attachment is unavailable."
            )
        if 300 <= response.status < 400:
            raise ZoteroProtocolError(
                "Zotero file redirects require an approved local-file-read "
                "boundary. Upload the PDF manually and link its source instead."
            )
        if response.status != 200:
            raise ZoteroProtocolError(
                f"Zotero Local API returned HTTP {response.status}."
            )
        if expected_server_id is not None:
            actual_server_id = _required_header(
                response.headers,
                "Zotero-Server-ID",
            )
            if actual_server_id != expected_server_id:
                raise ZoteroIdentityChangedError(
                    "ResearchMind reached a different Zotero database."
                )
            if _required_header(
                response.headers,
                "Zotero-API-Version",
            ) != str(API_VERSION):
                raise ZoteroProtocolError(
                    "ResearchMind requires Zotero Local API version 3."
                )
        return response


def _bounded_read(stream: object, max_bytes: int) -> bytes:
    read = getattr(stream, "read")
    body = read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ZoteroProtocolError(
            "Zotero response exceeds the configured size limit."
        )
    return body


def _json_array(body: bytes) -> list[object]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ZoteroProtocolError(
            "Zotero returned malformed JSON."
        ) from exc
    if not isinstance(payload, list):
        raise ZoteroProtocolError(
            "Zotero returned an unexpected JSON shape."
        )
    return payload


def _map_item(raw: object, server_id: str) -> ZoteroItem:
    envelope = _object(raw, "item")
    data = _object(envelope.get("data"), "item data")
    library = _object(envelope.get("library"), "item library")
    item_key = _matching_key(envelope, data)
    item_version = _matching_version(envelope, data)
    library_type = _bounded_text(
        library.get("type"),
        field_name="library type",
        max_length=20,
    )
    if library_type not in {"user", "group"}:
        raise ZoteroProtocolError("Zotero returned an unsupported library type.")
    library_id = _bounded_text(
        library.get("id"),
        field_name="library id",
        max_length=40,
    )
    creators = _map_creators(data.get("creators"))
    return ZoteroItem(
        server_id=server_id,
        library_type=library_type,
        library_id=library_id,
        item_key=item_key,
        item_version=item_version,
        item_type=_bounded_text(
            data.get("itemType"),
            field_name="item type",
            max_length=80,
        ),
        title=_optional_bounded_text(data.get("title"), 500)
        or "Untitled Zotero item",
        creators=creators,
        publication_title=_optional_bounded_text(
            data.get("publicationTitle"),
            500,
        ),
        published_date=_optional_bounded_text(data.get("date"), 100),
        doi=_optional_bounded_text(data.get("DOI"), 300),
        url=_optional_bounded_text(data.get("url"), 2_048),
    )


def _map_pdf_attachment(
    raw: object,
    parent: ZoteroItem,
) -> ZoteroAttachment | None:
    envelope = _object(raw, "attachment")
    data = _object(envelope.get("data"), "attachment data")
    if data.get("itemType") != "attachment":
        return None
    if str(data.get("contentType", "")).lower() != "application/pdf":
        return None
    if data.get("parentItem") != parent.item_key:
        raise ZoteroProtocolError(
            "Zotero attachment parent identity is inconsistent."
        )
    library = _object(envelope.get("library"), "attachment library")
    if (
        str(library.get("type")) != parent.library_type
        or str(library.get("id")) != parent.library_id
    ):
        raise ZoteroProtocolError(
            "Zotero attachment library identity is inconsistent."
        )
    key = _matching_key(envelope, data)
    return ZoteroAttachment(
        item_key=key,
        item_version=_matching_version(envelope, data),
        parent_item_key=parent.item_key,
        title=_optional_bounded_text(data.get("title"), 500) or "PDF",
        filename=_safe_pdf_filename(
            _optional_bounded_text(data.get("filename"), 500),
            key,
        ),
        content_type="application/pdf",
        link_mode=_optional_bounded_text(data.get("linkMode"), 80)
        or "unknown",
    )


def _map_creators(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) > 20:
        raise ZoteroProtocolError("Zotero creators are malformed or excessive.")
    creators = []
    for raw_creator in raw:
        creator = _object(raw_creator, "creator")
        name = _optional_bounded_text(creator.get("name"), 200)
        if name is None:
            first = _optional_bounded_text(creator.get("firstName"), 100)
            last = _optional_bounded_text(creator.get("lastName"), 100)
            name = " ".join(part for part in (first, last) if part)
        if name:
            creators.append(name)
    return tuple(creators)


def _matching_key(
    envelope: Mapping[str, object],
    data: Mapping[str, object],
) -> str:
    envelope_key = str(envelope.get("key", ""))
    data_key = str(data.get("key", ""))
    if envelope_key != data_key:
        raise ZoteroProtocolError("Zotero item keys are inconsistent.")
    _validate_item_key(envelope_key)
    return envelope_key


def _matching_version(
    envelope: Mapping[str, object],
    data: Mapping[str, object],
) -> int:
    envelope_version = envelope.get("version")
    data_version = data.get("version")
    if (
        not isinstance(envelope_version, int)
        or isinstance(envelope_version, bool)
        or envelope_version < 0
        or data_version != envelope_version
    ):
        raise ZoteroProtocolError("Zotero item versions are inconsistent.")
    return envelope_version


def _validate_item_for_connection(
    item: ZoteroItem,
    connection: ZoteroConnection,
) -> None:
    _validate_connection(connection)
    if item.server_id != connection.server_id:
        raise ZoteroIdentityChangedError(
            "The selected Zotero item belongs to a different database."
        )
    _validate_item_key(item.item_key)


def _validate_connection(connection: ZoteroConnection) -> None:
    if connection.api_version != API_VERSION or not connection.server_id:
        raise ZoteroProtocolError(
            "Zotero connection identity is invalid or unsupported."
        )


def _library_prefix(library_type: str, library_id: str) -> str:
    if library_type == "user":
        return "users/0"
    if library_type == "group":
        if not library_id.isdigit():
            raise ZoteroProtocolError("Zotero group library id is invalid.")
        return f"groups/{library_id}"
    raise ZoteroProtocolError("Zotero library type is unsupported.")


def _validate_item_key(value: str) -> None:
    if _KEY_PATTERN.fullmatch(value) is None:
        raise ZoteroProtocolError("Zotero item key is invalid.")


def _safe_pdf_filename(value: str | None, item_key: str) -> str:
    raw = (value or "").strip().replace("\\", "/")
    name = PurePosixPath(raw).name if raw else f"{item_key}.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name[:240]


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ZoteroProtocolError(f"Zotero {label} is malformed.")
    return value


def _bounded_text(
    value: object,
    *,
    field_name: str,
    max_length: int,
) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or len(text) > max_length:
        raise ZoteroProtocolError(f"Zotero {field_name} is invalid.")
    return text


def _optional_bounded_text(
    value: object,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        raise ZoteroProtocolError(
            "Zotero metadata exceeds the accepted field limit."
        )
    return text


def _required_header(
    headers: Mapping[str, str],
    name: str,
) -> str:
    value = _optional_header(headers, name)
    if value is None:
        raise ZoteroProtocolError(
            f"Zotero response is missing {name}."
        )
    return value


def _optional_header(
    headers: Mapping[str, str],
    name: str,
) -> str | None:
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            normalized = str(value).strip()
            return normalized or None
    return None
