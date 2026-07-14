"""Security tests for the current-auth to SAGE identity bridge."""

import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from minions.app import auth
from minions.sage.identity import current_sage_identity


@pytest.fixture
def isolated_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "auth.json")
    monkeypatch.setattr(
        auth,
        "encrypt_dict_fields",
        lambda data, _fields: data,
    )
    monkeypatch.setattr(
        auth,
        "decrypt_dict_fields",
        lambda data, _fields: data,
    )
    monkeypatch.setattr(auth, "is_encrypted", lambda _value: True)
    return auth


def _resign_payload(module, token: str, **changes) -> str:
    payload_b64, _ = token.split(".", 1)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    payload.update(changes)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode(),
    ).decode()
    signature = hmac.new(
        module._get_jwt_secret().encode(),
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def test_new_token_contains_stable_server_identity(isolated_auth) -> None:
    token = isolated_auth.register_user("owner", "secret-password")
    assert token is not None
    claims = isolated_auth.verify_token_claims(token)
    assert claims is not None
    assert claims["iss"] == isolated_auth.TOKEN_ISSUER
    assert claims["aud"] == isolated_auth.TOKEN_AUDIENCE
    assert claims["ver"] == isolated_auth.TOKEN_VERSION
    stored = isolated_auth._load_auth_data()["user"]
    assert stored["password_algorithm"] == isolated_auth.PASSWORD_ALGORITHM
    assert stored["password_iterations"] == isolated_auth.PASSWORD_ITERATIONS
    tenant_id = UUID(claims["tenant_id"])
    user_id = UUID(claims["user_id"])

    updated = isolated_auth.update_credentials(
        "secret-password",
        new_username="renamed-owner",
    )
    assert updated is not None
    updated_claims = isolated_auth.verify_token_claims(updated)
    assert updated_claims is not None
    assert UUID(updated_claims["tenant_id"]) == tenant_id
    assert UUID(updated_claims["user_id"]) == user_id


def test_signed_claims_cannot_switch_persisted_tenant(isolated_auth) -> None:
    token = isolated_auth.register_user("owner", "secret-password")
    assert token is not None
    forged = _resign_payload(
        isolated_auth,
        token,
        tenant_id=str(uuid4()),
    )
    assert isolated_auth.verify_token_claims(forged) is None


def test_legacy_tokens_are_disabled_unless_migration_flag_is_set(
    isolated_auth,
    monkeypatch,
) -> None:
    token = isolated_auth.register_user("owner", "secret-password")
    assert token is not None
    legacy = _resign_payload(
        isolated_auth,
        token,
        ver=1,
        iss=None,
        aud=None,
    )
    assert isolated_auth.verify_token_claims(legacy) is None
    monkeypatch.setenv("MINIONS_AUTH_ALLOW_LEGACY_TOKENS", "true")
    assert isolated_auth.verify_token_claims(legacy) is not None


def test_corrupt_persisted_identity_fails_closed(isolated_auth) -> None:
    isolated_auth._save_auth_data(
        {
            "jwt_secret": "a" * 64,
            "tenant_id": "not-a-uuid",
            "user": {
                "username": "owner",
                "password_hash": "hash",
                "password_salt": "salt",
            },
        },
    )
    assert isolated_auth._ensure_single_user_identity() is None
    with pytest.raises(ValueError, match="registered identity"):
        isolated_auth.create_token("owner")


def test_tenant_mode_disables_localhost_auth_bypass(
    isolated_auth,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MINIONS_SAGE_MODE", "tenant")
    monkeypatch.setattr(isolated_auth, "is_auth_enabled", lambda: False)
    monkeypatch.setattr(isolated_auth, "has_registered_users", lambda: False)
    protected = SimpleNamespace(
        url=SimpleNamespace(path="/api/console/chat"),
        method="POST",
    )
    public = SimpleNamespace(
        url=SimpleNamespace(path="/api/auth/register"),
        method="POST",
    )
    assert isolated_auth.AuthMiddleware._should_skip_auth(protected) is False
    assert isolated_auth.AuthMiddleware._should_skip_auth(public) is True


def test_legacy_password_is_rehashed_after_successful_login(
    isolated_auth,
) -> None:
    password = "legacy-password"
    salt = "ab" * 16
    legacy_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    isolated_auth._save_auth_data(
        {
            "jwt_secret": "b" * 64,
            "user": {
                "username": "legacy-owner",
                "password_hash": legacy_hash,
                "password_salt": salt,
            },
        },
    )
    token = isolated_auth.authenticate("legacy-owner", password)
    assert token is not None
    stored = isolated_auth._load_auth_data()["user"]
    assert stored["password_algorithm"] == isolated_auth.PASSWORD_ALGORITHM
    assert stored["password_hash"] != legacy_hash


@pytest.mark.asyncio
async def test_auth_middleware_binds_and_resets_identity(
    isolated_auth,
    monkeypatch,
) -> None:
    token = isolated_auth.register_user("owner", "secret-password")
    assert token is not None
    middleware = object.__new__(isolated_auth.AuthMiddleware)
    monkeypatch.setattr(middleware, "_should_skip_auth", lambda _request: False)
    monkeypatch.setattr(middleware, "_extract_token", lambda _request: token)
    request = SimpleNamespace(state=SimpleNamespace())

    async def call_next(bound_request):
        identity = current_sage_identity()
        assert identity is not None
        assert identity is bound_request.state.sage_identity
        assert bound_request.state.user == "owner"
        return "ok"

    assert await middleware.dispatch(request, call_next) == "ok"
    assert current_sage_identity() is None
