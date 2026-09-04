"""Project-defined errors for the PDF infrastructure boundary."""


class PdfError(Exception):
    """Base class for PDF failures that callers may safely present to users."""


class PdfValidationError(PdfError):
    """Raised when a PDF path or file fails pre-parse validation."""


class PdfExtractionError(PdfError):
    """Raised when metadata, pages, or text cannot be extracted safely."""


class PdfPageError(PdfError):
    """Raised when a requested page number is outside the document."""


class PdfRenderError(PdfError):
    """Raised when a page cannot be rendered as an image."""
