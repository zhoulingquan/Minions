from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

import pytest

from minions.tenancy.errors import (
    AccessDenied,
    AmbiguousTenant,
    AuthenticationFailed,
    Conflict,
    ResourceNotFound,
)
from minions.tenancy.models import AgentAccess, MembershipStatus, TenantRole


def test_bootstrap_login_invite_and_immediate_revocation(tenancy_service):
    token, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    assert tenancy_service.verify_token(token).tenant_id == owner.tenant_id

    invite, raw = tenancy_service.invite_member(
        owner,
        username="operator",
        role=TenantRole.OPERATOR,
    )
    assert invite.token_hash != raw
    operator_token, operator = tenancy_service.accept_invite(
        invite_token=raw,
        username="operator",
        password="correct-horse",
    )
    assert tenancy_service.verify_token(operator_token).role is TenantRole.OPERATOR

    tenancy_service.update_member(
        owner,
        user_id=operator.user_id,
        status=MembershipStatus.DISABLED,
    )
    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(operator_token)


def test_pending_invite_can_be_revoked_once(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    invite, raw = tenancy_service.invite_member(
        owner,
        username="operator",
        role=TenantRole.OPERATOR,
    )
    assert tenancy_service.revoke_invite(owner, invite_id=invite.invite_id)
    with pytest.raises(ResourceNotFound, match="invite is invalid or expired"):
        tenancy_service.accept_invite(
            invite_token=raw,
            username="operator",
            password="correct-horse",
        )


def test_duplicate_pending_invite_and_existing_member_are_rejected(
    tenancy_service,
):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.invite_member(
        owner,
        username="operator",
        role=TenantRole.OPERATOR,
    )
    with pytest.raises(Conflict, match="invite already exists"):
        tenancy_service.invite_member(
            owner,
            username="operator",
            role=TenantRole.MEMBER,
        )
    with pytest.raises(Conflict, match="already a tenant member"):
        tenancy_service.invite_member(
            owner,
            username="owner",
            role=TenantRole.ADMIN,
        )


def test_viewer_cannot_create_agent(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    _, raw = tenancy_service.invite_member(
        owner,
        username="viewer",
        role=TenantRole.VIEWER,
    )
    _, viewer = tenancy_service.accept_invite(
        invite_token=raw,
        username="viewer",
        password="correct-horse",
    )
    with pytest.raises(AccessDenied):
        tenancy_service.register_agent(viewer, agent_id="forbidden")


def test_private_agent_is_hidden_from_ordinary_tenant_members(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.register_agent(
        owner,
        agent_id="owner-private",
        access=AgentAccess.PRIVATE,
    )
    tenancy_service.register_agent(owner, agent_id="tenant-shared")
    _, raw = tenancy_service.invite_member(
        owner,
        username="viewer",
        role=TenantRole.VIEWER,
    )
    _, viewer = tenancy_service.accept_invite(
        invite_token=raw,
        username="viewer",
        password="correct-horse",
    )

    assert [value.agent_id for value in tenancy_service.list_agent_grants(viewer)] == [
        "tenant-shared"
    ]


def test_last_owner_cannot_be_disabled(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    with pytest.raises(Conflict, match="cannot disable the current account"):
        tenancy_service.update_member(
            owner,
            user_id=owner.user_id,
            status=MembershipStatus.DISABLED,
        )


def test_admin_cannot_manage_an_owner(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    _, raw = tenancy_service.invite_member(
        owner,
        username="admin",
        role=TenantRole.ADMIN,
    )
    _, admin = tenancy_service.accept_invite(
        invite_token=raw,
        username="admin",
        password="correct-horse",
    )
    with pytest.raises(AccessDenied, match="only an owner"):
        tenancy_service.update_member(
            admin,
            user_id=owner.user_id,
            role=TenantRole.ADMIN,
        )


def test_cross_tenant_agent_is_hidden(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.register_agent(owner, agent_id="acme-agent")
    foreign = owner.model_copy(
        update={"tenant_id": uuid4()},
    )
    with pytest.raises(ResourceNotFound):
        tenancy_service.assert_agent_access(foreign, "acme-agent")


def test_audit_metadata_drops_secret_fields(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.audit(
        owner,
        action="security.test",
        resource_type="test",
        resource_id="1",
        metadata={
            "token": "leak",
            "safe": "ok",
            "nested": {"password": "leak", "result": "kept"},
        },
    )
    latest = tenancy_service.list_audit(owner, limit=1)[0]
    assert latest.metadata == {
        "safe": "ok",
        "nested": {"result": "kept"},
    }


def test_legacy_owner_keeps_identity_and_upgrades_password(tenancy_service):
    tenant_id, user_id = uuid4(), uuid4()
    salt = "legacy-salt"
    password = "correct-horse"
    digest = hashlib.sha256((salt + password).encode()).hexdigest()

    owner = tenancy_service.import_legacy_owner(
        tenant_id=tenant_id,
        user_id=user_id,
        username="legacy-owner",
        display_name="Legacy Owner",
        password_hash=digest,
        password_salt=salt,
        password_algorithm="legacy_sha256",
        password_iterations=0,
    )
    assert owner.tenant_id == tenant_id
    assert owner.user_id == user_id

    token, logged_in = tenancy_service.login(
        username="legacy-owner",
        password=password,
    )
    assert tenancy_service.verify_token(token).user_id == logged_in.user_id
    stored = tenancy_service.store.get_user_credentials("legacy-owner")
    assert stored is not None
    assert stored["password_algorithm"] == "pbkdf2_sha256"
    assert stored["password_iterations"] == 600_000


def test_service_accepts_native_postgres_uuid_rows(tenancy_service, monkeypatch):
    token, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    store = tenancy_service.store
    original_owner = store.get_first_active_owner
    original_session = store.resolve_session

    def native_owner_row():
        row = original_owner()
        assert row is not None
        row["tenant_id"] = UUID(row["tenant_id"])
        row["user_id"] = UUID(row["user_id"])
        return row

    def native_session_row(token_hash, now, tenant_id):
        row = original_session(token_hash, now, tenant_id)
        assert row is not None
        for key in ("session_id", "tenant_id", "user_id"):
            row[key] = UUID(row[key])
        return row

    monkeypatch.setattr(store, "get_first_active_owner", native_owner_row)
    assert tenancy_service.system_owner_principal().tenant_id == owner.tenant_id
    monkeypatch.setattr(store, "resolve_session", native_session_row)
    assert tenancy_service.verify_token(token).user_id == owner.user_id


def test_profile_update_rotates_sessions_and_preserves_membership(tenancy_service):
    old_token, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    new_token, updated = tenancy_service.update_profile(
        owner,
        current_password="correct-horse",
        new_username="renamed-owner",
        new_password="stronger-horse",
    )

    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(old_token)
    assert tenancy_service.verify_token(new_token).user_id == owner.user_id
    assert updated.tenant_id == owner.tenant_id
    with pytest.raises(AuthenticationFailed):
        tenancy_service.login(username="owner", password="correct-horse")
    tenancy_service.login(
        username="renamed-owner",
        password="stronger-horse",
    )


def test_revoke_all_user_sessions_is_immediate(tenancy_service):
    first, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    second, _ = tenancy_service.login(
        username="owner",
        password="correct-horse",
    )
    assert tenancy_service.revoke_all_user_sessions(owner) == 2
    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(first)
    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(second)


def test_logout_revokes_the_current_server_session(tenancy_service):
    token, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    assert tenancy_service.logout(owner)
    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(token)


def test_owner_can_create_and_switch_between_isolated_spaces(tenancy_service):
    original_token, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    second_token, second_owner = tenancy_service.create_space(
        owner,
        tenant_name="Beta",
        tenant_slug="beta",
    )

    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(original_token)
    assert (
        tenancy_service.verify_token(second_token).tenant_id == second_owner.tenant_id
    )
    assert {item["slug"] for item in tenancy_service.list_spaces(second_owner)} == {
        "acme",
        "beta",
    }
    with pytest.raises(AmbiguousTenant):
        tenancy_service.login(username="owner", password="correct-horse")

    acme_token, acme_owner = tenancy_service.switch_space(
        second_owner,
        tenant_slug="acme",
    )
    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(second_token)
    assert acme_owner.tenant_id == owner.tenant_id
    assert tenancy_service.verify_token(acme_token).tenant_id == owner.tenant_id


def test_existing_user_must_prove_password_to_accept_another_space_invite(
    tenancy_service,
):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    _, staff_invite = tenancy_service.invite_member(
        owner,
        username="staff",
        role=TenantRole.MEMBER,
    )
    _, staff = tenancy_service.accept_invite(
        invite_token=staff_invite,
        username="staff",
        password="staff-password",
    )
    _, beta_owner = tenancy_service.create_space(
        owner,
        tenant_name="Beta",
        tenant_slug="beta",
    )
    _, beta_invite = tenancy_service.invite_member(
        beta_owner,
        username="staff",
        role=TenantRole.OPERATOR,
    )

    with pytest.raises(AuthenticationFailed):
        tenancy_service.accept_invite(
            invite_token=beta_invite,
            username="staff",
            password="wrong-password",
        )
    _, beta_staff = tenancy_service.accept_invite(
        invite_token=beta_invite,
        username="staff",
        password="staff-password",
    )
    assert beta_staff.user_id == staff.user_id
    assert beta_staff.tenant_id == beta_owner.tenant_id


@pytest.mark.parametrize("password", ["correct-horse", "wrong-password"])
def test_invalid_invite_does_not_reveal_existing_account_password(
    tenancy_service,
    password,
):
    tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )

    with pytest.raises(ResourceNotFound, match="invite is invalid or expired"):
        tenancy_service.accept_invite(
            invite_token="invalid-invite-token",
            username="owner",
            password=password,
        )


def test_profile_change_revokes_sessions_from_every_space(tenancy_service):
    acme_token, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    beta_token, beta_owner = tenancy_service.create_space(
        owner,
        tenant_name="Beta",
        tenant_slug="beta",
    )
    # create_space already replaces the original session; create another Acme
    # session so both tenant scopes have a live token before the profile change.
    acme_token, _ = tenancy_service.login(
        username="owner",
        password="correct-horse",
        tenant_slug="acme",
    )
    new_token, _ = tenancy_service.update_profile(
        beta_owner,
        current_password="correct-horse",
        new_password="stronger-horse",
    )

    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(acme_token)
    with pytest.raises(AuthenticationFailed):
        tenancy_service.verify_token(beta_token)
    assert tenancy_service.verify_token(new_token).tenant_id == beta_owner.tenant_id
