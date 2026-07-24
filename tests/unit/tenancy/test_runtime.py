# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from minions.tenancy.errors import ResourceNotFound
from minions.sage.identity import current_sage_identity
from minions.tenancy.context import current_principal
from minions.tenancy.models import DeploymentMode, TenantPrincipal, TenantRole
from minions.tenancy.runtime import agent_runtime_scope


class _MissingAgentService:
    settings = SimpleNamespace(mode=DeploymentMode.DEVELOPMENT)

    @staticmethod
    def agent_runtime_principal(agent_id: str, *, source: str):
        del agent_id, source
        raise ResourceNotFound("missing")


async def test_explicit_development_tenancy_fails_closed(monkeypatch):
    monkeypatch.setenv("MINIONS_TENANCY_ENABLED", "true")
    monkeypatch.setattr(
        "minions.tenancy.runtime.get_tenancy_service",
        lambda: _MissingAgentService(),
    )

    with pytest.raises(ResourceNotFound):
        async with agent_runtime_scope("missing", source="test"):
            pass


async def test_legacy_local_runtime_keeps_test_compatibility(monkeypatch):
    monkeypatch.delenv("MINIONS_TENANCY_ENABLED", raising=False)
    monkeypatch.delenv("MINIONS_TENANCY_MODE", raising=False)
    monkeypatch.setattr(
        "minions.tenancy.runtime.get_tenancy_service",
        lambda: _MissingAgentService(),
    )

    async with agent_runtime_scope("missing", source="test") as principal:
        assert principal is None


async def test_every_agent_runtime_binds_same_tenant_identity_to_sage(
    monkeypatch,
):
    principal = TenantPrincipal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        username="channel-service",
        role=TenantRole.MEMBER,
        permissions=frozenset({"sage.scope.user.write.any"}),
        source="channel",
        service_id="channel-worker",
    )

    class Service:
        settings = SimpleNamespace(mode=DeploymentMode.DEVELOPMENT)

        @staticmethod
        def agent_runtime_principal(agent_id: str, *, source: str):
            assert agent_id == "sales-agent"
            assert source == "runtime:feishu"
            return principal

        @staticmethod
        def acquire_task_lease(_principal, _agent_id):
            return uuid4()

        @staticmethod
        def release_task_lease(_principal, _lease_id):
            return True

    monkeypatch.setattr(
        "minions.tenancy.runtime.get_tenancy_service",
        lambda: Service(),
    )

    async with agent_runtime_scope(
        "sales-agent",
        source="runtime:feishu",
    ) as bound:
        identity = current_sage_identity()
        assert bound is principal
        assert current_principal() is principal
        assert identity is not None
        assert identity.tenant_id == principal.tenant_id
        assert identity.user_id == principal.user_id
        assert identity.agent_uid is not None
        assert identity.permissions == principal.permissions

    assert current_principal() is None
    assert current_sage_identity() is None
