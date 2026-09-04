"""Optional V3-G2 read-only Zotero Local API integration."""

from researchmind.integration.zotero.errors import (
    ZoteroApiDisabledError,
    ZoteroError,
    ZoteroIdentityChangedError,
    ZoteroItemNotFoundError,
    ZoteroProtocolError,
    ZoteroUnavailableError,
)
from researchmind.integration.zotero.local_api import (
    API_VERSION,
    LOCAL_API_BASE_URL,
    MAX_ITEMS,
    UrllibZoteroTransport,
    ZoteroHttpResponse,
    ZoteroLocalApi,
    ZoteroTransport,
)

__all__ = [
    "API_VERSION",
    "LOCAL_API_BASE_URL",
    "MAX_ITEMS",
    "UrllibZoteroTransport",
    "ZoteroApiDisabledError",
    "ZoteroError",
    "ZoteroHttpResponse",
    "ZoteroIdentityChangedError",
    "ZoteroItemNotFoundError",
    "ZoteroLocalApi",
    "ZoteroProtocolError",
    "ZoteroTransport",
    "ZoteroUnavailableError",
]
