"""Project-defined errors for the LLM infrastructure boundary."""


class LlmError(Exception):
    """Base class for failures callers may safely present to users."""


class LlmConfigurationError(LlmError):
    """Raised when the configured provider cannot be constructed or used."""


class LlmApiError(LlmError):
    """Raised when an LLM network or provider request fails."""


class LlmBadResponseError(LlmError):
    """Raised when the provider returns no usable assistant text."""
