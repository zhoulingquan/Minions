# -*- coding: utf-8 -*-
"""Tests for durable and idempotent SAGE nightly scheduling."""

from uuid import uuid4

import pytest

from minions.sage.control import PolicyCenter
from minions.sage.maintenance import MaintenanceCoordinator
from minions.sage.models import (
    ActivationMode,
    GrowthJobType,
    Principal,
    SageCapability,
)
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*permissions: str) -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="maintenance-session",
        permissions=frozenset(permissions),
    )


@pytest.mark.asyncio
async def test_schedule_due_creates_three_deterministic_jobs(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        coordinator = MaintenanceCoordinator(store, PolicyCenter(store))
        first = await coordinator.schedule_due(
            principal,
            local_date="2026-07-13",
        )
        second = await coordinator.schedule_due(
            principal,
            local_date="2026-07-13",
        )
        assert [job.job_id for job in first] == [job.job_id for job in second]
        assert {job.job_type for job in first} == {
            GrowthJobType.CONSOLIDATE_TENANT,
            GrowthJobType.RECALCULATE_UTILITY,
            GrowthJobType.EVALUATE_RECALL,
        }
        claimed = await store.claim_growth_jobs(
            principal,
            worker_id="maintenance-test",
            limit=10,
        )
        assert len(claimed) == 3
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_off_policy_does_not_schedule_nightly_work(tmp_path) -> None:
    principal = _principal("sage.policy.manage")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        control = PolicyCenter(store)
        await control.set_policy(
            principal,
            capability=SageCapability.NIGHTLY_CONSOLIDATION,
            mode=ActivationMode.OFF,
        )
        assert (
            await MaintenanceCoordinator(store, control).schedule_due(
                principal,
                local_date="2026-07-13",
            )
            == []
        )
    finally:
        await store.close()
