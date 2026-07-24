# -*- coding: utf-8 -*-
"""Static contract tests for the production PostgreSQL foundation."""

import inspect
import re

from minions.sage.postgres_store import PostgresSageStore
from minions.sage.postgres_schema import (
    RLS_TABLES,
    SET_LOCAL_TENANT_SQL,
    all_migrations_sql,
    core_migration_sql,
    core_migration_checksum,
    migration_manifest,
    runtime_role_sql,
)


def test_every_tenant_table_enables_and_forces_rls() -> None:
    sql = all_migrations_sql()
    for table in RLS_TABLES:
        qualified = f"sage.{table}"
        assert f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY" in sql
        assert f"CREATE POLICY tenant_isolation ON {qualified}" in sql


def test_every_tenant_table_uses_tenant_first_primary_key() -> None:
    sql = all_migrations_sql()
    for table in RLS_TABLES:
        block = re.search(
            rf"CREATE TABLE IF NOT EXISTS sage\.{table} \((.*?)\n\);",
            sql,
            flags=re.DOTALL,
        )
        assert block is not None
        assert "tenant_id uuid NOT NULL" in block.group(1)
        assert "PRIMARY KEY (tenant_id," in block.group(1)


def test_rls_policy_uses_database_session_tenant_for_read_and_write() -> None:
    sql = all_migrations_sql()
    expected = "tenant_id = sage.current_tenant_id()"
    assert sql.count(f"USING ({expected})") == len(RLS_TABLES)
    assert sql.count(f"WITH CHECK ({expected})") == len(RLS_TABLES)
    assert "current_setting('sage.tenant_id', true)" in sql


def test_tenant_binding_is_parameterized_and_transaction_local() -> None:
    assert "%s" in SET_LOCAL_TENANT_SQL
    assert "true" in SET_LOCAL_TENANT_SQL
    assert "{" not in SET_LOCAL_TENANT_SQL


def test_runtime_role_cannot_bypass_rls() -> None:
    sql = runtime_role_sql()
    assert "NOSUPERUSER" in sql
    assert "NOBYPASSRLS" in sql
    assert "REVOKE ALL ON SCHEMA sage FROM PUBLIC" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE" in sql


def test_core_migration_has_release_checksum_not_placeholder() -> None:
    checksum = core_migration_checksum()
    assert len(checksum) == 64
    assert set(checksum) <= set("0123456789abcdef")
    assert "managed-by-minions-release" not in core_migration_sql()
    assert checksum == (
        "357597609ba69bb6b56f055321eb89fc9fb9851b91832d6cb6d340a5c33ac0c6"
    )


def test_migration_manifest_contains_governance_policy_migration() -> None:
    manifest = migration_manifest()
    assert [entry.version for entry in manifest] == [1, 2, 3]
    assert "sage.capability_policy" in manifest[1].sql
    assert "embedding_model" in manifest[2].sql
    assert len(manifest[1].checksum) == 64


def test_postgres_policy_queries_remain_tenant_bound() -> None:
    save_source = inspect.getsource(PostgresSageStore.save_capability_policy)
    list_source = inspect.getsource(PostgresSageStore.list_capability_policies)
    assert "_tenant_connection" in save_source
    assert "tenant_id = %s" in list_source


def test_postgres_store_supports_queryless_kind_filtered_item_listing() -> (
    None
):
    source = inspect.getsource(PostgresSageStore.list_items)
    assert "kind = ANY(%s)" in source
    assert "_filter_scoped" in source


def test_growth_outbox_claim_uses_skip_locked_leases() -> None:
    source = inspect.getsource(PostgresSageStore.claim_growth_jobs)
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "leased_until" in source
    assert "attempts=j.attempts + 1" in source
