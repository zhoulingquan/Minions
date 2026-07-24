"""Idempotent bridge from existing Minions configuration to tenancy 2.1."""

from __future__ import annotations

import logging
from typing import Any

from ..config.utils import load_config
from .errors import Conflict, QuotaExceeded
from .models import TenantPrincipal

logger = logging.getLogger(__name__)


def import_configured_agents(service: Any, principal: TenantPrincipal) -> int:
    """Bind every unowned configured Agent to the selected tenant.

    Existing workspace paths are deliberately retained. New Agent creation uses
    tenant paths; moving old workspaces is a separate offline operation.
    """
    config = load_config()
    imported = 0
    for agent_id in config.agents.profiles:
        try:
            before = service.store.get_agent_grant(agent_id)
            service.import_agent(principal, agent_id)
            imported += int(before is None)
        except Conflict:
            logger.warning(
                "tenancy migration left agent %s unchanged because it belongs "
                "to another tenant",
                agent_id,
            )
        except QuotaExceeded:
            logger.error(
                "tenancy migration stopped at agent %s because the tenant "
                "agent quota is exhausted",
                agent_id,
            )
            raise
    if imported:
        service.audit(
            principal,
            action="migration.agents.import",
            resource_type="agent_collection",
            resource_id=str(principal.tenant_id),
            metadata={"count": imported},
        )
    return imported


def initialize_tenancy_control_plane() -> Any:
    """Initialize storage and reconcile legacy Agent references at startup."""
    from ..app.auth import (
        get_legacy_auth_account_for_migration,
        is_auth_enabled,
        is_tenancy_auth_enabled,
        is_tenant_mode,
    )
    from .factory import get_tenancy_service

    service = get_tenancy_service()
    principal = None
    if is_tenancy_auth_enabled():
        principal = service.system_owner_principal()
        if principal is None:
            legacy = get_legacy_auth_account_for_migration()
            if legacy is not None:
                principal = service.import_legacy_owner(
                    tenant_id=legacy["tenant_id"],
                    user_id=legacy["user_id"],
                    username=legacy["username"],
                    display_name=legacy["display_name"],
                    password_hash=legacy["password_hash"],
                    password_salt=legacy["password_salt"],
                    password_algorithm=legacy["password_algorithm"],
                    password_iterations=legacy["password_iterations"],
                )
        if principal is None and is_tenant_mode():
            # Fresh production installation: only public bootstrap registration
            # is available until the first owner is created.
            return service
    elif not is_auth_enabled():
        principal = service.local_principal(source="local-startup")

    if principal is not None:
        import_configured_agents(service, principal)
    return service


__all__ = ["import_configured_agents", "initialize_tenancy_control_plane"]
