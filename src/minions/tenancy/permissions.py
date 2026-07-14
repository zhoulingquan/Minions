"""Role-to-permission policy for Minions tenancy."""

from __future__ import annotations

from .models import TenantRole


TENANT_READ = "tenant.read"
TENANT_MANAGE = "tenant.manage"
MEMBER_READ = "member.read"
MEMBER_INVITE = "member.invite"
MEMBER_MANAGE = "member.manage"
AGENT_READ = "agent.read"
AGENT_USE = "agent.use"
AGENT_CREATE = "agent.create"
AGENT_MANAGE = "agent.manage"
AGENT_DELETE = "agent.delete"
AUDIT_READ = "audit.read"
QUOTA_READ = "quota.read"
QUOTA_MANAGE = "quota.manage"

SAGE_PERMISSIONS = frozenset(
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

_VIEW = frozenset({TENANT_READ, AGENT_READ, AUDIT_READ, QUOTA_READ})
_MEMBER = _VIEW | {AGENT_USE, "sage.scope.user.write.any"}
_OPERATOR = _MEMBER | {
    AGENT_CREATE,
    AGENT_MANAGE,
    MEMBER_READ,
    "sage.policy.manage",
    "sage.consolidation.approve",
    "sage.consolidation.apply",
    "sage.insight.approve",
    "sage.scope.tenant.read",
    "sage.scope.tenant.write",
    "sage.scope.agent.any",
    "sage.scope.agent.write.any",
    "sage.scope.case.any",
    "sage.trace.read.any",
    "sage.trace.write.any",
    "sage.content.export",
}
_ADMIN = _OPERATOR | {
    MEMBER_INVITE,
    MEMBER_MANAGE,
    AGENT_DELETE,
    QUOTA_MANAGE,
} | SAGE_PERMISSIONS
_OWNER = _ADMIN | {TENANT_MANAGE}

ROLE_PERMISSIONS: dict[TenantRole, frozenset[str]] = {
    TenantRole.OWNER: _OWNER,
    TenantRole.ADMIN: _ADMIN,
    TenantRole.OPERATOR: _OPERATOR,
    TenantRole.MEMBER: _MEMBER,
    TenantRole.VIEWER: _VIEW,
}


def permissions_for(role: TenantRole) -> frozenset[str]:
    """Return an immutable permission set for a role."""
    return ROLE_PERMISSIONS[role]


__all__ = [
    "AGENT_CREATE",
    "AGENT_DELETE",
    "AGENT_MANAGE",
    "AGENT_READ",
    "AGENT_USE",
    "AUDIT_READ",
    "MEMBER_INVITE",
    "MEMBER_MANAGE",
    "MEMBER_READ",
    "QUOTA_MANAGE",
    "QUOTA_READ",
    "ROLE_PERMISSIONS",
    "SAGE_PERMISSIONS",
    "TENANT_MANAGE",
    "TENANT_READ",
    "permissions_for",
]
