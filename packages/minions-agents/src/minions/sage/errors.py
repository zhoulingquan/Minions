"""SAGE domain errors."""


class SageError(Exception):
    """Base error for the SAGE subsystem."""


class SageAccessDenied(SageError):
    """Raised when a principal cannot access a tenant or scope."""


class SageConflict(SageError):
    """Raised when an operation conflicts with existing SAGE state."""


class SageInvalidTransition(SageError):
    """Raised when a domain state transition is not allowed."""


class SageNotFound(SageError):
    """Raised when a tenant-scoped SAGE object does not exist."""

