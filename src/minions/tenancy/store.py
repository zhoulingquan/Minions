"""Persistence contract for the tenancy control plane."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from .models import (
    AgentAccess,
    AgentGrant,
    AuthSession,
    MembershipStatus,
    Tenant,
    TenantAuditEvent,
    TenantInvite,
    TenantMembership,
    TenantQuota,
    TenantRole,
    TenantUsage,
    UserAccount,
)


class TenancyStore(Protocol):
    """Backend-neutral operations used by :class:`TenancyService`."""

    def initialize(self) -> None: ...

    def close(self) -> None: ...

    def has_login_users(self) -> bool: ...

    def ensure_local_identity(self) -> tuple[Tenant, UserAccount, TenantMembership]: ...

    def create_tenant_owner(
        self,
        *,
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        slug: str,
        tenant_name: str,
        username: str,
        display_name: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
    ) -> tuple[Tenant, UserAccount, TenantMembership]: ...

    def create_tenant_for_existing_owner(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        slug: str,
        tenant_name: str,
        now: datetime,
    ) -> tuple[Tenant, UserAccount, TenantMembership]: ...

    def get_user_credentials(self, username: str) -> dict[str, Any] | None: ...

    def update_user_password(
        self,
        *,
        user_id: UUID,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        now: datetime,
    ) -> None: ...

    def update_user_profile(
        self,
        *,
        user_id: UUID,
        username: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        now: datetime,
    ) -> None: ...

    def get_first_active_owner(self) -> dict[str, Any] | None: ...

    def list_active_memberships(
        self,
        user_id: UUID,
    ) -> list[tuple[Tenant, TenantMembership]]: ...

    def create_session(self, session: AuthSession) -> None: ...

    def resolve_session(
        self,
        token_hash: str,
        now: datetime,
        tenant_id: UUID,
    ) -> dict[str, Any] | None: ...

    def touch_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> None: ...

    def revoke_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> bool: ...

    def revoke_user_sessions(
        self,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> int: ...

    def get_tenant(self, tenant_id: UUID) -> Tenant | None: ...

    def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]: ...

    def update_membership(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        role: TenantRole | None,
        status: MembershipStatus | None,
        now: datetime,
    ) -> TenantMembership: ...

    def create_invite(self, invite: TenantInvite) -> None: ...

    def list_invites(self, tenant_id: UUID, now: datetime) -> list[TenantInvite]: ...

    def revoke_invite(
        self,
        tenant_id: UUID,
        invite_id: UUID,
        now: datetime,
    ) -> bool: ...

    def get_pending_invite(
        self,
        *,
        token_hash: str,
        now: datetime,
    ) -> TenantInvite | None: ...

    def accept_invite(
        self,
        *,
        token_hash: str,
        username: str,
        display_name: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        now: datetime,
    ) -> tuple[Tenant, UserAccount, TenantMembership]: ...

    def register_agent(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        access: AgentAccess,
        now: datetime,
    ) -> AgentGrant: ...

    def import_agent(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        now: datetime,
    ) -> AgentGrant: ...

    def get_agent_grant(self, agent_id: str) -> AgentGrant | None: ...

    def get_agent_runtime_identity(self, agent_id: str) -> dict[str, Any] | None: ...

    def list_agent_grants(self, tenant_id: UUID) -> list[AgentGrant]: ...

    def archive_agent(self, agent_id: str, tenant_id: UUID, now: datetime) -> bool: ...

    def rollback_agent_registration(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        now: datetime,
    ) -> bool: ...

    def get_quota(self, tenant_id: UUID) -> TenantQuota: ...

    def get_usage(self, tenant_id: UUID) -> TenantUsage: ...

    def update_storage_usage(
        self,
        tenant_id: UUID,
        storage_mb: int,
        now: datetime,
    ) -> None: ...

    def acquire_task_lease(
        self,
        *,
        tenant_id: UUID,
        agent_id: str,
        now: datetime,
        expires_at: datetime,
    ) -> UUID: ...

    def renew_task_lease(
        self,
        *,
        lease_id: UUID,
        tenant_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> bool: ...

    def release_task_lease(
        self,
        *,
        lease_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> bool: ...

    def append_audit(self, event: TenantAuditEvent) -> None: ...

    def list_audit_events(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        before: datetime | None = None,
    ) -> list[TenantAuditEvent]: ...


__all__ = ["TenancyStore"]
