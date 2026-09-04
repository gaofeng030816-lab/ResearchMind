"""Project exceptions for the optional read-only Zotero boundary."""


class ZoteroError(Exception):
    """Base class for user-visible Zotero integration failures."""


class ZoteroUnavailableError(ZoteroError):
    """Raised when the loopback Zotero service cannot be reached."""


class ZoteroApiDisabledError(ZoteroError):
    """Raised when Zotero is running but its Local API is disabled."""


class ZoteroIdentityChangedError(ZoteroError):
    """Raised when cached data belongs to a different Zotero database."""


class ZoteroProtocolError(ZoteroError):
    """Raised for unsupported, malformed, or unsafe Zotero responses."""


class ZoteroItemNotFoundError(ZoteroError):
    """Raised when an explicitly requested Zotero item is unavailable."""
