"""Independent translation capability package."""
"""Public translation API."""

from researchmind.translation.base import TranslationProvider
from researchmind.translation.errors import TranslationError
from researchmind.translation.providers import LlmTranslationProvider
from researchmind.translation.service import (
    TranslationRequest,
    prepare_translation_request,
    translate_text,
)

__all__ = [
    "LlmTranslationProvider",
    "TranslationError",
    "TranslationProvider",
    "TranslationRequest",
    "prepare_translation_request",
    "translate_text",
]
