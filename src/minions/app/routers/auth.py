# -*- coding: utf-8 -*-
"""Authentication API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..auth import (
    authenticate,
    has_registered_users,
    is_auth_enabled,
    is_tenancy_auth_enabled,
    register_user,
    revoke_all_tokens,
    revoke_token,
    update_credentials,
    verify_token,
    resolve_client_ip,
)
from ..rate_limiter import rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_slug: str | None = None
    expires_in: int | None = (
        None  # Token expiry in seconds, -1/0 for permanent
    )


class LoginResponse(BaseModel):
    token: str
    username: str
    tenant_id: str | None = None
    tenant_slug: str | None = None
    role: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RegisterRequest(BaseModel):
    username: str
    password: str
    tenant_name: str = "默认企业空间"
    tenant_slug: str = "default"
    display_name: str | None = None
    expires_in: int | None = (
        None  # Token expiry in seconds, -1/0 for permanent
    )


class AuthStatusResponse(BaseModel):
    enabled: bool
    has_users: bool
    multitenant: bool = False


@router.post("/login")
async def login(request: Request, req: LoginRequest):
    """Authenticate with username and password.

    Optional `expires_in` field:
    - Positive integer: token expires in N seconds
    - 0 or -1: permanent token (100 years)
    - None/omitted: default 7 days
    """
    if not is_auth_enabled():
        return LoginResponse(token="", username="")

    # Get client IP for rate limiting
    client_ip = resolve_client_ip(request)

    # Check if user account is locked
    if rate_limiter.is_user_locked(req.username):
        raise HTTPException(
            status_code=423,
            detail="Account temporarily locked. Please try again later",
        )

    # Check if IP is locked or rate-limited
    if rate_limiter.is_ip_locked(client_ip):
        raise HTTPException(
            status_code=423,
            detail="Too many login attempts. Please try again later",
        )

    if rate_limiter.is_ip_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down",
        )

    # Attempt authentication
    principal = None
    if is_tenancy_auth_enabled():
        from ...tenancy.errors import (
            AmbiguousTenant,
            AuthenticationFailed,
        )
        from ...tenancy.factory import get_tenancy_service

        try:
            token, principal = get_tenancy_service().login(
                username=req.username,
                password=req.password,
                tenant_slug=req.tenant_slug,
            )
        except AmbiguousTenant as exc:
            raise HTTPException(
                status_code=409,
                detail="请选择要进入的企业空间",
            ) from exc
        except AuthenticationFailed:
            token = None
    else:
        token = authenticate(req.username, req.password, req.expires_in)
    if token is None:
        # Record failed attempt
        rate_limiter.record_login_attempt(
            client_ip,
            req.username,
            success=False,
        )
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )

    # Record successful attempt
    rate_limiter.record_login_attempt(client_ip, req.username, success=True)

    return LoginResponse(
        token=token,
        username=req.username,
        tenant_id=str(principal.tenant_id) if principal else None,
        tenant_slug=req.tenant_slug if principal else None,
        role=principal.role.value if principal else None,
        permissions=sorted(principal.permissions) if principal else [],
    )


@router.post("/register")
async def register(req: RegisterRequest):
    """Register the single user account (only allowed once).

    Optional `expires_in` field:
    - Positive integer: token expires in N seconds
    - 0 or -1: permanent token (100 years)
    - None/omitted: default 7 days
    """
    if not is_auth_enabled():
        raise HTTPException(
            status_code=403,
            detail="Authentication is not enabled",
        )

    if is_tenancy_auth_enabled():
        from ...tenancy.errors import Conflict
        from ...tenancy.factory import get_tenancy_service

        service = get_tenancy_service()
        if service.has_login_users():
            raise HTTPException(
                status_code=403,
                detail="企业空间已完成初始化",
            )
        try:
            token, principal = service.bootstrap_owner(
                username=req.username.strip(),
                password=req.password,
                tenant_name=req.tenant_name,
                tenant_slug=req.tenant_slug,
                display_name=req.display_name,
            )
        except (Conflict, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        from ...tenancy.migration import import_configured_agents

        import_configured_agents(service, principal)
        return LoginResponse(
            token=token,
            username=principal.username,
            tenant_id=str(principal.tenant_id),
            tenant_slug=req.tenant_slug,
            role=principal.role.value,
            permissions=sorted(principal.permissions),
        )

    if has_registered_users():
        raise HTTPException(
            status_code=403,
            detail="User already registered",
        )

    if not req.username.strip() or not req.password.strip():
        raise HTTPException(
            status_code=400,
            detail="Username and password are required",
        )

    token = register_user(req.username.strip(), req.password, req.expires_in)
    if token is None:
        raise HTTPException(
            status_code=409,
            detail="Registration failed",
        )

    return LoginResponse(token=token, username=req.username.strip())


@router.get("/status")
async def auth_status():
    """Check if authentication is enabled and whether a user exists."""
    multitenant = is_tenancy_auth_enabled()
    if multitenant:
        from ...tenancy.factory import get_tenancy_service

        has_users = get_tenancy_service().has_login_users()
    else:
        has_users = has_registered_users()
    return AuthStatusResponse(
        enabled=is_auth_enabled(),
        has_users=has_users,
        multitenant=multitenant,
    )


@router.post("/tenant-options")
async def tenant_options(req: LoginRequest, request: Request):
    """List selectable spaces only after validating the supplied password."""
    if not is_tenancy_auth_enabled():
        return {"items": []}
    from ...tenancy.errors import AuthenticationFailed
    from ...tenancy.factory import get_tenancy_service

    client_ip = resolve_client_ip(request)
    if rate_limiter.is_user_locked(req.username) or rate_limiter.is_ip_locked(
        client_ip,
    ):
        raise HTTPException(status_code=423, detail="Too many login attempts")
    if rate_limiter.is_ip_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")
    try:
        values = get_tenancy_service().list_login_tenants(
            req.username,
            req.password,
        )
    except AuthenticationFailed as exc:
        rate_limiter.record_login_attempt(client_ip, req.username, success=False)
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        ) from exc
    rate_limiter.record_login_attempt(client_ip, req.username, success=True)
    return {"items": values}


@router.get("/verify")
async def verify(request: Request):
    """Verify that the caller's Bearer token is still valid."""
    if not is_auth_enabled():
        return {"valid": True, "username": ""}

    if is_tenancy_auth_enabled():
        principal = getattr(request.state, "tenant_principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {
            "valid": True,
            "username": principal.username,
            "tenant_id": str(principal.tenant_id),
            "role": principal.role.value,
            "permissions": sorted(principal.permissions),
        }

    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")

    username = verify_token(token)
    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )

    return {"valid": True, "username": username}


class UpdateProfileRequest(BaseModel):
    current_password: str
    new_username: str | None = None
    new_password: str | None = None
    expires_in: int | None = (
        None  # Token expiry in seconds, -1/0 for permanent
    )


@router.post("/update-profile")
async def update_profile(req: UpdateProfileRequest, request: Request):
    """Update username and/or password for the authenticated user."""
    if not is_auth_enabled():
        raise HTTPException(
            status_code=403,
            detail="Authentication is not enabled",
        )

    if is_tenancy_auth_enabled():
        from ...tenancy.errors import AuthenticationFailed, Conflict
        from ...tenancy.factory import get_tenancy_service

        principal = getattr(request.state, "tenant_principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if not req.new_username and not req.new_password:
            raise HTTPException(status_code=400, detail="Nothing to update")
        try:
            token, updated = get_tenancy_service().update_profile(
                principal,
                current_password=req.current_password,
                new_username=req.new_username,
                new_password=req.new_password,
            )
        except AuthenticationFailed as exc:
            raise HTTPException(
                status_code=401,
                detail="Current password is incorrect",
            ) from exc
        except Conflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return LoginResponse(
            token=token,
            username=updated.username,
            tenant_id=str(updated.tenant_id),
            role=updated.role.value,
            permissions=sorted(updated.permissions),
        )

    if not has_registered_users():
        raise HTTPException(
            status_code=403,
            detail="No user registered",
        )

    # Verify caller is authenticated
    auth_header = request.headers.get("Authorization", "")
    caller_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    if not caller_token or verify_token(caller_token) is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not req.new_username and not req.new_password:
        raise HTTPException(
            status_code=400,
            detail="Nothing to update",
        )

    if req.new_username is not None and not req.new_username.strip():
        raise HTTPException(
            status_code=400,
            detail="Username cannot be empty",
        )

    if req.new_password is not None and not req.new_password.strip():
        raise HTTPException(
            status_code=400,
            detail="Password cannot be empty",
        )

    token = update_credentials(
        current_password=req.current_password,
        new_username=req.new_username,
        new_password=req.new_password,
        expiry_seconds=req.expires_in,
    )
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Current password is incorrect",
        )

    username = req.new_username.strip() if req.new_username else ""
    return LoginResponse(token=token, username=username)


class RevokeTokenRequest(BaseModel):
    token: str | None = (
        None  # Optional: revoke specific token, or current if omitted
    )


@router.post("/revoke-token")
async def revoke_single_token(req: RevokeTokenRequest, request: Request):
    """Revoke a single token by adding it to the blacklist.

    If `token` is provided in the request body, revokes that token.
    If `token` is omitted, revokes the token used for authentication
    (current token).

    This allows you to:
    - Revoke a leaked token from another device
    - Logout from the current session
    """
    if not is_auth_enabled():
        raise HTTPException(
            status_code=403,
            detail="Authentication is not enabled",
        )

    if is_tenancy_auth_enabled():
        from ...tenancy.factory import get_tenancy_service

        principal = getattr(request.state, "tenant_principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if req.token:
            raise HTTPException(
                status_code=400,
                detail="只能退出当前会话；其他成员会话请通过成员停用撤销",
            )
        get_tenancy_service().logout(principal)
        return {
            "message": "Current token has been revoked. Please login again.",
            "revoked": True,
            "revoked_current_token": True,
        }

    # Get current token for authentication
    auth_header = request.headers.get("Authorization", "")
    caller_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    if not caller_token or verify_token(caller_token) is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Determine which token to revoke
    token_to_revoke = req.token if req.token else caller_token
    is_current_token = token_to_revoke == caller_token

    success = revoke_token(token_to_revoke)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke token",
        )

    message = (
        "Current token has been revoked. Please login again."
        if is_current_token
        else "Specified token has been revoked."
    )

    return {
        "message": message,
        "revoked": True,
        "revoked_current_token": is_current_token,
    }


@router.post("/revoke-all-tokens")
async def revoke_all_sessions(request: Request):
    """Revoke all existing tokens by rotating the JWT secret.

    This endpoint requires authentication. After calling this endpoint,
    all previously issued tokens will be invalidated, and you will need
    to login again to get a new token.

    This is more efficient than revoking tokens individually when you
    want to invalidate all sessions (e.g., password reset, security incident).
    """
    if not is_auth_enabled():
        raise HTTPException(
            status_code=403,
            detail="Authentication is not enabled",
        )

    if is_tenancy_auth_enabled():
        from ...tenancy.factory import get_tenancy_service

        principal = getattr(request.state, "tenant_principal", None)
        if principal is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        count = get_tenancy_service().revoke_all_user_sessions(principal)
        return {
            "message": "All sessions have been revoked. Please login again.",
            "revoked": True,
            "count": count,
        }

    # Verify caller is authenticated
    auth_header = request.headers.get("Authorization", "")
    caller_token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    if not caller_token or verify_token(caller_token) is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    success = revoke_all_tokens()
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke tokens",
        )

    return {
        "message": "All tokens have been revoked. Please login again.",
        "revoked": True,
    }
