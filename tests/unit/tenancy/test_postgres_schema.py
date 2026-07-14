from __future__ import annotations

from pathlib import Path

from minions.tenancy import postgres_store


def _migration(name: str) -> str:
    return (
        Path(postgres_store.__file__).parent / "migrations" / name
    ).read_text(encoding="utf-8")


def test_postgres_schema_has_rls_and_tenant_leading_indexes():
    sql = _migration("0001_control_plane.sql").lower()
    assert "enable row level security" in sql
    assert "current_setting(''app.tenant_id''" in sql
    assert "on agent_grants (tenant_id, status, agent_id)" in sql
    assert "on tenant_audit_events (tenant_id, created_at desc" in sql
    assert "where revoked_at is null" in sql
    assert "security definer" in sql
    assert "revoke all on function tenancy_login_memberships" in sql


def test_runtime_role_cannot_bypass_rls_or_administer_database():
    sql = _migration("runtime_role.sql").lower()
    assert "nosuperuser" in sql
    assert "nocreatedb" in sql
    assert "nocreaterole" in sql
    assert "nobypassrls" in sql
    assert "revoke all on schema" in sql
    assert "grant execute on function tenancy_invite_tenant" in sql


def test_task_leases_are_tenant_scoped_and_indexed():
    sql = _migration("0002_task_leases.sql").lower()
    assert "enable row level security" in sql
    assert "tenant_task_leases_tenant_isolation" in sql
    assert "on tenant_task_leases (tenant_id, expires_at)" in sql


def test_pending_invites_are_unique_per_tenant_and_username():
    sql = _migration("0003_invite_uniqueness.sql").lower()
    assert "partition by tenant_id, lower(username)" in sql
    assert "unique index" in sql
    assert "where status='pending'" in sql
    assert "values (3)" in sql
