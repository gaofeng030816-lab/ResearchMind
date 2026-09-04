"""Application-facing translation validation and error mapping."""

from researchmind.translation.base import TranslationProvider
from researchmind.translation.errors import TranslationError


def translate_text(
    text: str,
    target_language: str,
    provider: TranslationProvider,
) -> str:
    """Translate non-blank text and expose only project translation errors."""

    source_text = text.strip()
    normalized_target = target_language.strip()
    if not source_text:
        raise TranslationError("Selected text must not be blank.")
    if not normalized_target:
        raise TranslationError("Target language must not be blank.")

    try:
        translated = provider.translate(source_text, normalized_target).strip()
    except TranslationError:
        raise
    except Exception:
        raise TranslationError("Translation request failed.") from None

    if not translated:
        raise TranslationError("Translation provider returned an empty response.")
    return translated
