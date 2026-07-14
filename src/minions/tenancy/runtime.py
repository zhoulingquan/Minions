"""Unified trusted-principal scope for HTTP, channels, Cron and ACP."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from .context import bind_principal, current_principal, reset_principal
from .errors import ResourceNotFound
from .factory import get_tenancy_service
from .models import DeploymentMode

logger = logging.getLogger(__name__)
_LEASE_RENEW_INTERVAL_SECONDS = 60


async def _renew_task_lease(service, principal, lease_id) -> None:
    while True:
        await asyncio.sleep(_LEASE_RENEW_INTERVAL_SECONDS)
        try:
            renewed = service.renew_task_lease(principal, lease_id)
        except Exception:
            logger.exception("Failed to renew tenant task lease")
            return
        if not renewed:
            logger.error("Tenant task lease expired before renewal")
            return


@asynccontextmanager
async def agent_runtime_scope(agent_id: str, *, source: str):
    """Authorize or attest one Agent execution and bind SAGE consistently."""
    from ..sage.identity import bind_sage_identity, reset_sage_identity

    service = get_tenancy_service()
    principal = current_principal()
    owns_binding = principal is None
    if principal is not None:
        service.assert_agent_access(principal, agent_id)
    else:
        try:
            principal = service.agent_runtime_principal(agent_id, source=source)
        except ResourceNotFound:
            from ..app.auth import is_tenancy_auth_enabled

            if is_tenancy_auth_enabled() or service.settings.mode in {
                DeploymentMode.TENANT,
                DeploymentMode.PRODUCTION,
            }:
                raise
            # Compatibility only for isolated unit/runtime construction that
            # did not run application startup reconciliation.
            yield None
            return
    lease_id = service.acquire_task_lease(principal, agent_id)
    principal_token = bind_principal(principal) if owns_binding else None
    sage_token = bind_sage_identity(principal.to_sage_identity(agent_id=agent_id))
    renewal = asyncio.create_task(
        _renew_task_lease(service, principal, lease_id),
        name=f"tenant-task-lease:{lease_id}",
    )
    try:
        yield principal
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError):
            await renewal
        try:
            service.release_task_lease(principal, lease_id)
        except Exception:
            logger.exception("Failed to release tenant task lease")
        finally:
            reset_sage_identity(sage_token)
            if principal_token is not None:
                reset_principal(principal_token)


__all__ = ["agent_runtime_scope"]
