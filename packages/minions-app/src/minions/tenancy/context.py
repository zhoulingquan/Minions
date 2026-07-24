"""Request-local tenant principal binding."""

from __future__ import annotations

from contextvars import ContextVar, Token

from .models import TenantPrincipal


_CURRENT_PRINCIPAL: ContextVar[TenantPrincipal | None] = ContextVar(
    "minions_tenant_principal",
    default=None,
)


def bind_principal(
    principal: TenantPrincipal,
) -> Token[TenantPrincipal | None]:
    return _CURRENT_PRINCIPAL.set(principal)


def current_principal() -> TenantPrincipal | None:
    return _CURRENT_PRINCIPAL.get()


def reset_principal(token: Token[TenantPrincipal | None]) -> None:
    _CURRENT_PRINCIPAL.reset(token)


__all__ = ["bind_principal", "current_principal", "reset_principal"]
