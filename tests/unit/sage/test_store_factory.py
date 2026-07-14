"""Tests for fail-closed SAGE storage selection."""

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

import minions.sage.postgres_store as postgres_module
from minions.sage.factory import (
    SageDeploymentMode,
    SageStoreBackend,
    SageStoreSettings,
    build_sage_store,
)
from minions.sage.postgres_store import PostgresSageStore
from minions.sage.models import Principal
from minions.sage.postgres_schema import SET_LOCAL_TENANT_SQL
from minions.sage.sqlite_store import SQLiteSageStore


def test_development_defaults_to_workspace_sqlite(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("MINIONS_SAGE_MODE", raising=False)
    monkeypatch.delenv("MINIONS_SAGE_STORE", raising=False)
    store = build_sage_store(tmp_path)
    assert isinstance(store, SQLiteSageStore)
    assert store.path == tmp_path / "sage" / "sage.db"


def test_production_never_falls_back_to_sqlite(tmp_path) -> None:
    settings = SageStoreSettings(
        mode=SageDeploymentMode.PRODUCTION,
        backend=SageStoreBackend.SQLITE,
    )
    with pytest.raises(RuntimeError, match="fallback denied"):
        build_sage_store(tmp_path, settings)


def test_production_requires_postgres_dsn(tmp_path) -> None:
    settings = SageStoreSettings(
        mode=SageDeploymentMode.TENANT,
        backend=SageStoreBackend.POSTGRES,
    )
    with pytest.raises(RuntimeError, match="POSTGRES_DSN"):
        build_sage_store(tmp_path, settings)


def test_postgres_selection_builds_production_adapter(tmp_path) -> None:
    settings = SageStoreSettings(
        mode=SageDeploymentMode.PRODUCTION,
        backend=SageStoreBackend.POSTGRES,
        postgres_dsn="postgresql://user:secret@db/minions",
        postgres_pool_min=2,
        postgres_pool_max=7,
    )
    store = build_sage_store(tmp_path, settings)
    assert isinstance(store, PostgresSageStore)
    assert store._dsn.endswith("/minions")
    assert store._min_size == 2
    assert store._max_size == 7


@pytest.mark.asyncio
async def test_missing_postgres_dependency_has_clear_failure(monkeypatch) -> None:
    monkeypatch.setattr(postgres_module, "AsyncConnectionPool", None)
    store = PostgresSageStore("postgresql://user:secret@db/minions")
    with pytest.raises(RuntimeError, match=r"minions\[postgres\]"):
        await store.start()


@pytest.mark.asyncio
async def test_postgres_connection_sets_transaction_local_tenant() -> None:
    calls = []

    class Connection:
        @asynccontextmanager
        async def transaction(self):
            yield

        async def execute(self, sql, params):
            calls.append((sql, params))

    class Pool:
        @asynccontextmanager
        async def connection(self):
            yield Connection()

    principal = Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="postgres-session",
    )
    store = PostgresSageStore("postgresql://user:secret@db/minions")
    store._pool = Pool()
    async with store._tenant_connection(principal):
        pass
    assert calls == [
        (SET_LOCAL_TENANT_SQL, (str(principal.tenant_id),)),
    ]
