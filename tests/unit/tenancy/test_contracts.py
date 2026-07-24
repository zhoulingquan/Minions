# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from minions.tenancy.factory import TenancySettings
from minions.tenancy.models import (
    DeploymentMode,
    StoreBackend,
    TenantPrincipal,
    TenantRole,
)
from minions.tenancy.permissions import permissions_for


def test_principal_is_immutable(tenancy_service):
    principal = tenancy_service.local_principal()
    with pytest.raises(Exception):
        principal.username = "forged"


def test_roles_map_to_explicit_permissions():
    assert "tenant.manage" in permissions_for(TenantRole.OWNER)
    assert "agent.use" in permissions_for(TenantRole.MEMBER)
    assert "member.manage" not in permissions_for(TenantRole.MEMBER)
    assert isinstance(permissions_for(TenantRole.VIEWER), frozenset)


def test_production_rejects_sqlite(tmp_path):
    settings = TenancySettings(
        mode=DeploymentMode.PRODUCTION,
        backend=StoreBackend.SQLITE,
        sqlite_path=tmp_path / "bad.db",
    )
    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        settings.validate()


def test_principal_does_not_accept_unknown_identity_fields(tenancy_service):
    value = tenancy_service.local_principal().model_dump()
    value["forged_tenant"] = "x"
    with pytest.raises(Exception):
        TenantPrincipal.model_validate(value)
