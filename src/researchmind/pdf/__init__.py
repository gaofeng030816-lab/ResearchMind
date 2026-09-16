"""Public PDF infrastructure API."""

from researchmind.pdf.errors import (
    PdfError,
    PdfExtractionError,
    PdfFormulaError,
    PdfPageError,
    PdfRenderError,
    PdfValidationError,
    PdfViewerError,
)
from researchmind.pdf.formulas import (
    FORMULA_CROP_PADDING_POINTS,
    FORMULA_CROP_ZOOM,
    MAX_FORMULA_CROP_BYTES,
    MAX_FORMULA_CROP_PIXELS,
    detect_formula_regions,
    render_formula_crop,
)
from researchmind.pdf.reader import (
    DEFAULT_PDF_MAX_SIZE_BYTES,
    DEFAULT_PDF_VIEWER_MAX_SIZE_BYTES,
    MAX_RENDER_ZOOM,
    OpenedDocument,
    PdfViewerSource,
    extract_page,
    load_pdf_viewer_source,
    open_pdf,
    render_figure_images,
    render_page_image,
)
from researchmind.pdf.search import TextMatch, search_text

__all__ = [
    "DEFAULT_PDF_MAX_SIZE_BYTES",
    "DEFAULT_PDF_VIEWER_MAX_SIZE_BYTES",
    "MAX_RENDER_ZOOM",
    "OpenedDocument",
    "PdfViewerSource",
    "PdfError",
    "PdfExtractionError",
    "PdfFormulaError",
    "PdfPageError",
    "PdfRenderError",
    "PdfValidationError",
    "PdfViewerError",
    "TextMatch",
    "extract_page",
    "load_pdf_viewer_source",
    "open_pdf",
    "render_figure_images",
    "render_page_image",
    "search_text",
    "FORMULA_CROP_PADDING_POINTS",
    "FORMULA_CROP_ZOOM",
    "MAX_FORMULA_CROP_BYTES",
    "MAX_FORMULA_CROP_PIXELS",
    "detect_formula_regions",
    "render_formula_crop",
]
