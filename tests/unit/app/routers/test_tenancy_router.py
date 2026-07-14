from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from minions.app.routers import tenancy as tenancy_router_module
from minions.tenancy.factory import TenancySettings, build_tenancy_service
from minions.tenancy.models import (
    DeploymentMode,
    StoreBackend,
    TenantPrincipal,
    TenantRole,
)


@pytest.fixture()
def tenancy_service(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "MINIONS_TENANCY_SIGNING_KEY_FILE",
        str(tmp_path / "tenancy.key"),
    )
    service = build_tenancy_service(
        TenancySettings(
            mode=DeploymentMode.TEST,
            backend=StoreBackend.SQLITE,
            sqlite_path=tmp_path / "tenancy.db",
            token_ttl_seconds=3_600,
        ),
    )
    yield service
    service.close()


def _client(
    monkeypatch,
    tenancy_service,
    principal: TenantPrincipal | None,
) -> TestClient:
    application = FastAPI()

    @application.middleware("http")
    async def bind_principal(request: Request, call_next):
        request.state.tenant_principal = principal
        return await call_next(request)

    application.include_router(tenancy_router_module.router, prefix="/api")
    monkeypatch.setattr(
        tenancy_router_module,
        "get_tenancy_service",
        lambda: tenancy_service,
    )
    return TestClient(application)


def test_owner_can_provision_a_space_through_the_http_contract(
    monkeypatch,
    tenancy_service,
):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    client = _client(monkeypatch, tenancy_service, owner)

    created = client.post(
        "/api/tenancy/spaces",
        json={"name": "Beta", "slug": "beta"},
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload["token"]
    assert payload["role"] == "owner"
    selected = tenancy_service.verify_token(payload["token"])
    spaces_client = _client(monkeypatch, tenancy_service, selected)
    spaces = spaces_client.get("/api/tenancy/spaces")
    assert spaces.status_code == 200
    assert {item["slug"] for item in spaces.json()["items"]} == {"acme", "beta"}


def test_non_owner_cannot_provision_a_space(monkeypatch, tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    _, raw = tenancy_service.invite_member(
        owner,
        username="staff",
        role=TenantRole.MEMBER,
    )
    _, staff = tenancy_service.accept_invite(
        invite_token=raw,
        username="staff",
        password="staff-password",
    )
    client = _client(monkeypatch, tenancy_service, staff)

    response = client.post(
        "/api/tenancy/spaces",
        json={"name": "Forbidden", "slug": "forbidden"},
    )

    assert response.status_code == 403


def test_invite_acceptance_does_not_require_a_bound_principal(
    monkeypatch,
    tenancy_service,
):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    _, raw = tenancy_service.invite_member(
        owner,
        username="staff",
        role=TenantRole.OPERATOR,
    )
    client = _client(monkeypatch, tenancy_service, None)

    response = client.post(
        "/api/tenancy/invites/accept",
        json={
            "invite_token": raw,
            "username": "staff",
            "password": "staff-password",
            "display_name": "Staff",
        },
    )

    assert response.status_code == 200
    assert response.json()["role"] == "operator"
