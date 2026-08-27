"""Public PDF infrastructure API."""

from researchmind.pdf.errors import (
    PdfError,
    PdfExtractionError,
    PdfPageError,
    PdfRenderError,
    PdfValidationError,
)
from researchmind.pdf.reader import (
    DEFAULT_PDF_MAX_SIZE_BYTES,
    MAX_RENDER_ZOOM,
    OpenedDocument,
    extract_page,
    open_pdf,
    render_page_image,
)
from researchmind.pdf.search import TextMatch, search_text

__all__ = [
    "DEFAULT_PDF_MAX_SIZE_BYTES",
    "MAX_RENDER_ZOOM",
    "OpenedDocument",
    "PdfError",
    "PdfExtractionError",
    "PdfPageError",
    "PdfRenderError",
    "PdfValidationError",
    "TextMatch",
    "extract_page",
    "open_pdf",
    "render_page_image",
    "search_text",
]
