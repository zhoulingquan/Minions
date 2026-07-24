# -*- coding: utf-8 -*-
"""Security and behavior tests for the SAGE management API."""

from types import SimpleNamespace
from uuid import uuid4, uuid5

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from minions.app.routers import sage as sage_router_module
from minions.sage.identity import SAGE_ADMIN_PERMISSIONS, TrustedSageIdentity
from minions.sage.models import Principal, ScopeRef, ScopeType, TraceType
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


@pytest.fixture
def runtime(tmp_path):
    import asyncio

    value = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    asyncio.run(value.start())
    yield value
    asyncio.run(value.close())


def _identity(*, permissions=SAGE_ADMIN_PERMISSIONS) -> TrustedSageIdentity:
    return TrustedSageIdentity(
        tenant_id=uuid4(),
        user_id=uuid4(),
        source="test-http",
        permissions=frozenset(permissions),
    )


def _client(monkeypatch, runtime, identity: TrustedSageIdentity | None):
    workspace = SimpleNamespace(agent_id="default", sage_runtime=runtime)

    async def get_workspace(_request):
        return workspace

    monkeypatch.setattr(
        sage_router_module,
        "get_agent_for_request",
        get_workspace,
    )
    application = FastAPI()

    if identity is not None:

        @application.middleware("http")
        async def bind_identity(request: Request, call_next):
            request.state.sage_identity = identity
            return await call_next(request)

    application.include_router(sage_router_module.router, prefix="/api")
    return TestClient(application)


def test_overview_uses_trusted_identity(monkeypatch, runtime) -> None:
    client = _client(monkeypatch, runtime, _identity())
    response = client.get("/api/sage/overview")
    assert response.status_code == 200
    assert response.json()["snapshot"]["knowledge_total"] == 0
    assert len(response.json()["policies"]) == 6


def test_missing_identity_fails_closed_in_tenant_mode(
    monkeypatch,
    runtime,
) -> None:
    monkeypatch.setattr(sage_router_module, "is_tenant_mode", lambda: True)
    client = _client(monkeypatch, runtime, None)
    response = client.get("/api/sage/overview")
    assert response.status_code == 401
    assert "identity" in response.json()["detail"].lower()


def test_policy_rejects_forged_tenant_field(monkeypatch, runtime) -> None:
    client = _client(monkeypatch, runtime, _identity())
    response = client.put(
        "/api/sage/policies/feedback_learning",
        json={"mode": "auto", "tenant_id": str(uuid4())},
    )
    assert response.status_code == 422


def test_maintenance_rejects_invalid_business_date(
    monkeypatch,
    runtime,
) -> None:
    client = _client(monkeypatch, runtime, _identity())
    response = client.post(
        "/api/sage/maintenance",
        json={"local_date": "not-a-date"},
    )
    assert response.status_code == 422


def test_policy_update_requires_server_granted_permission(
    monkeypatch,
    runtime,
) -> None:
    client = _client(monkeypatch, runtime, _identity(permissions=frozenset()))
    response = client.put(
        "/api/sage/policies/feedback_learning",
        json={"mode": "auto"},
    )
    assert response.status_code == 403
    assert "sage.policy.manage" in response.json()["detail"]


def test_cross_tenant_candidate_identifier_is_not_disclosed(
    monkeypatch,
    runtime,
) -> None:
    client = _client(monkeypatch, runtime, _identity())
    response = client.post(f"/api/sage/candidates/{uuid4()}/approve")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_authenticated_case_review_forms_a_draft_insight(
    monkeypatch,
    runtime,
) -> None:
    import asyncio

    identity = _identity()
    principal = Principal(
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        agent_uid=uuid5(identity.tenant_id, "agent:default"),
        source="test",
        session_id="business-session",
        permissions=identity.permissions,
    )

    async def prepare_case():
        turn = await runtime.begin(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            user_input="Prepare the renewal proposal",
            process="renewal",
            goal="Renew the customer",
        )
        await runtime.observe(
            principal,
            turn,
            trace_type=TraceType.AGENT_OUTPUT,
            content=(
                "Validated the decision maker before sending the " "proposal."
            ),
        )
        await runtime.cases.mark_pending_review(principal, turn.case_id)
        return turn.case_id

    case_id = asyncio.run(prepare_case())
    client = _client(monkeypatch, runtime, identity)
    response = client.post(
        f"/api/sage/cases/{case_id}/review",
        json={"outcome": "success", "decision_summary": ""},
    )

    assert response.status_code == 200
    assert response.json()["case"]["state"] == "completed"
    assert response.json()["insight"]["state"] == "draft"
    assert "Authenticated" not in response.text


def test_insight_can_be_revised_through_management_api(
    monkeypatch,
    runtime,
) -> None:
    import asyncio

    identity = _identity()
    principal = Principal(
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        agent_uid=uuid5(identity.tenant_id, "agent:default"),
        source="test",
        session_id="revise-session",
        permissions=identity.permissions,
    )

    async def prepare_insight():
        return await runtime.growth.propose(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="旧心得",
            content="需要修订的内容",
        )

    insight = asyncio.run(prepare_insight())
    client = _client(monkeypatch, runtime, identity)
    response = client.put(
        f"/api/sage/insights/{insight.insight_id}",
        json={
            "title": "发票复核经验",
            "content": "先核对合同和验收证据。",
            "applicability": {"process": "发票复核"},
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "发票复核经验"
    assert response.json()["version"] == 2
    listed = client.get("/api/sage/insights")
    assert listed.status_code == 200
    assert [value["title"] for value in listed.json()["items"]] == [
        "发票复核经验",
    ]


def test_playbook_list_is_tenant_scoped(monkeypatch, runtime) -> None:
    import asyncio

    from minions.sage.models import Playbook, PlaybookState

    identity = _identity()
    principal = Principal(
        tenant_id=identity.tenant_id,
        user_id=identity.user_id,
        agent_uid=uuid5(identity.tenant_id, "agent:default"),
        source="test",
        session_id="playbook-session",
        permissions=identity.permissions,
    )

    async def prepare_playbook():
        await runtime.store.save_playbook(
            principal,
            Playbook(
                tenant_id=principal.tenant_id,
                scope=ScopeRef(
                    scope_type=ScopeType.USER,
                    scope_id=str(principal.user_id),
                ),
                name="月度对账手册",
                state=PlaybookState.ACTIVE,
            ),
        )

    asyncio.run(prepare_playbook())
    client = _client(monkeypatch, runtime, identity)
    response = client.get("/api/sage/playbooks")

    assert response.status_code == 200
    assert [value["name"] for value in response.json()["items"]] == [
        "月度对账手册",
    ]
