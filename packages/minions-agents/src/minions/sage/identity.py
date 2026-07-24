"""Trusted request identity propagation for SAGE.

Only authentication/channel adapters may construct and bind this identity.
Domain code receives an immutable value through a request-local ContextVar.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from uuid import UUID


SAGE_ADMIN_PERMISSIONS = frozenset(
    {
        "sage.policy.manage",
        "sage.consolidation.approve",
        "sage.consolidation.apply",
        "sage.consolidation.rollback",
        "sage.insight.approve",
        "sage.insight.rollback",
        "sage.insight.publish.high_risk",
        "sage.scope.tenant.read",
        "sage.scope.tenant.write",
        "sage.scope.team.any",
        "sage.scope.team.write",
        "sage.scope.project.any",
        "sage.scope.project.write",
        "sage.scope.user.any",
        "sage.scope.user.write.any",
        "sage.scope.agent.any",
        "sage.scope.agent.write.any",
        "sage.scope.case.any",
        "sage.classification.confidential.read",
        "sage.classification.confidential.write",
        "sage.classification.restricted.read",
        "sage.classification.restricted.write",
        "sage.trace.read.any",
        "sage.trace.write.any",
        "sage.content.export",
    },
)


@dataclass(frozen=True, slots=True)
class TrustedSageIdentity:
    """Server-attested tenant identity, never populated from model input."""

    tenant_id: UUID
    user_id: UUID
    source: str
    agent_uid: UUID | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    team_ids: tuple[UUID, ...] = ()
    project_ids: tuple[UUID, ...] = ()
    case_ids: tuple[UUID, ...] = ()
    service_id: str | None = None
    token_id: str | None = None


_CURRENT_IDENTITY: ContextVar[TrustedSageIdentity | None] = ContextVar(
    "sage_trusted_identity",
    default=None,
)


def bind_sage_identity(
    identity: TrustedSageIdentity,
) -> Token[TrustedSageIdentity | None]:
    """Bind an attested identity for the current asynchronous request."""
    return _CURRENT_IDENTITY.set(identity)


def current_sage_identity() -> TrustedSageIdentity | None:
    """Return the current attested identity, if one was bound upstream."""
    return _CURRENT_IDENTITY.get()


def reset_sage_identity(token: Token[TrustedSageIdentity | None]) -> None:
    """Restore the previous request identity."""
    _CURRENT_IDENTITY.reset(token)


__all__ = [
    "TrustedSageIdentity",
    "bind_sage_identity",
    "current_sage_identity",
    "reset_sage_identity",
    "SAGE_ADMIN_PERMISSIONS",
]
