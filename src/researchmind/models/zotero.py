"""Vendor-free values for the optional V3-G2 Zotero connection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


ZoteroLibraryType = Literal["user", "group"]


@dataclass(frozen=True)
class ZoteroConnection:
    """Identity of one probed Zotero Local API database."""

    server_id: str
    api_version: int


@dataclass(frozen=True)
class ZoteroItem:
    """Bounded bibliographic snapshot mapped from vendor JSON."""

    server_id: str
    library_type: ZoteroLibraryType
    library_id: str
    item_key: str
    item_version: int
    item_type: str
    title: str
    creators: tuple[str, ...]
    publication_title: str | None = None
    published_date: str | None = None
    doi: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class ZoteroAttachment:
    """One PDF attachment reference owned by a Zotero item."""

    item_key: str
    item_version: int
    parent_item_key: str
    title: str
    filename: str
    content_type: str
    link_mode: str


@dataclass(frozen=True)
class ZoteroDownloadedFile:
    """Bounded PDF bytes returned by the loopback Local API."""

    filename: str
    content: bytes = field(repr=False)


@dataclass(frozen=True)
class ZoteroBrowseResult:
    """One explicit, session-only Local API browse result."""

    connection: ZoteroConnection
    items: tuple[ZoteroItem, ...]


@dataclass(frozen=True)
class ZoteroItemDetails:
    """Selected item and its explicitly fetched PDF attachments."""

    connection: ZoteroConnection
    item: ZoteroItem
    attachments: tuple[ZoteroAttachment, ...]


@dataclass(frozen=True)
class ZoteroSourceLink:
    """Durable ResearchMind record-to-Zotero source snapshot."""

    id: str
    record_id: str
    server_id: str
    library_type: ZoteroLibraryType
    library_id: str
    item_key: str
    item_version: int
    item_type: str
    title: str
    creators: tuple[str, ...]
    publication_title: str | None
    published_date: str | None
    doi: str | None
    url: str | None
    attachment_key: str | None
    attachment_version: int | None
    attachment_filename: str | None
    linked_at: datetime
    observed_at: datetime
