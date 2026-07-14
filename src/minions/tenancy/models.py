"""Immutable domain models for the Minions 2.1 tenancy control plane."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    """Base class for values that must not mutate after attestation."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DeploymentMode(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    TENANT = "tenant"
    PRODUCTION = "production"


class StoreBackend(StrEnum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class TenantRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    MEMBER = "member"
    VIEWER = "viewer"


class AgentAccess(StrEnum):
    PRIVATE = "private"
    TENANT = "tenant"


class AgentStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class InviteStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class Tenant(FrozenModel):
    tenant_id: UUID
    slug: str
    name: str
    status: TenantStatus
    version: int = 1
    created_at: datetime
    updated_at: datetime


class UserAccount(FrozenModel):
    user_id: UUID
    username: str
    display_name: str
    status: UserStatus
    version: int = 1
    created_at: datetime
    updated_at: datetime


class TenantMembership(FrozenModel):
    tenant_id: UUID
    user_id: UUID
    role: TenantRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime


class TenantPrincipal(FrozenModel):
    """Server-attested caller identity shared by every runtime entry point."""

    tenant_id: UUID
    user_id: UUID
    username: str
    role: TenantRole
    permissions: frozenset[str] = Field(default_factory=frozenset)
    source: str
    session_id: UUID | None = None
    service_id: str | None = None
    token_id: str | None = None

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    def to_sage_identity(self, *, agent_id: str | None = None):
        """Convert to SAGE's trusted value without accepting client claims."""
        from uuid import uuid5

        from ..sage.identity import TrustedSageIdentity

        agent_uid = (
            uuid5(self.tenant_id, f"agent:{agent_id}") if agent_id else None
        )
        return TrustedSageIdentity(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            source=self.source,
            agent_uid=agent_uid,
            permissions=self.permissions,
            service_id=self.service_id,
            token_id=self.token_id,
        )


class AuthSession(FrozenModel):
    session_id: UUID
    tenant_id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None


class AgentGrant(FrozenModel):
    agent_id: str
    tenant_id: UUID
    owner_user_id: UUID
    access: AgentAccess
    status: AgentStatus
    created_at: datetime
    updated_at: datetime


class TenantQuota(FrozenModel):
    tenant_id: UUID
    max_members: int = 25
    max_agents: int = 20
    max_concurrent_tasks: int = 20
    max_storage_mb: int = 10_240
    updated_at: datetime


class TenantUsage(FrozenModel):
    tenant_id: UUID
    members: int = 0
    agents: int = 0
    concurrent_tasks: int = 0
    storage_mb: int = 0
    version: int = 1
    updated_at: datetime


class TenantInvite(FrozenModel):
    invite_id: UUID
    tenant_id: UUID
    username: str
    role: TenantRole
    token_hash: str
    status: InviteStatus
    expires_at: datetime
    created_by: UUID
    created_at: datetime
    accepted_by: UUID | None = None
    accepted_at: datetime | None = None


class TenantAuditEvent(FrozenModel):
    event_id: UUID
    tenant_id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    request_id: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TenantOverview(FrozenModel):
    tenant: Tenant
    membership: TenantMembership
    quota: TenantQuota
    usage: TenantUsage
    permissions: tuple[str, ...]


__all__ = [
    "AgentAccess",
    "AgentGrant",
    "AgentStatus",
    "AuthSession",
    "DeploymentMode",
    "InviteStatus",
    "MembershipStatus",
    "StoreBackend",
    "Tenant",
    "TenantAuditEvent",
    "TenantInvite",
    "TenantMembership",
    "TenantOverview",
    "TenantPrincipal",
    "TenantQuota",
    "TenantRole",
    "TenantStatus",
    "TenantUsage",
    "UserAccount",
    "UserStatus",
]
