"""Application-facing translation validation and error mapping."""

from dataclasses import dataclass

from researchmind.translation.base import TranslationProvider
from researchmind.translation.errors import TranslationError


@dataclass(frozen=True)
class TranslationRequest:
    """The exact normalized payload shown before an explicit translation call."""

    source_text: str
    target_language: str


def prepare_translation_request(
    text: str,
    target_language: str,
) -> TranslationRequest:
    """Validate and normalize the exact fields sent to a translation provider."""

    source_text = text.strip()
    normalized_target = target_language.strip()
    if not source_text:
        raise TranslationError("Selected text must not be blank.")
    if not normalized_target:
        raise TranslationError("Target language must not be blank.")
    return TranslationRequest(
        source_text=source_text,
        target_language=normalized_target,
    )


def translate_text(
    text: str,
    target_language: str,
    provider: TranslationProvider,
) -> str:
    """Translate non-blank text and expose only project translation errors."""

    request = prepare_translation_request(text, target_language)

    try:
        translated = provider.translate(
            request.source_text,
            request.target_language,
        ).strip()
    except TranslationError:
        raise
    except Exception:
        raise TranslationError("Translation request failed.") from None

    if not translated:
        raise TranslationError("Translation provider returned an empty response.")
    return translated
