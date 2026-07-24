"""Tenant and scope policy for SAGE."""

from __future__ import annotations

from uuid import UUID

from .errors import SageAccessDenied
from .models import Classification, Principal, ScopeRef, ScopeType


class ScopePolicy:
    """Fail-closed checks shared by SAGE services and storage adapters."""

    @staticmethod
    def require_tenant(principal: Principal, tenant_id: UUID) -> None:
        if principal.tenant_id != tenant_id:
            raise SageAccessDenied("cross-tenant SAGE access denied")

    @staticmethod
    def require_permission(principal: Principal, permission: str) -> None:
        if permission not in principal.permissions:
            raise SageAccessDenied(
                f"SAGE permission denied: {permission}",
            )

    @classmethod
    def require_classification_read(
        cls,
        principal: Principal,
        classification: Classification,
    ) -> None:
        if classification in {Classification.PUBLIC, Classification.INTERNAL}:
            return
        cls.require_permission(
            principal,
            f"sage.classification.{classification.value}.read",
        )

    @classmethod
    def require_classification_write(
        cls,
        principal: Principal,
        classification: Classification,
    ) -> None:
        if classification in {Classification.PUBLIC, Classification.INTERNAL}:
            return
        cls.require_permission(
            principal,
            f"sage.classification.{classification.value}.write",
        )

    @classmethod
    def require_scope(cls, principal: Principal, scope: ScopeRef) -> None:
        allowed = False
        scope_id = scope.scope_id

        if scope.scope_type is ScopeType.TENANT:
            allowed = (
                scope_id == str(principal.tenant_id)
                and "sage.scope.tenant.read" in principal.permissions
            )
        elif scope.scope_type is ScopeType.USER:
            allowed = scope_id == str(principal.user_id) or (
                "sage.scope.user.any" in principal.permissions
            )
        elif scope.scope_type is ScopeType.AGENT:
            allowed = scope_id == str(principal.agent_uid) or (
                "sage.scope.agent.any" in principal.permissions
            )
        elif scope.scope_type is ScopeType.SESSION:
            allowed = scope_id == principal.session_id
        elif scope.scope_type is ScopeType.TEAM:
            allowed = cls._contains_uuid(scope_id, principal.team_ids) or (
                "sage.scope.team.any" in principal.permissions
            )
        elif scope.scope_type is ScopeType.PROJECT:
            allowed = cls._contains_uuid(scope_id, principal.project_ids) or (
                "sage.scope.project.any" in principal.permissions
            )
        elif scope.scope_type is ScopeType.CASE:
            allowed = cls._contains_uuid(scope_id, principal.case_ids) or (
                "sage.scope.case.any" in principal.permissions
            )

        if not allowed:
            raise SageAccessDenied(
                f"SAGE scope access denied: {scope.scope_type}:{scope_id}",
            )

    @classmethod
    def require_write_scope(cls, principal: Principal, scope: ScopeRef) -> None:
        """Require visibility plus explicit authority for shared writes."""
        cls.require_scope(principal, scope)
        permission: str | None = None
        if scope.scope_type in {
            ScopeType.TENANT,
            ScopeType.TEAM,
            ScopeType.PROJECT,
        }:
            permission = f"sage.scope.{scope.scope_type.value}.write"
        elif scope.scope_type is ScopeType.USER and (
            scope.scope_id != str(principal.user_id)
        ):
            permission = "sage.scope.user.write.any"
        elif scope.scope_type is ScopeType.AGENT and (
            scope.scope_id != str(principal.agent_uid)
        ):
            permission = "sage.scope.agent.write.any"
        if permission is not None:
            cls.require_permission(principal, permission)

    @staticmethod
    def _contains_uuid(raw: str, values: tuple[UUID, ...]) -> bool:
        try:
            value = UUID(raw)
        except ValueError:
            return False
        return value in values
