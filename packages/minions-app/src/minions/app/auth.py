# -*- coding: utf-8 -*-
"""Authentication middleware and legacy single-user migration bridge.

When tenancy 2.1 is enabled, online identities, signed sessions, membership
checks and revocation come from :mod:`minions.tenancy`.  The older ``auth.json``
implementation remains only for installations that have not enabled tenancy
and as an idempotent source for importing the first owner.  Both paths use
PBKDF2-HMAC-SHA256 and upgrade historical salted SHA-256 values after a
successful credential check.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..constant import SECRET_DIR, EnvVarLoader
from ..security.secret_store import (
    AUTH_SECRET_FIELDS,
    decrypt_dict_fields,
    encrypt_dict_fields,
    is_encrypted,
)

logger = logging.getLogger(__name__)

AUTH_FILE = SECRET_DIR / "auth.json"

# Token validity: 7 days (default)
TOKEN_EXPIRY_SECONDS = 7 * 24 * 3600
TOKEN_ISSUER = "minions"
TOKEN_AUDIENCE = "minions-api"
TOKEN_VERSION = 2
PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000

# Maximum token validity: 100 years (for "permanent" tokens)
TOKEN_EXPIRY_MAX = 100 * 365 * 24 * 3600

# Paths that do NOT require authentication
_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/api/auth/login",
        "/api/auth/tenant-options",
        "/api/auth/status",
        "/api/auth/register",
        "/api/tenancy/invites/accept",
        "/api/version",
        "/api/settings/language",
        "/api/settings/upload-limit",
        "/api/frontend_plugin",
    },
)

# Prefixes that do NOT require authentication (static assets)
# /api/frontend_plugin/ is safe: only read-only GET handlers are registered
# under that prefix (list + static file serving).  All write operations
# remain under /api/plugins/ which requires authentication.
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/assets/",
    "/logo.png",
    "/minions-symbol.svg",
    "/api/frontend_plugin/",
)


# ---------------------------------------------------------------------------
# Helpers (reuse SECRET_DIR patterns from envs/store.py)
# ---------------------------------------------------------------------------


def _chmod_best_effort(path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _prepare_secret_parent(path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod_best_effort(path.parent, 0o700)


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256, with legacy upgrade)
# ---------------------------------------------------------------------------


def _hash_password(
    password: str,
    salt: Optional[str] = None,
    iterations: int = PASSWORD_ITERATIONS,
) -> tuple[str, str]:
    """Hash a password using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    ).hex()
    return h, salt


def verify_password(
    password: str,
    stored_hash: str,
    salt: str,
    *,
    algorithm: str = "legacy_sha256",
    iterations: int = PASSWORD_ITERATIONS,
) -> bool:
    """Verify *password* against a stored hash."""
    if algorithm == PASSWORD_ALGORITHM:
        if iterations < 100_000:
            return False
        try:
            h, _ = _hash_password(password, salt, iterations)
        except (ValueError, TypeError):
            return False
    elif algorithm == "legacy_sha256":
        h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    else:
        return False
    return hmac.compare_digest(h, stored_hash)


def _stored_password_iterations(user: dict) -> int:
    try:
        return int(user.get("password_iterations", PASSWORD_ITERATIONS))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Token generation / verification (HMAC-SHA256, no PyJWT needed)
# ---------------------------------------------------------------------------


def _get_jwt_secret() -> str:
    """Return the signing secret, creating one if absent."""
    data = _load_auth_data()
    secret = data.get("jwt_secret", "")
    if not secret:
        secret = secrets.token_hex(32)
        data["jwt_secret"] = secret
        _save_auth_data(data)
    return secret


def _ensure_single_user_identity() -> dict | None:
    """Migrate the registered account to stable tenant/user UUIDs."""
    data = _load_auth_data()
    if data.get("_auth_load_error"):
        return None
    user = data.get("user")
    if not isinstance(user, dict) or not user.get("username"):
        return None

    changed = False
    secret = data.get("jwt_secret")
    if not secret:
        secret = secrets.token_hex(32)
        data["jwt_secret"] = secret
        changed = True

    raw_tenant_id = data.get("tenant_id")
    if raw_tenant_id:
        try:
            tenant_id = UUID(str(raw_tenant_id))
        except (TypeError, ValueError):
            logger.error("Invalid persisted tenant_id; refusing identity migration")
            return None
    else:
        tenant_id = uuid5(NAMESPACE_URL, f"minions:tenant:{secret}")
        data["tenant_id"] = str(tenant_id)
        changed = True

    raw_user_id = user.get("user_id")
    if raw_user_id:
        try:
            user_id = UUID(str(raw_user_id))
        except (TypeError, ValueError):
            logger.error("Invalid persisted user_id; refusing identity migration")
            return None
    else:
        user_id = uuid5(tenant_id, f"user:{user['username']}")
        user["user_id"] = str(user_id)
        data["user"] = user
        changed = True

    if changed:
        _save_auth_data(data)
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "username": str(user["username"]),
    }


def create_token(username: str, expiry_seconds: Optional[int] = None) -> str:
    """Create an HMAC-signed token: ``base64(payload).signature``.

    Args:
        username: The username to encode in the token.
        expiry_seconds: Custom expiry time in seconds.
            Use -1 or 0 for permanent tokens.
            Defaults to TOKEN_EXPIRY_SECONDS (7 days).
    """
    import base64

    if expiry_seconds is None:
        expiry_seconds = TOKEN_EXPIRY_SECONDS
    elif expiry_seconds <= 0:
        # Permanent token: 100 years
        expiry_seconds = TOKEN_EXPIRY_MAX
    else:
        # Cap at maximum allowed expiry
        expiry_seconds = min(expiry_seconds, TOKEN_EXPIRY_MAX)

    secret = _get_jwt_secret()
    identity = _ensure_single_user_identity()
    if identity is None or identity["username"] != username:
        raise ValueError("cannot issue token without a registered identity")
    # Generate unique token ID (jti) for revocation support
    token_id = secrets.token_hex(16)
    payload = json.dumps(
        {
            "sub": username,
            "exp": int(time.time()) + expiry_seconds,
            "iat": int(time.time()),
            "jti": token_id,  # JWT ID for individual revocation
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "ver": TOKEN_VERSION,
            "tenant_id": str(identity["tenant_id"]),
            "user_id": str(identity["user_id"]),
        },
        separators=(",", ":"),
    )
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(
        secret.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_token_claims(token: str) -> dict | None:
    """Verify token integrity and bind claims to the stored identity."""
    import base64

    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        secret = _get_jwt_secret()
        expected_sig = hmac.new(
            secret.encode(),
            payload_b64.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
            return None

        # Check if token is revoked
        jti = payload.get("jti")
        if jti and _is_token_revoked(jti):
            return None

        username = payload.get("sub")
        identity = _ensure_single_user_identity()
        if identity is None or username != identity["username"]:
            return None
        version = int(payload.get("ver", 1))
        if version == 1:
            allow_legacy = EnvVarLoader.get_str(
                "MINIONS_AUTH_ALLOW_LEGACY_TOKENS",
                "",
            ).strip().lower() in {"true", "1", "yes"}
            if not allow_legacy:
                return None
        elif version != TOKEN_VERSION:
            return None
        if version == TOKEN_VERSION and (
            payload.get("iss") != TOKEN_ISSUER
            or payload.get("aud") != TOKEN_AUDIENCE
        ):
            return None
        claimed_tenant = payload.get("tenant_id")
        claimed_user = payload.get("user_id")
        if claimed_tenant and claimed_tenant != str(identity["tenant_id"]):
            return None
        if claimed_user and claimed_user != str(identity["user_id"]):
            return None
        payload["tenant_id"] = str(identity["tenant_id"])
        payload["user_id"] = str(identity["user_id"])
        return payload
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.debug("Token verification failed: %s", exc)
        return None


def verify_token(token: str) -> Optional[str]:
    """Verify *token*, returning its username for compatibility."""
    claims = verify_token_claims(token)
    return str(claims["sub"]) if claims is not None else None


def get_sage_auth_identity(
    username: str,
    *,
    token_id: str | None = None,
):
    """Return an immutable SAGE identity for an authenticated account."""
    identity = _ensure_single_user_identity()
    if identity is None or identity["username"] != username:
        return None
    from ..sage.identity import SAGE_ADMIN_PERMISSIONS, TrustedSageIdentity

    return TrustedSageIdentity(
        tenant_id=identity["tenant_id"],
        user_id=identity["user_id"],
        source="http",
        permissions=SAGE_ADMIN_PERMISSIONS,
        token_id=token_id,
    )


# ---------------------------------------------------------------------------
# Auth data persistence (auth.json in SECRET_DIR)
# ---------------------------------------------------------------------------


def _load_auth_data() -> dict:
    """Load ``auth.json`` from ``SECRET_DIR``.

    Returns the parsed dict, or a sentinel with ``_auth_load_error``
    set to ``True`` when the file exists but cannot be read/parsed so
    that callers can fail closed instead of silently bypassing auth.

    Encrypted fields (``jwt_secret``) are transparently decrypted.
    Legacy plaintext values trigger an automatic re-encryption.
    """
    if AUTH_FILE.is_file():
        try:
            with open(AUTH_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            needs_rewrite = any(
                isinstance(data.get(field), str)
                and data.get(field)
                and not is_encrypted(data[field])
                for field in AUTH_SECRET_FIELDS
            )
            data = decrypt_dict_fields(data, AUTH_SECRET_FIELDS)
            if needs_rewrite:
                try:
                    _save_auth_data(data)
                except Exception as enc_err:
                    logger.debug(
                        "Deferred plaintext→encrypted migration for"
                        " auth.json: %s",
                        enc_err,
                    )
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load auth file %s: %s", AUTH_FILE, exc)
            return {"_auth_load_error": True}
    return {}


def _save_auth_data(data: dict) -> None:
    """Save ``auth.json`` to ``SECRET_DIR`` with restrictive permissions.

    Sensitive fields (``jwt_secret``) are encrypted before writing.
    """
    _prepare_secret_parent(AUTH_FILE)
    encrypted_data = encrypt_dict_fields(data, AUTH_SECRET_FIELDS)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(encrypted_data, f, indent=2, ensure_ascii=False)
    _chmod_best_effort(AUTH_FILE, 0o600)


# ---------------------------------------------------------------------------
# Token revocation (blacklist management)
# ---------------------------------------------------------------------------


def _is_token_revoked(jti: str) -> bool:
    """Check if a token ID (jti) is in the revocation list.

    Uses O(1) dict lookup via revoked_tokens_meta for performance.
    """
    data = _load_auth_data()
    meta = data.get("revoked_tokens_meta", {})
    return jti in meta


def _add_to_revocation_list(jti: str, exp: int) -> None:
    """Add a token ID to the revocation list with its expiry time.

    Uses revoked_tokens_meta dict for O(1) lookups. The revoked_tokens list
    is kept for backwards compatibility but not used for membership checks.
    """
    data = _load_auth_data()
    if data.get("_auth_load_error"):
        return

    # Initialize revoked_tokens_meta if not present
    if "revoked_tokens_meta" not in data:
        data["revoked_tokens_meta"] = {}

    # O(1) check using dict
    if jti not in data["revoked_tokens_meta"]:
        data["revoked_tokens_meta"][jti] = exp

        # Also add to list for backwards compatibility
        if "revoked_tokens" not in data:
            data["revoked_tokens"] = []
        data["revoked_tokens"].append(jti)

    _save_auth_data(data)


def _clean_expired_revocations() -> None:
    """
    Remove expired tokens from the revocation list to prevent unbounded growth.
    """
    data = _load_auth_data()
    if data.get("_auth_load_error"):
        return

    revoked = data.get("revoked_tokens", [])
    meta = data.get("revoked_tokens_meta", {})
    current_time = int(time.time())

    # Remove expired tokens
    cleaned_revoked = []
    cleaned_meta = {}

    for jti in revoked:
        exp = meta.get(jti, 0)
        if exp > current_time:
            cleaned_revoked.append(jti)
            cleaned_meta[jti] = exp

    if len(cleaned_revoked) < len(revoked):
        data["revoked_tokens"] = cleaned_revoked
        data["revoked_tokens_meta"] = cleaned_meta
        _save_auth_data(data)
        logger.info(
            "Cleaned %d expired tokens from revocation list",
            len(revoked) - len(cleaned_revoked),
        )


def is_auth_enabled() -> bool:
    """Check whether authentication is enabled via environment variable.

    Returns ``True`` when ``MINIONS_AUTH_ENABLED`` is set to a truthy
    value (``true``, ``1``, ``yes``).  The presence of a registered
    user is checked separately by the middleware so that the first
    user can still reach the registration page.
    """
    env_flag = EnvVarLoader.get_str("MINIONS_AUTH_ENABLED", "").strip().lower()
    return (
        env_flag in ("true", "1", "yes")
        or is_tenant_mode()
        or is_tenancy_auth_enabled()
    )


def is_tenancy_auth_enabled() -> bool:
    """Return whether online authentication uses the 2.1 control plane.

    Development remains backwards compatible until explicitly enabled. Tenant
    and production deployments always use the control plane and cannot opt out.
    """
    explicit = EnvVarLoader.get_str("MINIONS_TENANCY_ENABLED", "").strip().lower()
    if explicit:
        return explicit in {"true", "1", "yes"}
    return is_tenant_mode()


def has_registered_users() -> bool:
    """Return ``True`` if a user has been registered."""
    data = _load_auth_data()
    return bool(data.get("user"))


def get_legacy_auth_account_for_migration() -> dict | None:
    """Return the former single-user credential record for an internal import.

    The identity UUIDs are stabilized first so existing SAGE rows keep the same
    tenant and user ownership after the control-plane upgrade.
    """
    identity = _ensure_single_user_identity()
    if identity is None:
        return None
    data = _load_auth_data()
    user = data.get("user")
    if not isinstance(user, dict):
        return None
    password_hash = str(user.get("password_hash") or "")
    password_salt = str(user.get("password_salt") or "")
    if not password_hash or not password_salt:
        return None
    return {
        **identity,
        "display_name": str(user.get("display_name") or identity["username"]),
        "password_hash": password_hash,
        "password_salt": password_salt,
        "password_algorithm": str(
            user.get("password_algorithm") or "legacy_sha256"
        ),
        "password_iterations": _stored_password_iterations(user),
    }


def is_tenant_mode() -> bool:
    """Return whether deployment policy requires authenticated tenancy."""
    mode = os.environ.get(
        "MINIONS_TENANCY_MODE",
        os.environ.get("MINIONS_SAGE_MODE", ""),
    ).strip().lower()
    return mode in {
        "production",
        "tenant",
    }


# ---------------------------------------------------------------------------
# Registration (single-user)
# ---------------------------------------------------------------------------


def register_user(
    username: str,
    password: str,
    expiry_seconds: Optional[int] = None,
) -> Optional[str]:
    """Register the single user account.

    Args:
        username: The username to register.
        password: The password to register.
        expiry_seconds: Custom token expiry time in seconds.

    Returns a token on success, ``None`` if a user already exists.
    """
    data = _load_auth_data()

    # Only one user allowed
    if data.get("user"):
        return None

    pw_hash, salt = _hash_password(password)
    data["user"] = {
        "username": username,
        "password_hash": pw_hash,
        "password_salt": salt,
        "password_algorithm": PASSWORD_ALGORITHM,
        "password_iterations": PASSWORD_ITERATIONS,
    }

    # Ensure jwt_secret exists
    if not data.get("jwt_secret"):
        data["jwt_secret"] = secrets.token_hex(32)

    tenant_id = uuid5(NAMESPACE_URL, f"minions:tenant:{data['jwt_secret']}")
    data["tenant_id"] = str(tenant_id)
    data["user"]["user_id"] = str(uuid5(tenant_id, f"user:{username}"))

    _save_auth_data(data)
    logger.info("User '%s' registered", username)
    return create_token(username, expiry_seconds)


def auto_register_from_env() -> None:
    """Auto-register admin user from environment variables.

    Called once during application startup.  If ``MINIONS_AUTH_ENABLED``
    is truthy and both ``MINIONS_AUTH_USERNAME`` and ``MINIONS_AUTH_PASSWORD``
    are set, the admin account is created automatically — useful for
    Docker, Kubernetes, server-panel, and other automated deployments
    where interactive web registration is not practical.

    Skips silently when:
    - authentication is not enabled
    - a user has already been registered
    - either env var is missing or empty
    """
    if not is_auth_enabled():
        return
    if has_registered_users():
        return

    username = EnvVarLoader.get_str("MINIONS_AUTH_USERNAME", "").strip()
    password = EnvVarLoader.get_str("MINIONS_AUTH_PASSWORD", "").strip()
    if not username or not password:
        return

    token = register_user(username, password)
    if token:
        logger.info(
            "Auto-registered user '%s' from environment variables",
            username,
        )


def update_credentials(
    current_password: str,
    new_username: Optional[str] = None,
    new_password: Optional[str] = None,
    expiry_seconds: Optional[int] = None,
) -> Optional[str]:
    """Update the registered user's username and/or password.

    Requires the current password for verification.  Returns a new
    token on success (because the username may have changed), or
    ``None`` if verification fails.

    Args:
        current_password: The current password for verification.
        new_username: The new username (optional).
        new_password: The new password (optional).
        expiry_seconds: Custom token expiry time in seconds.
    """
    data = _load_auth_data()
    user = data.get("user")
    if not user:
        return None

    stored_hash = user.get("password_hash", "")
    stored_salt = user.get("password_salt", "")
    if not verify_password(
        current_password,
        stored_hash,
        stored_salt,
        algorithm=user.get("password_algorithm", "legacy_sha256"),
        iterations=_stored_password_iterations(user),
    ):
        return None

    if new_username and new_username.strip():
        user["username"] = new_username.strip()

    if new_password:
        pw_hash, salt = _hash_password(new_password)
        user["password_hash"] = pw_hash
        user["password_salt"] = salt
        user["password_algorithm"] = PASSWORD_ALGORITHM
        user["password_iterations"] = PASSWORD_ITERATIONS
        # Rotate JWT secret to invalidate all existing sessions
        data["jwt_secret"] = secrets.token_hex(32)

    data["user"] = user
    _save_auth_data(data)
    logger.info("Credentials updated for user '%s'", user["username"])
    return create_token(user["username"], expiry_seconds)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def authenticate(
    username: str,
    password: str,
    expiry_seconds: Optional[int] = None,
) -> Optional[str]:
    """Authenticate *username* / *password*.  Returns a token if valid.

    Args:
        username: The username to authenticate.
        password: The password to verify.
        expiry_seconds: Custom token expiry time in seconds.
    """
    data = _load_auth_data()
    user = data.get("user")
    if not user:
        return None
    if user.get("username") != username:
        return None
    stored_hash = user.get("password_hash", "")
    stored_salt = user.get("password_salt", "")
    algorithm = user.get("password_algorithm", "legacy_sha256")
    iterations = _stored_password_iterations(user)
    if stored_hash and stored_salt and verify_password(
        password,
        stored_hash,
        stored_salt,
        algorithm=algorithm,
        iterations=iterations,
    ):
        if algorithm != PASSWORD_ALGORITHM:
            upgraded_hash, upgraded_salt = _hash_password(password)
            user["password_hash"] = upgraded_hash
            user["password_salt"] = upgraded_salt
            user["password_algorithm"] = PASSWORD_ALGORITHM
            user["password_iterations"] = PASSWORD_ITERATIONS
            data["user"] = user
            _save_auth_data(data)
        return create_token(username, expiry_seconds)
    return None


def revoke_token(token: str) -> bool:
    """Revoke a single token by adding its jti to the blacklist.

    Args:
        token: The token string to revoke.

    Returns True on success, False on failure.
    """
    import base64

    try:
        # Extract jti and exp from token
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False

        payload_b64 = parts[0]
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        jti = payload.get("jti")
        exp = payload.get("exp", 0)

        if not jti:
            logger.warning("Token has no jti, cannot revoke individually")
            return False

        _add_to_revocation_list(jti, exp)
        logger.info("Token %s revoked", jti[:8])

        # Clean up expired tokens periodically
        _clean_expired_revocations()

        return True
    except Exception as exc:
        logger.error("Failed to revoke token: %s", exc)
        return False


def revoke_all_tokens() -> bool:
    """Revoke all existing tokens by rotating the JWT secret.

    This will invalidate all tokens that were issued before this call.
    Also clears the revocation list since all tokens are invalid anyway.
    Returns True on success, False on failure.
    """
    try:
        data = _load_auth_data()
        if data.get("_auth_load_error"):
            return False

        # Rotate JWT secret to invalidate all existing tokens
        data["jwt_secret"] = secrets.token_hex(32)

        # Clear revocation list since all tokens are now invalid
        data["revoked_tokens"] = []
        data["revoked_tokens_meta"] = {}

        _save_auth_data(data)
        logger.info("All tokens revoked (JWT secret rotated)")
        return True
    except Exception as exc:
        logger.error("Failed to revoke tokens: %s", exc)
        return False


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------


def _resolve_client_ip(request: Request) -> str:
    """Return the real client IP, respecting reverse-proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""


# Make this function available at module level so it can be
# imported from routers
resolve_client_ip = _resolve_client_ip


# Cached config for hot-path auth checks (avoids disk read per request)
_auth_config_cache: tuple = (0, None)  # (mtime_ns, config)


def _get_config_cached():
    """Return config with mtime-based cache (stat is ~1us vs read ~1ms)."""
    global _auth_config_cache  # noqa: PLW0603
    from ..config import load_config
    from ..config.utils import get_config_path

    config_path = get_config_path()
    try:
        mtime_ns = config_path.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    if mtime_ns != _auth_config_cache[0] or _auth_config_cache[1] is None:
        _auth_config_cache = (mtime_ns, load_config())
    return _auth_config_cache[1]


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that checks Bearer token on protected routes."""

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        """Check Bearer token on protected API routes; skip public paths."""
        if self._should_skip_auth(request):
            if self._should_bind_local_principal(request):
                from ..tenancy.factory import get_tenancy_service

                principal = get_tenancy_service().local_principal()
                return await self._call_with_principal(
                    request,
                    call_next,
                    principal,
                )
            return await call_next(request)

        token = self._extract_token(request)
        if not token:
            return Response(
                content=json.dumps({"detail": "Not authenticated"}),
                status_code=401,
                media_type="application/json",
            )

        if is_tenancy_auth_enabled():
            from ..tenancy.errors import AuthenticationFailed
            from ..tenancy.factory import get_tenancy_service

            try:
                principal = get_tenancy_service().verify_token(token)
            except AuthenticationFailed:
                return Response(
                    content=json.dumps(
                        {"detail": "Invalid or expired token"},
                    ),
                    status_code=401,
                    media_type="application/json",
                )
            return await self._call_with_principal(
                request,
                call_next,
                principal,
            )

        claims = verify_token_claims(token)
        if claims is None:
            return Response(
                content=json.dumps(
                    {"detail": "Invalid or expired token"},
                ),
                status_code=401,
                media_type="application/json",
            )

        identity = get_sage_auth_identity(
            str(claims["sub"]),
            token_id=claims.get("jti"),
        )
        if identity is None:
            return Response(
                content=json.dumps({"detail": "Identity unavailable"}),
                status_code=401,
                media_type="application/json",
            )

        from ..sage.identity import bind_sage_identity, reset_sage_identity

        request.state.user = claims["sub"]
        request.state.sage_identity = identity
        identity_token = bind_sage_identity(identity)
        try:
            return await call_next(request)
        finally:
            reset_sage_identity(identity_token)

    @staticmethod
    async def _call_with_principal(request: Request, call_next, principal):
        """Bind one attested identity to tenancy, request and SAGE contexts."""
        from ..sage.identity import bind_sage_identity, reset_sage_identity
        from ..tenancy.context import bind_principal, reset_principal

        request.state.user = principal.username
        request.state.tenant_principal = principal
        sage_identity = principal.to_sage_identity(
            agent_id=getattr(request.state, "agent_id", None),
        )
        request.state.sage_identity = sage_identity
        principal_token = bind_principal(principal)
        sage_token = bind_sage_identity(sage_identity)
        try:
            return await call_next(request)
        finally:
            reset_sage_identity(sage_token)
            reset_principal(principal_token)

    @staticmethod
    def _should_bind_local_principal(request: Request) -> bool:
        """Bind a server-created local admin only for protected dev APIs."""
        if is_tenant_mode() or is_auth_enabled() or has_registered_users():
            return False
        path = request.url.path
        if not path.startswith("/api/") or request.method == "OPTIONS":
            return False
        if path in _PUBLIC_PATHS or any(
            path.startswith(prefix) for prefix in _PUBLIC_PREFIXES
        ):
            return False
        return True

    @staticmethod
    def _should_skip_auth(request: Request) -> bool:
        """Return ``True`` when the request does not require auth."""
        tenant_mode = is_tenant_mode()
        if not is_tenancy_auth_enabled() and not tenant_mode and (
            not is_auth_enabled() or not has_registered_users()
        ):
            return True

        path = request.url.path

        if request.method == "OPTIONS":
            return True

        if path in _PUBLIC_PATHS or any(
            path.startswith(p) for p in _PUBLIC_PREFIXES
        ):
            return True

        # Only protect /api/ routes
        if not path.startswith("/api/"):
            return True

        # Tenant/production mode never honors localhost or reverse-proxy
        # no-auth bypasses. Public bootstrap/login paths were handled above.
        if tenant_mode or is_tenancy_auth_enabled():
            return False

        # Check if client host is in allow_no_auth_hosts whitelist
        client_host = resolve_client_ip(request)
        config = _get_config_cached()
        allowed_hosts = config.security.allow_no_auth_hosts
        return client_host in allowed_hosts

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        """Extract Bearer token from header or WebSocket query param."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        if "upgrade" in request.headers.get("connection", "").lower():
            return request.query_params.get("token")

        token = request.query_params.get("token")
        if token:
            return token
        return None
