"""Tenant-safe domain operations and authentication orchestration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from ..constant import SECRET_DIR
from .errors import (
    AccessDenied,
    AmbiguousTenant,
    AuthenticationFailed,
    Conflict,
    QuotaExceeded,
    ResourceNotFound,
)
from .models import (
    AgentAccess,
    AgentGrant,
    AgentStatus,
    AuthSession,
    InviteStatus,
    MembershipStatus,
    TenantAuditEvent,
    TenantInvite,
    TenantMembership,
    TenantOverview,
    TenantPrincipal,
    TenantRole,
)
from .permissions import (
    AGENT_CREATE,
    AGENT_DELETE,
    AGENT_MANAGE,
    AGENT_READ,
    AGENT_USE,
    AUDIT_READ,
    MEMBER_INVITE,
    MEMBER_MANAGE,
    MEMBER_READ,
    TENANT_MANAGE,
    permissions_for,
)
from .store import TenancyStore


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
TOKEN_VERSION = 1
TOKEN_ISSUER = "minions-tenancy"
TASK_LEASE_TTL_SECONDS = 10 * 60
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_USERNAME_RE = re.compile(r"^[^\s]{2,128}$")
_AUDIT_SECRET_MARKERS = ("password", "token", "secret", "credential")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _sanitize_audit_value(value: Any, *, depth: int = 0) -> Any:
    """Bound audit values and remove sensitive keys at every nesting level."""
    if depth >= 6:
        return "[depth-limited]"
    if isinstance(value, dict):
        return {
            str(key)[:64]: _sanitize_audit_value(item, depth=depth + 1)
            for key, item in list(value.items())[:100]
            if not any(
                marker in str(key).casefold() for marker in _AUDIT_SECRET_MARKERS
            )
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            _sanitize_audit_value(item, depth=depth + 1) for item in list(value)[:100]
        ]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2_048]


class TenancyService:
    """Authoritative domain facade used by HTTP and background runtimes."""

    def __init__(self, *, store: TenancyStore, settings: Any):
        self.store = store
        self.settings = settings
        self._signing_key = self._load_or_create_signing_key()
        self._storage_cache: dict[UUID, tuple[float, int]] = {}

    def close(self) -> None:
        self.store.close()

    @staticmethod
    def _signing_key_path() -> Path:
        override = os.environ.get("MINIONS_TENANCY_SIGNING_KEY_FILE", "")
        return Path(override).expanduser() if override else SECRET_DIR / "tenancy.key"

    def _load_or_create_signing_key(self) -> bytes:
        path = self._signing_key_path()
        if path.exists():
            raw = path.read_bytes().strip()
            if len(raw) < 32:
                raise RuntimeError("tenancy signing key is invalid")
            return raw
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
        raw = secrets.token_bytes(48)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, raw)
        finally:
            os.close(fd)
        return raw

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        if len(password) < 8 or len(password) > 1024:
            raise ValueError("password must contain 8-1024 characters")
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            PASSWORD_ITERATIONS,
        ).hex()
        return digest, salt

    @staticmethod
    def verify_password(password: str, row: dict[str, Any]) -> bool:
        algorithm = str(row.get("password_algorithm") or "legacy_sha256")
        try:
            if algorithm == PASSWORD_ALGORITHM:
                iterations = int(row.get("password_iterations", 0))
                if iterations < 100_000:
                    return False
                digest = hashlib.pbkdf2_hmac(
                    "sha256",
                    password.encode("utf-8"),
                    bytes.fromhex(str(row["password_salt"])),
                    iterations,
                ).hex()
            elif algorithm == "legacy_sha256":
                digest = hashlib.sha256(
                    (str(row["password_salt"]) + password).encode("utf-8"),
                ).hexdigest()
            else:
                return False
        except (ValueError, TypeError, KeyError):
            return False
        return hmac.compare_digest(digest, str(row.get("password_hash", "")))

    def _upgrade_legacy_password(self, password: str, row: dict[str, Any]) -> None:
        if row.get("password_algorithm") == PASSWORD_ALGORITHM:
            return
        digest, salt = self.hash_password(password)
        self.store.update_user_password(
            user_id=UUID(str(row["user_id"])),
            password_hash=digest,
            password_salt=salt,
            password_algorithm=PASSWORD_ALGORITHM,
            password_iterations=PASSWORD_ITERATIONS,
            now=_now(),
        )

    def has_login_users(self) -> bool:
        return self.store.has_login_users()

    def local_principal(self, *, source: str = "local-http") -> TenantPrincipal:
        tenant, user, membership = self.store.ensure_local_identity()
        return self._principal(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            username=user.username,
            membership=membership,
            source=source,
            service_id="local-development",
        )

    def system_owner_principal(
        self,
        *,
        source: str = "internal-migration",
    ) -> TenantPrincipal | None:
        """Return the first active owner for trusted startup reconciliation."""
        row = self.store.get_first_active_owner()
        if row is None:
            return None
        membership = TenantMembership(
            tenant_id=_as_uuid(row["tenant_id"]),
            user_id=_as_uuid(row["user_id"]),
            role=TenantRole(row["role"]),
            status=MembershipStatus(row["membership_status"]),
            created_at=_now(),
            updated_at=_now(),
        )
        return self._principal(
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            username=row["username"],
            membership=membership,
            source=source,
            service_id="tenancy-reconciler",
        )

    def bootstrap_owner(
        self,
        *,
        username: str,
        password: str,
        tenant_name: str = "默认企业空间",
        tenant_slug: str = "default",
        display_name: str | None = None,
    ) -> tuple[str, TenantPrincipal]:
        if self.has_login_users():
            raise Conflict("an owner account already exists")
        username = self._validate_username(username)
        slug = self._validate_slug(tenant_slug)
        name = tenant_name.strip()
        if not name or len(name) > 128:
            raise ValueError("tenant name must contain 1-128 characters")
        digest, salt = self.hash_password(password)
        tenant, user, membership = self.store.create_tenant_owner(
            slug=slug,
            tenant_name=name,
            username=username,
            display_name=(display_name or username).strip()[:128],
            password_hash=digest,
            password_salt=salt,
            password_algorithm=PASSWORD_ALGORITHM,
            password_iterations=PASSWORD_ITERATIONS,
        )
        token, principal = self._issue_session(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            username=user.username,
            membership=membership,
            source="http",
        )
        self.audit(
            principal,
            action="tenant.bootstrap",
            resource_type="tenant",
            resource_id=str(tenant.tenant_id),
        )
        return token, principal

    def import_legacy_owner(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        username: str,
        display_name: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        tenant_name: str = "默认企业空间",
        tenant_slug: str = "default",
    ) -> TenantPrincipal:
        """Import the former single-user identity without changing its UUIDs."""
        if self.has_login_users():
            owner = self.system_owner_principal(source="legacy-auth-migration")
            if owner is None:
                raise Conflict("tenant owner already exists")
            return owner
        username = self._validate_username(username)
        slug = self._validate_slug(tenant_slug)
        if password_algorithm not in {PASSWORD_ALGORITHM, "legacy_sha256"}:
            raise ValueError("unsupported legacy password algorithm")
        tenant, user, membership = self.store.create_tenant_owner(
            tenant_id=tenant_id,
            user_id=user_id,
            slug=slug,
            tenant_name=tenant_name.strip()[:128] or "默认企业空间",
            username=username,
            display_name=display_name.strip()[:128] or username,
            password_hash=password_hash,
            password_salt=password_salt,
            password_algorithm=password_algorithm,
            password_iterations=password_iterations,
        )
        principal = self._principal(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            username=user.username,
            membership=membership,
            source="legacy-auth-migration",
            service_id="tenancy-migrator",
        )
        self.audit(
            principal,
            action="migration.auth.import",
            resource_type="membership",
            resource_id=str(user.user_id),
        )
        return principal

    def login(
        self,
        *,
        username: str,
        password: str,
        tenant_slug: str | None = None,
        source: str = "http",
    ) -> tuple[str, TenantPrincipal]:
        row = self.store.get_user_credentials(username)
        if not row or row.get("status") != "active":
            raise AuthenticationFailed("invalid username or password")
        if not self.verify_password(password, row):
            raise AuthenticationFailed("invalid username or password")
        self._upgrade_legacy_password(password, row)
        memberships = self.store.list_active_memberships(_as_uuid(row["user_id"]))
        if tenant_slug:
            slug = tenant_slug.strip().casefold()
            memberships = [
                item for item in memberships if item[0].slug.casefold() == slug
            ]
        elif len(memberships) > 1:
            raise AmbiguousTenant("tenant selection is required")
        if not memberships:
            raise AuthenticationFailed("no active tenant membership")
        tenant, membership = memberships[0]
        return self._issue_session(
            tenant_id=tenant.tenant_id,
            user_id=_as_uuid(row["user_id"]),
            username=row["username"],
            membership=membership,
            source=source,
        )

    def list_login_tenants(self, username: str, password: str) -> list[dict[str, str]]:
        """Return tenant choices only after credentials have been verified."""
        row = self.store.get_user_credentials(username)
        if not row or not self.verify_password(password, row):
            raise AuthenticationFailed("invalid username or password")
        self._upgrade_legacy_password(password, row)
        return [
            {
                "tenant_id": str(tenant.tenant_id),
                "slug": tenant.slug,
                "name": tenant.name,
            }
            for tenant, _ in self.store.list_active_memberships(
                _as_uuid(row["user_id"]),
            )
        ]

    def list_spaces(self, principal: TenantPrincipal) -> list[dict[str, Any]]:
        """List active spaces the authenticated account may enter."""
        self.require(principal, "tenant.read")
        return [
            {
                "tenant_id": str(tenant.tenant_id),
                "slug": tenant.slug,
                "name": tenant.name,
                "role": membership.role.value,
                "current": tenant.tenant_id == principal.tenant_id,
            }
            for tenant, membership in self.store.list_active_memberships(
                principal.user_id,
            )
        ]

    def create_space(
        self,
        principal: TenantPrincipal,
        *,
        tenant_name: str,
        tenant_slug: str,
    ) -> tuple[str, TenantPrincipal]:
        """Provision a new isolated enterprise owned by the current owner."""
        self.require(principal, TENANT_MANAGE)
        name = tenant_name.strip()
        if not name or len(name) > 128:
            raise ValueError("tenant name must contain 1-128 characters")
        slug = self._validate_slug(tenant_slug)
        tenant, user, membership = self.store.create_tenant_for_existing_owner(
            tenant_id=uuid4(),
            user_id=principal.user_id,
            slug=slug,
            tenant_name=name,
            now=_now(),
        )
        self.audit(
            principal,
            action="tenant.provision",
            resource_type="tenant",
            resource_id=str(tenant.tenant_id),
            metadata={"slug": tenant.slug},
        )
        token, next_principal = self._issue_session(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            username=user.username,
            membership=membership,
            source="http",
        )
        self.audit(
            next_principal,
            action="tenant.bootstrap",
            resource_type="tenant",
            resource_id=str(tenant.tenant_id),
        )
        self._revoke_previous_session(principal)
        return token, next_principal

    def switch_space(
        self,
        principal: TenantPrincipal,
        *,
        tenant_slug: str,
    ) -> tuple[str, TenantPrincipal]:
        """Mint a session for another active membership of the same account."""
        slug = self._validate_slug(tenant_slug)
        selected = next(
            (
                item
                for item in self.store.list_active_memberships(principal.user_id)
                if item[0].slug.casefold() == slug.casefold()
            ),
            None,
        )
        if selected is None:
            raise ResourceNotFound("enterprise space not found")
        tenant, membership = selected
        token, next_principal = self._issue_session(
            tenant_id=tenant.tenant_id,
            user_id=principal.user_id,
            username=principal.username,
            membership=membership,
            source="http",
        )
        self.audit(
            next_principal,
            action="tenant.switch",
            resource_type="tenant",
            resource_id=str(tenant.tenant_id),
        )
        self._revoke_previous_session(principal)
        return token, next_principal

    def _revoke_previous_session(self, principal: TenantPrincipal) -> None:
        if principal.session_id is not None:
            self.store.revoke_session(
                principal.session_id,
                principal.tenant_id,
                _now(),
            )

    def _issue_session(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        username: str,
        membership: TenantMembership,
        source: str,
    ) -> tuple[str, TenantPrincipal]:
        now = _now()
        expires = now + timedelta(seconds=self.settings.token_ttl_seconds)
        session_id = uuid4()
        token_id = secrets.token_hex(12)
        payload = {
            "ver": TOKEN_VERSION,
            "iss": TOKEN_ISSUER,
            "sid": str(session_id),
            "tid": str(tenant_id),
            "uid": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
            "jti": token_id,
            "nonce": secrets.token_hex(16),
        }
        body = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
        signature = hmac.new(
            self._signing_key, body.encode(), hashlib.sha256
        ).hexdigest()
        token = f"{body}.{signature}"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.store.create_session(
            AuthSession(
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires,
                created_at=now,
                last_seen_at=now,
            ),
        )
        principal = self._principal(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            membership=membership,
            source=source,
            session_id=session_id,
            token_id=token_id,
        )
        return token, principal

    def verify_token(self, token: str, *, source: str = "http") -> TenantPrincipal:
        try:
            body, signature = token.split(".", 1)
            expected = hmac.new(
                self._signing_key, body.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise AuthenticationFailed("invalid or expired token")
            payload = json.loads(_b64_decode(body))
            if (
                payload.get("ver") != TOKEN_VERSION
                or payload.get("iss") != TOKEN_ISSUER
                or int(payload.get("exp", 0)) <= int(_now().timestamp())
            ):
                raise AuthenticationFailed("invalid or expired token")
            session_id = UUID(payload["sid"])
            tenant_id = UUID(payload["tid"])
            user_id = UUID(payload["uid"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise AuthenticationFailed("invalid or expired token") from exc
        row = self.store.resolve_session(
            hashlib.sha256(token.encode()).hexdigest(),
            _now(),
            tenant_id,
        )
        if row is None:
            raise AuthenticationFailed("invalid or expired token")
        if (
            _as_uuid(row["session_id"]) != session_id
            or _as_uuid(row["tenant_id"]) != tenant_id
            or _as_uuid(row["user_id"]) != user_id
        ):
            raise AuthenticationFailed("invalid or expired token")
        membership = TenantMembership(
            tenant_id=tenant_id,
            user_id=user_id,
            role=TenantRole(row["role"]),
            status=MembershipStatus(row["membership_status"]),
            created_at=_now(),
            updated_at=_now(),
        )
        self.store.touch_session(session_id, tenant_id, _now())
        return self._principal(
            tenant_id=tenant_id,
            user_id=user_id,
            username=row["username"],
            membership=membership,
            source=source,
            session_id=session_id,
            token_id=str(payload.get("jti") or ""),
        )

    def logout(self, principal: TenantPrincipal) -> bool:
        if principal.session_id is None:
            return False
        result = self.store.revoke_session(
            principal.session_id,
            principal.tenant_id,
            _now(),
        )
        if result:
            self.audit(
                principal,
                action="session.revoke",
                resource_type="session",
                resource_id=str(principal.session_id),
            )
        return result

    def update_profile(
        self,
        principal: TenantPrincipal,
        *,
        current_password: str,
        new_username: str | None = None,
        new_password: str | None = None,
    ) -> tuple[str, TenantPrincipal]:
        row = self.store.get_user_credentials(principal.username)
        if row is None or UUID(str(row["user_id"])) != principal.user_id:
            raise AuthenticationFailed("current password is incorrect")
        if not self.verify_password(current_password, row):
            raise AuthenticationFailed("current password is incorrect")
        username = (
            self._validate_username(new_username)
            if new_username is not None
            else principal.username
        )
        if new_password is not None:
            digest, salt = self.hash_password(new_password)
        elif row.get("password_algorithm") != PASSWORD_ALGORITHM:
            digest, salt = self.hash_password(current_password)
        else:
            digest, salt = str(row["password_hash"]), str(row["password_salt"])
        now = _now()
        self.store.update_user_profile(
            user_id=principal.user_id,
            username=username,
            password_hash=digest,
            password_salt=salt,
            password_algorithm=PASSWORD_ALGORITHM,
            password_iterations=PASSWORD_ITERATIONS,
            now=now,
        )
        self._revoke_sessions_in_all_spaces(principal.user_id, now)
        membership = TenantMembership(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            role=principal.role,
            status=MembershipStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        token, updated = self._issue_session(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            username=username,
            membership=membership,
            source="http",
        )
        self.audit(
            updated,
            action="user.profile.update",
            resource_type="user",
            resource_id=str(principal.user_id),
        )
        return token, updated

    def revoke_all_user_sessions(self, principal: TenantPrincipal) -> int:
        count = self._revoke_sessions_in_all_spaces(principal.user_id, _now())
        self.audit(
            principal,
            action="session.revoke_all",
            resource_type="user",
            resource_id=str(principal.user_id),
            metadata={"count": count},
        )
        return count

    def _revoke_sessions_in_all_spaces(
        self,
        user_id: UUID,
        now: datetime,
    ) -> int:
        """Revoke a global account's sessions through each tenant RLS scope."""
        return sum(
            self.store.revoke_user_sessions(tenant.tenant_id, user_id, now)
            for tenant, _ in self.store.list_active_memberships(user_id)
        )

    @staticmethod
    def _principal(
        *,
        tenant_id: UUID,
        user_id: UUID,
        username: str,
        membership: TenantMembership,
        source: str,
        session_id: UUID | None = None,
        service_id: str | None = None,
        token_id: str | None = None,
    ) -> TenantPrincipal:
        return TenantPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            username=username,
            role=membership.role,
            permissions=permissions_for(membership.role),
            source=source[:64],
            session_id=session_id,
            service_id=service_id,
            token_id=token_id,
        )

    @staticmethod
    def require(principal: TenantPrincipal, permission: str) -> None:
        if not principal.has(permission):
            raise AccessDenied(f"permission required: {permission}")

    def overview(self, principal: TenantPrincipal) -> TenantOverview:
        self.require(principal, "tenant.read")
        self.refresh_storage_usage(principal)
        tenant = self.store.get_tenant(principal.tenant_id)
        if tenant is None:
            raise ResourceNotFound("tenant not found")
        membership = next(
            (
                membership
                for item_tenant, membership in self.store.list_active_memberships(
                    principal.user_id,
                )
                if item_tenant.tenant_id == principal.tenant_id
            ),
            None,
        )
        if membership is None:
            raise ResourceNotFound("tenant membership not found")
        return TenantOverview(
            tenant=tenant,
            membership=membership,
            quota=self.store.get_quota(principal.tenant_id),
            usage=self.store.get_usage(principal.tenant_id),
            permissions=tuple(sorted(principal.permissions)),
        )

    def list_members(self, principal: TenantPrincipal) -> list[dict[str, Any]]:
        self.require(principal, MEMBER_READ)
        rows = self.store.list_members(principal.tenant_id)
        return [
            {
                "tenant_id": row["tenant_id"],
                "user_id": row["user_id"],
                "username": row["username"],
                "display_name": row["display_name"],
                "role": row["role"],
                "status": row["status"],
                "user_status": row["user_status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def update_member(
        self,
        principal: TenantPrincipal,
        *,
        user_id: UUID,
        role: TenantRole | None = None,
        status: MembershipStatus | None = None,
    ) -> TenantMembership:
        self.require(principal, MEMBER_MANAGE)
        if user_id == principal.user_id and status is MembershipStatus.DISABLED:
            raise Conflict("cannot disable the current account")
        target = next(
            (
                row
                for row in self.store.list_members(principal.tenant_id)
                if UUID(str(row["user_id"])) == user_id
            ),
            None,
        )
        if target is None:
            raise ResourceNotFound("member not found")
        if (
            TenantRole(target["role"]) is TenantRole.OWNER
            and principal.role is not TenantRole.OWNER
        ):
            raise AccessDenied("only an owner can manage another owner")
        if principal.role is not TenantRole.OWNER and role is TenantRole.OWNER:
            raise AccessDenied("only an owner can assign owner role")
        value = self.store.update_membership(
            tenant_id=principal.tenant_id,
            user_id=user_id,
            role=role,
            status=status,
            now=_now(),
        )
        if status is MembershipStatus.DISABLED:
            self.store.revoke_user_sessions(principal.tenant_id, user_id, _now())
        self.audit(
            principal,
            action="member.update",
            resource_type="membership",
            resource_id=str(user_id),
            metadata={"role": value.role.value, "status": value.status.value},
        )
        return value

    def invite_member(
        self,
        principal: TenantPrincipal,
        *,
        username: str,
        role: TenantRole,
        expires_hours: int = 72,
    ) -> tuple[TenantInvite, str]:
        self.require(principal, MEMBER_INVITE)
        if role is TenantRole.OWNER:
            raise AccessDenied("owner role cannot be assigned by invite")
        username = self._validate_username(username)
        if any(
            str(row["username"]).casefold() == username.casefold()
            for row in self.store.list_members(principal.tenant_id)
        ):
            raise Conflict("user is already a tenant member")
        now = _now()
        if not 1 <= expires_hours <= 24 * 30:
            raise ValueError("invite expiry must be between 1 hour and 30 days")
        raw_token = secrets.token_urlsafe(32)
        invite = TenantInvite(
            invite_id=uuid4(),
            tenant_id=principal.tenant_id,
            username=username,
            role=role,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            status=InviteStatus.PENDING,
            expires_at=now + timedelta(hours=expires_hours),
            created_by=principal.user_id,
            created_at=now,
        )
        self.store.create_invite(invite)
        self.audit(
            principal,
            action="member.invite",
            resource_type="invite",
            resource_id=str(invite.invite_id),
            metadata={"username": username, "role": role.value},
        )
        return invite, raw_token

    def accept_invite(
        self,
        *,
        invite_token: str,
        username: str,
        password: str,
        display_name: str | None = None,
    ) -> tuple[str, TenantPrincipal]:
        username = self._validate_username(username)
        now = _now()
        token_hash = hashlib.sha256(invite_token.encode()).hexdigest()
        invite = self.store.get_pending_invite(
            token_hash=token_hash,
            now=now,
        )
        if invite is None or invite.username.casefold() != username.casefold():
            raise ResourceNotFound("invite is invalid or expired")
        existing = self.store.get_user_credentials(username)
        if existing is not None:
            if existing.get("status") != "active" or not self.verify_password(
                password,
                existing,
            ):
                raise AuthenticationFailed("invalid invite or account password")
        digest, salt = self.hash_password(password)
        tenant, user, membership = self.store.accept_invite(
            token_hash=token_hash,
            username=username,
            display_name=(display_name or username).strip()[:128],
            password_hash=digest,
            password_salt=salt,
            password_algorithm=PASSWORD_ALGORITHM,
            password_iterations=PASSWORD_ITERATIONS,
            now=now,
        )
        token, principal = self._issue_session(
            tenant_id=tenant.tenant_id,
            user_id=user.user_id,
            username=user.username,
            membership=membership,
            source="http",
        )
        self.audit(
            principal,
            action="member.accept_invite",
            resource_type="membership",
            resource_id=str(user.user_id),
        )
        return token, principal

    def revoke_invite(
        self,
        principal: TenantPrincipal,
        *,
        invite_id: UUID,
    ) -> bool:
        self.require(principal, MEMBER_INVITE)
        revoked = self.store.revoke_invite(
            principal.tenant_id,
            invite_id,
            _now(),
        )
        if not revoked:
            raise ResourceNotFound("pending invite not found")
        self.audit(
            principal,
            action="member.invite.revoke",
            resource_type="invite",
            resource_id=str(invite_id),
        )
        return True

    def register_agent(
        self,
        principal: TenantPrincipal,
        *,
        agent_id: str,
        access: AgentAccess = AgentAccess.TENANT,
    ) -> AgentGrant:
        self.require(principal, AGENT_CREATE)
        grant = self.store.register_agent(
            agent_id=agent_id,
            tenant_id=principal.tenant_id,
            owner_user_id=principal.user_id,
            access=access,
            now=_now(),
        )
        self.audit(
            principal,
            action="agent.create",
            resource_type="agent",
            resource_id=agent_id,
        )
        return grant

    def import_agent(self, principal: TenantPrincipal, agent_id: str) -> AgentGrant:
        self.require(principal, AGENT_CREATE)
        return self.store.import_agent(
            agent_id=agent_id,
            tenant_id=principal.tenant_id,
            owner_user_id=principal.user_id,
            now=_now(),
        )

    def list_agent_grants(self, principal: TenantPrincipal) -> list[AgentGrant]:
        self.require(principal, AGENT_READ)
        values = self.store.list_agent_grants(principal.tenant_id)
        if principal.has(AGENT_MANAGE):
            return values
        return [
            value
            for value in values
            if value.access is AgentAccess.TENANT
            or value.owner_user_id == principal.user_id
        ]

    def assert_agent_access(
        self,
        principal: TenantPrincipal,
        agent_id: str,
        *,
        write: bool = False,
    ) -> AgentGrant:
        self.require(principal, AGENT_MANAGE if write else AGENT_USE)
        grant = self.store.get_agent_grant(agent_id)
        if (
            grant is None
            or grant.tenant_id != principal.tenant_id
            or grant.status is not AgentStatus.ACTIVE
        ):
            raise ResourceNotFound("agent not found")
        if (
            grant.access is AgentAccess.PRIVATE
            and grant.owner_user_id != principal.user_id
            and not principal.has(AGENT_MANAGE)
        ):
            raise ResourceNotFound("agent not found")
        return grant

    def agent_runtime_principal(
        self,
        agent_id: str,
        *,
        source: str,
    ) -> TenantPrincipal:
        """Create a least-privilege service principal for background entry."""
        row = self.store.get_agent_runtime_identity(agent_id)
        if row is None or any(
            row[key] != "active"
            for key in (
                "agent_status",
                "tenant_status",
                "user_status",
                "membership_status",
            )
        ):
            raise ResourceNotFound("agent runtime identity is unavailable")
        service_role = TenantRole.OPERATOR
        return TenantPrincipal(
            tenant_id=_as_uuid(row["tenant_id"]),
            user_id=_as_uuid(row["owner_user_id"]),
            username=row["username"],
            role=service_role,
            permissions=permissions_for(service_role),
            source=source[:64],
            service_id=f"agent:{agent_id}",
        )

    def archive_agent(self, principal: TenantPrincipal, agent_id: str) -> bool:
        self.require(principal, AGENT_DELETE)
        self.assert_agent_access(principal, agent_id, write=True)
        result = self.store.archive_agent(agent_id, principal.tenant_id, _now())
        if result:
            self.audit(
                principal,
                action="agent.archive",
                resource_type="agent",
                resource_id=agent_id,
            )
        return result

    def rollback_agent_registration(
        self,
        principal: TenantPrincipal,
        agent_id: str,
    ) -> bool:
        """Compensate a failed create before the Agent becomes observable."""
        self.require(principal, AGENT_CREATE)
        result = self.store.rollback_agent_registration(
            agent_id=agent_id,
            tenant_id=principal.tenant_id,
            owner_user_id=principal.user_id,
            now=_now(),
        )
        if result:
            self.audit(
                principal,
                action="agent.create.rollback",
                resource_type="agent",
                resource_id=agent_id,
            )
        return result

    def acquire_task_lease(
        self,
        principal: TenantPrincipal,
        agent_id: str,
    ) -> UUID:
        """Reserve one crash-tolerant tenant concurrency slot."""
        self.require(principal, AGENT_USE)
        self.assert_agent_access(principal, agent_id)
        storage_mb = self.refresh_storage_usage(principal)
        if storage_mb >= self.store.get_quota(principal.tenant_id).max_storage_mb:
            raise QuotaExceeded("storage quota exceeded")
        now = _now()
        return self.store.acquire_task_lease(
            tenant_id=principal.tenant_id,
            agent_id=agent_id,
            now=now,
            expires_at=now + timedelta(seconds=TASK_LEASE_TTL_SECONDS),
        )

    def renew_task_lease(
        self,
        principal: TenantPrincipal,
        lease_id: UUID,
    ) -> bool:
        now = _now()
        return self.store.renew_task_lease(
            lease_id=lease_id,
            tenant_id=principal.tenant_id,
            now=now,
            expires_at=now + timedelta(seconds=TASK_LEASE_TTL_SECONDS),
        )

    def release_task_lease(
        self,
        principal: TenantPrincipal,
        lease_id: UUID,
    ) -> bool:
        released = self.store.release_task_lease(
            lease_id=lease_id,
            tenant_id=principal.tenant_id,
            now=_now(),
        )
        self.refresh_storage_usage(principal, force=True)
        return released

    def refresh_storage_usage(
        self,
        principal: TenantPrincipal,
        *,
        force: bool = False,
    ) -> int:
        """Measure authorized Agent workspaces without following symlinks."""
        cached = self._storage_cache.get(principal.tenant_id)
        if not force and cached and time.monotonic() - cached[0] < 30:
            return cached[1]
        from ..config.utils import load_config

        config = load_config()
        grants = self.store.list_agent_grants(principal.tenant_id)
        roots = {
            Path(config.agents.profiles[grant.agent_id].workspace_dir)
            for grant in grants
            if grant.agent_id in config.agents.profiles
        }
        quota = self.store.get_quota(principal.tenant_id)
        stop_after = (quota.max_storage_mb + 1) * 1024 * 1024
        total = 0
        stack = [root for root in roots if root.exists() and not root.is_symlink()]
        while stack and total <= stop_after:
            directory = stack.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            if total > stop_after:
                                break
            except OSError as exc:
                raise RuntimeError(
                    f"cannot measure tenant workspace storage: {directory}",
                ) from exc
        storage_mb = (total + 1024 * 1024 - 1) // (1024 * 1024)
        self.store.update_storage_usage(
            principal.tenant_id,
            storage_mb,
            _now(),
        )
        self._storage_cache[principal.tenant_id] = (time.monotonic(), storage_mb)
        return storage_mb

    def list_audit(
        self,
        principal: TenantPrincipal,
        *,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[TenantAuditEvent]:
        self.require(principal, AUDIT_READ)
        return self.store.list_audit_events(
            principal.tenant_id,
            limit=limit,
            before=before,
        )

    def audit(
        self,
        principal: TenantPrincipal,
        *,
        action: str,
        resource_type: str,
        resource_id: str,
        outcome: str = "success",
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_metadata = _sanitize_audit_value(metadata or {})
        encoded = json.dumps(safe_metadata, ensure_ascii=False, default=str)
        if len(encoded) > 16_384:
            safe_metadata = {"truncated": True}
        self.store.append_audit(
            TenantAuditEvent(
                event_id=uuid4(),
                tenant_id=principal.tenant_id,
                actor_user_id=principal.user_id,
                action=action[:128],
                resource_type=resource_type[:64],
                resource_id=resource_id[:256],
                outcome=outcome[:32],
                request_id=request_id[:128] if request_id else None,
                metadata=safe_metadata,
                created_at=_now(),
            ),
        )

    @staticmethod
    def _validate_slug(value: str) -> str:
        slug = value.strip().lower()
        if not _SLUG_RE.fullmatch(slug):
            raise ValueError(
                "tenant slug must be lowercase letters, numbers or hyphens"
            )
        return slug

    @staticmethod
    def _validate_username(value: str) -> str:
        username = value.strip()
        if not _USERNAME_RE.fullmatch(username):
            raise ValueError("username must contain 2-128 non-space characters")
        return username


__all__ = [
    "PASSWORD_ALGORITHM",
    "PASSWORD_ITERATIONS",
    "TenancyService",
]
