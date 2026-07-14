"""Administration API for the Minions 2.1 enterprise control plane."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ...tenancy.errors import (
    AccessDenied,
    AuthenticationFailed,
    Conflict,
    QuotaExceeded,
    ResourceNotFound,
)
from ...tenancy.factory import get_tenancy_service
from ...tenancy.models import MembershipStatus, TenantPrincipal, TenantRole
from ..auth import resolve_client_ip
from ..rate_limiter import rate_limiter

router = APIRouter(prefix="/tenancy", tags=["tenancy"])


class InviteMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    role: TenantRole = TenantRole.MEMBER
    expires_hours: int = Field(default=72, ge=1, le=24 * 30)


class AcceptInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invite_token: str = Field(min_length=20, max_length=512)
    username: str
    password: str = Field(min_length=8, max_length=1024)
    display_name: str | None = Field(default=None, max_length=128)


class UpdateMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: TenantRole | None = None
    status: MembershipStatus | None = None


class CreateSpaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=63)


def _principal(request: Request) -> TenantPrincipal:
    value = getattr(request.state, "tenant_principal", None)
    if isinstance(value, TenantPrincipal):
        return value
    raise HTTPException(status_code=401, detail="Trusted tenant identity required")


def _raise_domain(exc: Exception) -> None:
    if isinstance(exc, AuthenticationFailed):
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if isinstance(exc, AccessDenied):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ResourceNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (Conflict, QuotaExceeded)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get("/overview")
async def overview(request: Request) -> dict:
    try:
        value = get_tenancy_service().overview(_principal(request))
    except Exception as exc:
        _raise_domain(exc)
    return value.model_dump(mode="json")


def _session_response(token: str, principal: TenantPrincipal) -> dict:
    return {
        "token": token,
        "username": principal.username,
        "tenant_id": str(principal.tenant_id),
        "role": principal.role.value,
        "permissions": sorted(principal.permissions),
    }


@router.get("/spaces")
async def list_spaces(request: Request) -> dict:
    try:
        values = get_tenancy_service().list_spaces(_principal(request))
    except Exception as exc:
        _raise_domain(exc)
    return {"items": values}


@router.post("/spaces", status_code=201)
async def create_space(body: CreateSpaceRequest, request: Request) -> dict:
    try:
        token, principal = get_tenancy_service().create_space(
            _principal(request),
            tenant_name=body.name,
            tenant_slug=body.slug,
        )
    except Exception as exc:
        _raise_domain(exc)
    return _session_response(token, principal)


@router.post("/spaces/{tenant_slug}/switch")
async def switch_space(tenant_slug: str, request: Request) -> dict:
    try:
        token, principal = get_tenancy_service().switch_space(
            _principal(request),
            tenant_slug=tenant_slug,
        )
    except Exception as exc:
        _raise_domain(exc)
    return _session_response(token, principal)


@router.get("/members")
async def list_members(request: Request) -> dict:
    try:
        values = get_tenancy_service().list_members(_principal(request))
    except Exception as exc:
        _raise_domain(exc)
    return {"items": values}


@router.patch("/members/{user_id}")
async def update_member(
    user_id: UUID,
    body: UpdateMemberRequest,
    request: Request,
) -> dict:
    try:
        value = get_tenancy_service().update_member(
            _principal(request),
            user_id=user_id,
            role=body.role,
            status=body.status,
        )
    except Exception as exc:
        _raise_domain(exc)
    return value.model_dump(mode="json")


@router.post("/invites", status_code=201)
async def invite_member(body: InviteMemberRequest, request: Request) -> dict:
    try:
        invite, token = get_tenancy_service().invite_member(
            _principal(request),
            username=body.username,
            role=body.role,
            expires_hours=body.expires_hours,
        )
    except Exception as exc:
        _raise_domain(exc)
    value = invite.model_dump(mode="json")
    value.pop("token_hash", None)
    value["invite_token"] = token
    return value


@router.get("/invites")
async def list_invites(request: Request) -> dict:
    principal = _principal(request)
    service = get_tenancy_service()
    try:
        service.require(principal, "member.read")
        values = service.store.list_invites(
            principal.tenant_id,
            datetime.now(timezone.utc),
        )
    except Exception as exc:
        _raise_domain(exc)
    items = []
    for value in values:
        item = value.model_dump(mode="json")
        item.pop("token_hash", None)
        items.append(item)
    return {"items": items}


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: UUID, request: Request) -> dict:
    try:
        get_tenancy_service().revoke_invite(
            _principal(request),
            invite_id=invite_id,
        )
    except Exception as exc:
        _raise_domain(exc)
    return {"success": True}


@router.post("/invites/accept")
async def accept_invite(body: AcceptInviteRequest, request: Request) -> dict:
    client_ip = resolve_client_ip(request)
    if rate_limiter.is_user_locked(body.username) or rate_limiter.is_ip_locked(
        client_ip,
    ):
        raise HTTPException(status_code=423, detail="Too many attempts")
    if rate_limiter.is_ip_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    try:
        token, principal = get_tenancy_service().accept_invite(
            invite_token=body.invite_token,
            username=body.username,
            password=body.password,
            display_name=body.display_name,
        )
    except Exception as exc:
        rate_limiter.record_login_attempt(client_ip, body.username, success=False)
        _raise_domain(exc)
    rate_limiter.record_login_attempt(client_ip, body.username, success=True)
    return _session_response(token, principal)


@router.get("/agents")
async def list_agent_grants(request: Request) -> dict:
    try:
        values = get_tenancy_service().list_agent_grants(_principal(request))
    except Exception as exc:
        _raise_domain(exc)
    return {"items": [value.model_dump(mode="json") for value in values]}


@router.get("/audit")
async def list_audit(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    before: datetime | None = None,
) -> dict:
    try:
        values = get_tenancy_service().list_audit(
            _principal(request),
            limit=limit,
            before=before,
        )
    except Exception as exc:
        _raise_domain(exc)
    return {"items": [value.model_dump(mode="json") for value in values]}


__all__ = ["router"]
