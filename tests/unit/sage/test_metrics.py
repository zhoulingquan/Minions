# -*- coding: utf-8 -*-
"""Tests for tenant-scoped SAGE health snapshots."""

from uuid import uuid4

import pytest

from minions.sage.metrics import SageMetrics
from minions.sage.models import (
    GrowthJob,
    GrowthJobType,
    ItemKind,
    ItemState,
    Principal,
    ScopeRef,
    ScopeType,
)
from minions.sage.catalog import SageCatalog
from minions.sage.sqlite_store import SQLiteSageStore


@pytest.mark.asyncio
async def test_snapshot_counts_only_visible_tenant_state(tmp_path) -> None:
    principal = Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="metrics",
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        await SageCatalog(store).create_item(
            principal,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Known fact",
            content="Verified",
            state=ItemState.ACTIVE,
        )
        await store.enqueue_growth_job(
            principal,
            GrowthJob(
                tenant_id=principal.tenant_id,
                job_type=GrowthJobType.EVALUATE_RECALL,
                payload={"principal": principal.model_dump(mode="json")},
            ),
        )
        snapshot = await SageMetrics(store).snapshot(principal)
        assert snapshot.knowledge_total == 1
        assert snapshot.active_knowledge == 1
        assert snapshot.pending_jobs == 1
        assert snapshot.degradation_rate == 0
    finally:
        await store.close()
