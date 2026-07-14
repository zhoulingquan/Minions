"""Tenant-authorized management API for the SAGE experience system."""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...constant import WORKING_DIR
from ...sage.errors import SageAccessDenied, SageConflict, SageNotFound
from ...sage.identity import (
    SAGE_ADMIN_PERMISSIONS,
    TrustedSageIdentity,
    current_sage_identity,
)
from ...sage.models import (
    ActivationMode,
    CandidateState,
    CaseOutcome,
    CaseState,
    Classification,
    ItemKind,
    ItemState,
    InsightState,
    FeedbackVerdict,
    PlaybookState,
    Principal,
    RiskLevel,
    SageCapability,
    ScopeRef,
    TraceType,
)
from ..agent_context import get_agent_for_request
from ..auth import has_registered_users, is_auth_enabled, is_tenant_mode

router = APIRouter(prefix="/sage", tags=["sage"])


class PolicyUpdate(BaseModel):
    """Validated policy mutation; tenant identity is intentionally absent."""

    model_config = ConfigDict(extra="forbid")

    mode: ActivationMode
    scope: ScopeRef | None = None
    max_auto_risk: RiskLevel = RiskLevel.LOW
    settings: dict[str, Any] = Field(default_factory=dict)

    @field_validator("settings")
    @classmethod
    def validate_settings(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, ensure_ascii=False)) > 16_384:
            raise ValueError("policy settings cannot exceed 16 KiB")
        if any(not key or len(key) > 64 for key in value):
            raise ValueError("policy setting keys must be 1-64 characters")
        return value


class MaintenanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_date: str | None = Field(default=None, max_length=10)

    @field_validator("local_date")
    @classmethod
    def validate_local_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value


class CaseReviewRequest(BaseModel):
    """Authenticated business review; tenant and actor are server-bound."""

    model_config = ConfigDict(extra="forbid")

    outcome: CaseOutcome
    decision_summary: str = Field(default="", max_length=4000)
    outcome_metrics: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome")
    @classmethod
    def require_decision(cls, value: CaseOutcome) -> CaseOutcome:
        if value is CaseOutcome.UNKNOWN:
            raise ValueError("review outcome cannot be unknown")
        return value


class InsightRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1, max_length=4000)
    applicability: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "content")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value cannot be blank")
        return value


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: UUID
    verdict: FeedbackVerdict
    source_id: UUID | None = None
    comment: str = Field(default="", max_length=4000)


async def _context(request: Request) -> tuple[Any, Principal]:
    workspace = await get_agent_for_request(request)
    runtime = getattr(workspace, "sage_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="SAGE service is unavailable")
    identity = _identity(request)
    agent_uid = uuid5(identity.tenant_id, f"agent:{workspace.agent_id}")
    user_id = identity.user_id
    principal = Principal(
        tenant_id=identity.tenant_id,
        user_id=user_id,
        agent_uid=agent_uid,
        source=identity.source[:64] or "http",
        session_id=(
            request.headers.get("X-Root-Session-Id")
            or f"sage-management:{identity.token_id or user_id}"
        )[:512],
        permissions=identity.permissions,
        team_ids=identity.team_ids,
        project_ids=identity.project_ids,
        case_ids=identity.case_ids,
        service_id=identity.service_id,
        token_id=identity.token_id,
    )
    return runtime, principal


async def _case_lesson(runtime: Any, principal: Principal, case: Any) -> str:
    """Build a conservative draft lesson from server-recorded evidence."""
    traces = await runtime.store.list_traces(
        principal,
        case_id=case.case_id,
        limit=1000,
    )
    output = next(
        (
            trace.content.strip()
            for trace in reversed(traces)
            if trace.trace_type is TraceType.AGENT_OUTPUT and trace.content.strip()
        ),
        "",
    )
    parts = []
    if case.goal.strip():
        parts.append(f"业务目标：{case.goal.strip()}")
    if output:
        parts.append(f"有效做法与结果摘要：{output[:2400]}")
    return "\n".join(parts)[:4000]


def _identity(request: Request) -> TrustedSageIdentity:
    identity = getattr(request.state, "sage_identity", None)
    if not isinstance(identity, TrustedSageIdentity):
        identity = current_sage_identity()
    if isinstance(identity, TrustedSageIdentity):
        return identity
    # Explicit no-auth development mode is a server policy, not a request claim.
    if not is_tenant_mode() and not is_auth_enabled() and not has_registered_users():
        tenant_id = uuid5(
            NAMESPACE_URL,
            f"minions:local-tenant:{WORKING_DIR.resolve()}",
        )
        return TrustedSageIdentity(
            tenant_id=tenant_id,
            user_id=uuid5(tenant_id, "local-admin"),
            source="local-http",
            permissions=SAGE_ADMIN_PERMISSIONS,
        )
    raise HTTPException(status_code=401, detail="Trusted SAGE identity required")


def _page(values: list[Any], offset: int, limit: int) -> dict[str, Any]:
    return {
        "items": values[offset : offset + limit],
        "offset": offset,
        "limit": limit,
        "has_more": len(values) > offset + limit,
    }


def _item_view(item: Any, principal: Principal) -> dict[str, Any]:
    value = item.model_dump(mode="json")
    if (
        item.classification
        in {
            Classification.CONFIDENTIAL,
            Classification.RESTRICTED,
        }
        and "sage.content.export" not in principal.permissions
    ):
        value["title"] = "受限知识"
        value["content"] = "[内容已隐藏]"
        value["structured_data"] = {}
    return value


def _candidate_view(candidate: Any, principal: Principal) -> dict[str, Any]:
    value = candidate.model_dump(mode="json")
    if "sage.content.export" in principal.permissions:
        return value
    for snapshot in value.get("before_snapshots", {}).values():
        if snapshot.get("classification") in {"confidential", "restricted"}:
            snapshot["title"] = "受限知识"
            snapshot["content"] = "[内容已隐藏]"
            snapshot["structured_data"] = {}
    return value


def _raise_domain(exc: Exception) -> None:
    if isinstance(exc, SageAccessDenied):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, SageNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, SageConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


@router.get("/overview")
async def overview(request: Request) -> dict[str, Any]:
    runtime, principal = await _context(request)
    snapshot = await runtime.metrics.snapshot(principal)
    policies = [
        await runtime.control.resolve(principal, capability)
        for capability in SageCapability
    ]
    return {
        "snapshot": snapshot.model_dump(mode="json"),
        "policies": [value.model_dump(mode="json") for value in policies],
    }


@router.get("/policies")
async def list_policies(request: Request) -> dict[str, Any]:
    runtime, principal = await _context(request)
    persisted = await runtime.store.list_capability_policies(
        principal,
        limit=1000,
    )
    values = {value.policy_id: value for value in persisted}
    for capability in SageCapability:
        default = await runtime.control.resolve(principal, capability)
        values.setdefault(default.policy_id, default)
    return {"items": [value.model_dump(mode="json") for value in values.values()]}


@router.put("/policies/{capability}")
async def update_policy(
    capability: SageCapability,
    body: PolicyUpdate,
    request: Request,
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    try:
        policy = await runtime.control.set_policy(
            principal,
            capability=capability,
            mode=body.mode,
            scope=body.scope,
            max_auto_risk=body.max_auto_risk,
            settings=body.settings,
        )
    except Exception as exc:  # domain-to-HTTP boundary
        _raise_domain(exc)
    return policy.model_dump(mode="json")


@router.get("/items")
async def list_items(
    request: Request,
    state: ItemState | None = None,
    kind: ItemKind | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_items(
        principal,
        states=(state,) if state else None,
        kinds=(kind,) if kind else None,
        limit=min(offset + limit + 1, 1000),
    )
    return _page([_item_view(value, principal) for value in values], offset, limit)


@router.get("/receipts")
async def list_receipts(
    request: Request,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    traces = await runtime.store.list_traces(principal, limit=1000)
    receipts = [
        trace.payload["receipt"]
        for trace in reversed(traces)
        if trace.trace_type is TraceType.RECALL
        and isinstance(trace.payload.get("receipt"), dict)
    ]
    return _page(receipts, offset, limit)


@router.get("/signals")
async def list_signals(
    request: Request,
    source_id: UUID | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_knowledge_signals(
        principal,
        source_id=source_id,
        limit=min(offset + limit + 1, 1000),
    )
    return _page([value.model_dump(mode="json") for value in values], offset, limit)


@router.post("/feedback")
async def record_feedback(body: FeedbackRequest, request: Request) -> dict[str, Any]:
    runtime, principal = await _context(request)
    try:
        trace = await runtime.feedback(
            principal,
            receipt_id=body.receipt_id,
            verdict=body.verdict,
            source_id=body.source_id,
            comment=body.comment,
        )
    except Exception as exc:
        _raise_domain(exc)
    return trace.model_dump(mode="json")


@router.get("/jobs")
async def list_jobs(
    request: Request,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_growth_jobs(
        principal,
        limit=min(offset + limit + 1, 1000),
    )
    return _page([value.model_dump(mode="json") for value in values], offset, limit)


@router.get("/runs")
async def list_runs(
    request: Request,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_consolidation_runs(
        principal,
        limit=min(offset + limit + 1, 1000),
    )
    return _page([value.model_dump(mode="json") for value in values], offset, limit)


@router.get("/candidates")
async def list_candidates(
    request: Request,
    state: CandidateState | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_consolidation_candidates(
        principal,
        states=(state,) if state else None,
        limit=min(offset + limit + 1, 1000),
    )
    return _page(
        [_candidate_view(value, principal) for value in values],
        offset,
        limit,
    )


@router.get("/cases")
async def list_cases(
    request: Request,
    state: CaseState | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_cases(
        principal,
        states=(state,) if state else None,
        limit=min(offset + limit + 1, 1000),
    )
    return _page(
        [value.model_dump(mode="json") for value in values],
        offset,
        limit,
    )


@router.post("/cases/{case_id}/review")
async def review_case(
    case_id: UUID,
    body: CaseReviewRequest,
    request: Request,
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    from ...sage.policy import ScopePolicy

    try:
        ScopePolicy.require_permission(principal, "sage.insight.approve")
        case = await runtime.store.get_case(principal, case_id)
        if case is None:
            from ...sage.errors import SageNotFound

            raise SageNotFound(f"SAGE case not found: {case_id}")
        summary = body.decision_summary.strip() or await _case_lesson(
            runtime,
            principal,
            case,
        )
        finished, insight = await runtime.review_pending_case(
            principal,
            case_id,
            outcome=body.outcome,
            decision_summary=summary,
            outcome_metrics=body.outcome_metrics,
        )
    except Exception as exc:
        _raise_domain(exc)
    return {
        "case": finished.model_dump(mode="json"),
        "insight": insight.model_dump(mode="json") if insight else None,
    }


@router.get("/insights")
async def list_insights(
    request: Request,
    state: InsightState | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_insights(
        principal,
        states=(state,) if state else None,
        limit=min(offset + limit + 1, 1000),
    )
    return _page(
        [value.model_dump(mode="json") for value in values],
        offset,
        limit,
    )


@router.put("/insights/{insight_id}")
async def revise_insight(
    insight_id: UUID,
    body: InsightRevisionRequest,
    request: Request,
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    from ...sage.policy import ScopePolicy

    try:
        ScopePolicy.require_permission(principal, "sage.insight.approve")
        insight = await runtime.growth.revise(
            principal,
            insight_id,
            title=body.title,
            content=body.content,
            applicability=body.applicability,
        )
    except Exception as exc:
        _raise_domain(exc)
    return insight.model_dump(mode="json")


@router.post("/items/{item_id}/{action}")
async def item_action(item_id: UUID, action: str, request: Request) -> dict[str, Any]:
    runtime, principal = await _context(request)
    from ...sage.policy import ScopePolicy

    operations = {
        "archive": runtime.catalog.archive_item,
        "dispute": runtime.catalog.dispute_item,
    }
    operation = operations.get(action)
    if operation is None:
        raise HTTPException(status_code=404, detail="Unknown knowledge action")
    try:
        ScopePolicy.require_permission(principal, "sage.insight.approve")
        item = await operation(principal, item_id)
    except Exception as exc:
        _raise_domain(exc)
    return _item_view(item, principal)


@router.get("/playbooks")
async def list_playbooks(
    request: Request,
    state: PlaybookState | None = None,
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    values = await runtime.store.list_playbooks(
        principal,
        states=(state,) if state else None,
        limit=min(offset + limit + 1, 1000),
    )
    return _page(
        [value.model_dump(mode="json") for value in values],
        offset,
        limit,
    )


@router.post("/insights/{insight_id}/{action}")
async def insight_action(
    insight_id: UUID,
    action: str,
    request: Request,
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    operations = {
        "validate": runtime.growth.start_validation,
        "approve": runtime.growth.approve,
        "reject": runtime.growth.reject,
        "activate": runtime.growth.activate,
        "rollback": runtime.growth.rollback,
    }
    operation = operations.get(action)
    if operation is None:
        raise HTTPException(status_code=404, detail="Unknown insight action")
    try:
        insight = await operation(principal, insight_id)
    except Exception as exc:
        _raise_domain(exc)
    return insight.model_dump(mode="json")


@router.post("/candidates/{candidate_id}/{action}")
async def candidate_action(
    candidate_id: UUID,
    action: str,
    request: Request,
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    operations = {
        "approve": runtime.consolidation.approve,
        "reject": runtime.consolidation.reject,
        "apply": runtime.consolidation.apply,
        "rollback": runtime.consolidation.rollback,
    }
    operation = operations.get(action)
    if operation is None:
        raise HTTPException(status_code=404, detail="Unknown candidate action")
    try:
        candidate = await operation(principal, candidate_id)
    except Exception as exc:  # domain-to-HTTP boundary
        _raise_domain(exc)
    return _candidate_view(candidate, principal)


@router.post("/maintenance")
async def schedule_maintenance(
    body: MaintenanceRequest,
    request: Request,
) -> dict[str, Any]:
    runtime, principal = await _context(request)
    jobs = await runtime.schedule_maintenance(
        principal,
        local_date=body.local_date,
    )
    return {"items": [job.model_dump(mode="json") for job in jobs]}


@router.get("/evaluations")
async def evaluation_snapshots(request: Request) -> dict[str, Any]:
    runtime, principal = await _context(request)
    snapshot = await runtime.metrics.snapshot(principal)
    return {"items": [snapshot.model_dump(mode="json")]}


__all__ = ["router"]
