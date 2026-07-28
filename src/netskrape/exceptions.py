"""Package-specific exception hierarchy."""


class NetSkrapeError(Exception):
    """Base exception for all expected NetSkrape failures."""


class ConfigurationError(NetSkrapeError):
    """Raised when application configuration is invalid."""


class FetchError(NetSkrapeError):
    """Raised when a resource cannot be retrieved."""


class ExtractionError(NetSkrapeError):
    """Raised when retrieved content cannot be extracted."""


class StorageError(NetSkrapeError):
    """Raised when extracted data cannot be persisted."""
