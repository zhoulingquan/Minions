"""Stable domain errors translated to HTTP only at application boundaries."""


class TenancyError(Exception):
    """Base tenancy error."""


class AccessDenied(TenancyError):
    """The attested caller is not permitted to perform an action."""


class ResourceNotFound(TenancyError):
    """A resource is absent or hidden by a tenant boundary."""


class Conflict(TenancyError):
    """A uniqueness, state or optimistic-concurrency conflict."""


class QuotaExceeded(TenancyError):
    """The tenant would exceed an enforced entitlement."""


class AuthenticationFailed(TenancyError):
    """Credentials or session proof are invalid."""


class AmbiguousTenant(TenancyError):
    """Valid credentials belong to multiple tenants and need a selection."""


__all__ = [
    "AccessDenied",
    "AmbiguousTenant",
    "AuthenticationFailed",
    "Conflict",
    "QuotaExceeded",
    "ResourceNotFound",
    "TenancyError",
]
