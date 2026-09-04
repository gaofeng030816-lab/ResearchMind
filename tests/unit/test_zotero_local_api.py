"""Unit coverage for the V3-G2 read-only Zotero Local API boundary."""

from collections.abc import Mapping
from email.message import Message as HeaderMessage
from io import BytesIO
import json
from pathlib import Path
from urllib.request import FileHandler, HTTPHandler
from urllib.response import addinfourl

import pytest

from researchmind.integration.zotero import (
    ZoteroApiDisabledError,
    ZoteroHttpResponse,
    ZoteroIdentityChangedError,
    ZoteroLocalApi,
    ZoteroProtocolError,
    UrllibZoteroTransport,
    ZoteroUnavailableError,
)


class FakeTransport:
    def __init__(
        self,
        responses: list[ZoteroHttpResponse | Exception],
    ) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, Mapping[str, str], int]] = []

    def get(
        self,
        relative_url: str,
        *,
        headers: Mapping[str, str],
        max_bytes: int,
    ) -> ZoteroHttpResponse:
        self.calls.append((relative_url, dict(headers), max_bytes))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(
    body: bytes,
    *,
    status: int = 200,
    server_id: str,
    content_type: str = "application/json",
) -> ZoteroHttpResponse:
    return ZoteroHttpResponse(
        status=status,
        headers={
            "Zotero-API-Version": "3",
            "Zotero-Server-ID": server_id,
            "Content-Type": content_type,
        },
        body=body,
    )


def test_probe_list_items_and_pdf_attachment_mapping() -> None:
    transport = FakeTransport(
        [
            _response(b"{}", server_id="server-A"),
            _response(
                json.dumps([_paper_item()]).encode("utf-8"),
                server_id="server-A",
            ),
            _response(
                json.dumps(
                    [
                        _attachment_item(),
                        {
                            "key": "NOTE1234",
                            "version": 3,
                            "library": {"type": "user", "id": 42},
                            "data": {
                                "key": "NOTE1234",
                                "version": 3,
                                "itemType": "note",
                                "parentItem": "ABCD2345",
                            },
                        },
                    ]
                ).encode("utf-8"),
                server_id="server-A",
            ),
        ]
    )
    client = ZoteroLocalApi(transport=transport)

    connection = client.probe()
    items = client.list_recent_items(connection, query="causal", limit=20)
    attachments = client.list_pdf_attachments(connection, items[0])

    assert connection.server_id == "server-A"
    assert connection.api_version == 3
    assert items[0].library_type == "user"
    assert items[0].library_id == "42"
    assert items[0].item_key == "ABCD2345"
    assert items[0].creators == ("Ada Lovelace", "Research Consortium")
    assert items[0].publication_title == "Journal of Tests"
    assert attachments[0].parent_item_key == items[0].item_key
    assert attachments[0].filename == "paper.pdf"

    assert transport.calls[0][0] == ""
    assert transport.calls[1][0].startswith("users/0/items/top?")
    assert "q=causal" in transport.calls[1][0]
    assert transport.calls[2][0] == (
        "users/0/items/ABCD2345/children?format=json&include=data"
    )
    for _url, headers, _max_bytes in transport.calls[1:]:
        assert headers["Zotero-Server-ID"] == "server-A"
        assert headers["Zotero-API-Version"] == "3"


def test_real_url_protocol_reads_a_locked_synthetic_file(tmp_path: Path) -> None:
    from researchmind.integration.zotero.local_api import _map_item
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\nfixture")
    responses = _copy_responses(source)
    transport = FakeTransport(responses + responses)
    client = ZoteroLocalApi(transport=transport)

    downloaded = client.download_pdf_attachment(
        _connection(),
        _pdf_attachment(),
        item=_map_item(_paper_item(), "server-A"),
        approved_root=str(tmp_path),
        max_size_bytes=1024,
    )

    assert downloaded.filename == "paper.pdf"
    assert downloaded.content.startswith(b"%PDF-")
    assert transport.calls[2][0] == "users/0/items/PDF12345/file/view/url"
    assert transport.calls[2][2] == 8192
    assert len(transport.calls) == 6
    assert downloaded.content == source.read_bytes()


@pytest.mark.parametrize(
    ("response", "error_type", "message"),
    [
        (
            _response(b"{}", status=403, server_id="server-A"),
            ZoteroApiDisabledError,
            "disabled",
        ),
        (
            _response(b"{}", status=412, server_id="server-B"),
            ZoteroIdentityChangedError,
            "different",
        ),
        (
            _response(b"{", server_id="server-A"),
            ZoteroProtocolError,
            "JSON",
        ),
    ],
)
def test_local_api_failures_have_distinct_project_errors(
    response: ZoteroHttpResponse,
    error_type: type[Exception],
    message: str,
) -> None:
    client = ZoteroLocalApi(transport=FakeTransport([response]))

    if response.status == 403:
        action = client.probe
    else:
        action = lambda: client.list_recent_items(_connection())

    with pytest.raises(error_type, match=message):
        action()


def test_probe_requires_server_identity_and_api_v3() -> None:
    missing_identity = ZoteroLocalApi(
        transport=FakeTransport(
            [
                ZoteroHttpResponse(
                    status=200,
                    headers={"Zotero-API-Version": "3"},
                    body=b"{}",
                )
            ]
        )
    )
    wrong_version = ZoteroLocalApi(
        transport=FakeTransport(
            [
                ZoteroHttpResponse(
                    status=200,
                    headers={
                        "Zotero-API-Version": "2",
                        "Zotero-Server-ID": "server-A",
                    },
                    body=b"{}",
                )
            ]
        )
    )

    with pytest.raises(ZoteroProtocolError, match="Server-ID"):
        missing_identity.probe()
    with pytest.raises(ZoteroProtocolError, match="version 3"):
        wrong_version.probe()


def _connection():
    from researchmind.models import ZoteroConnection

    return ZoteroConnection(server_id="server-A", api_version=3)


def test_transport_refuses_redirect_before_leaving_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def fake_http_open(_handler, request):
        urls.append(request.full_url)
        headers = HeaderMessage()
        headers["Location"] = "http://example.invalid/private"
        if len(urls) > 1:
            raise AssertionError("A redirect escaped the Local API boundary.")
        result = addinfourl(BytesIO(b""), headers, request.full_url, 302)
        result.msg = "Found"
        return result

    monkeypatch.setattr(HTTPHandler, "http_open", fake_http_open)
    with pytest.raises(ZoteroProtocolError, match="redirect"):
        UrllibZoteroTransport().get("", headers={}, max_bytes=1024)
    assert urls == ["http://127.0.0.1:23119/api/"]


def test_official_file_redirect_is_blocked_without_local_file_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []

    def fake_http_open(_handler, request):
        urls.append(request.full_url)
        headers = HeaderMessage()
        headers["Location"] = "file:///C:/fixture-only/private.pdf"
        result = addinfourl(BytesIO(b""), headers, request.full_url, 302)
        result.msg = "Found"
        return result

    def forbid_file_read(*_args, **_kwargs):
        raise AssertionError("An unapproved local file was opened.")

    monkeypatch.setattr(HTTPHandler, "http_open", fake_http_open)
    monkeypatch.setattr(FileHandler, "file_open", forbid_file_read)
    client = ZoteroLocalApi(transport=UrllibZoteroTransport())
    with pytest.raises(ZoteroProtocolError, match="local-file-read") as error:
        client._get("users/0/items/PDF12345/file", expected_server_id="server-A")
    assert urls == ["http://127.0.0.1:23119/api/users/0/items/PDF12345/file"]
    assert "private.pdf" not in str(error.value)


@pytest.mark.parametrize(
    "relative_url",
    [
        "https://example.invalid/",
        "//example.invalid/",
        "../outside",
        "users/0/../../outside",
        "%2e%2e/outside",
        "users\\outside",
    ],
)
def test_transport_rejects_unsafe_path_before_io(
    relative_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = UrllibZoteroTransport()

    def forbid_io(*_args, **_kwargs):
        raise AssertionError("Unsafe input reached the HTTP opener.")

    monkeypatch.setattr(transport._opener, "open", forbid_io)
    with pytest.raises(ZoteroProtocolError, match="boundary"):
        transport.get(relative_url, headers={}, max_bytes=1024)


def test_unavailable_and_oversized_responses_remain_project_errors() -> None:
    client = ZoteroLocalApi(
        transport=FakeTransport(
            [ZoteroUnavailableError("Zotero Local API is unavailable.")]
        )
    )
    with pytest.raises(ZoteroUnavailableError, match="unavailable"):
        client.probe()
    oversized = ZoteroLocalApi(
        transport=FakeTransport(
            [_response(b"%PDF-1.7", server_id="server-A")]
        )
    )
    with pytest.raises(ZoteroProtocolError, match="size limit"):
        oversized._get("", expected_server_id="server-A", max_bytes=4)


def _copy_responses(source: Path) -> list[ZoteroHttpResponse]:
    return [
        _response(json.dumps(_paper_item()).encode(), server_id="server-A"),
        _response(json.dumps(_attachment_item()).encode(), server_id="server-A"),
        _response(source.as_uri().encode(), server_id="server-A", content_type="text/plain"),
    ]


@pytest.mark.parametrize("change_after_read", [False, True])
def test_copy_rejects_stale_metadata(tmp_path: Path, change_after_read: bool) -> None:
    from researchmind.integration.zotero.local_api import _map_item
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\nfixture")
    responses = _copy_responses(source) + _copy_responses(source)
    changed = _attachment_item()
    changed["version"] = 8
    changed["data"]["version"] = 8
    responses[4 if change_after_read else 1] = _response(
        json.dumps(changed).encode(), server_id="server-A",
    )
    transport = FakeTransport(responses)
    with pytest.raises(ZoteroProtocolError, match="selection changed"):
        ZoteroLocalApi(transport=transport).download_pdf_attachment(
            _connection(), _pdf_attachment(), item=_map_item(_paper_item(), "server-A"),
            approved_root=str(tmp_path), max_size_bytes=1024,
        )
    assert len(transport.calls) == (5 if change_after_read else 2)


def test_copy_rejects_url_change_after_read(tmp_path: Path) -> None:
    from researchmind.integration.zotero.local_api import _map_item
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\nfixture")
    responses = _copy_responses(source) + _copy_responses(tmp_path / "other.pdf")
    with pytest.raises(ZoteroProtocolError, match="location changed"):
        ZoteroLocalApi(transport=FakeTransport(responses)).download_pdf_attachment(
            _connection(), _pdf_attachment(), item=_map_item(_paper_item(), "server-A"),
            approved_root=str(tmp_path), max_size_bytes=1024,
        )


def _paper_item() -> dict[str, object]:
    return {
        "key": "ABCD2345",
        "version": 12,
        "library": {"type": "user", "id": 42},
        "data": {
            "key": "ABCD2345",
            "version": 12,
            "itemType": "journalArticle",
            "title": "Causal testing",
            "creators": [
                {
                    "creatorType": "author",
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                },
                {
                    "creatorType": "author",
                    "name": "Research Consortium",
                },
            ],
            "date": "2026",
            "DOI": "10.0000/example",
            "url": "https://example.test/paper",
            "publicationTitle": "Journal of Tests",
        },
    }


def _attachment_item() -> dict[str, object]:
    return {
        "key": "PDF12345",
        "version": 7,
        "library": {"type": "user", "id": 42},
        "data": {
            "key": "PDF12345",
            "version": 7,
            "itemType": "attachment",
            "parentItem": "ABCD2345",
            "title": "PDF",
            "filename": "paper.pdf",
            "contentType": "application/pdf",
            "linkMode": "imported_file",
        },
    }


def _pdf_attachment():
    from researchmind.models import ZoteroAttachment

    return ZoteroAttachment(
        item_key="PDF12345",
        item_version=7,
        parent_item_key="ABCD2345",
        title="PDF",
        filename="paper.pdf",
        content_type="application/pdf",
        link_mode="imported_file",
    )
