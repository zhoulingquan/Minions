"""Tests for governed, reversible tenant knowledge consolidation."""

from uuid import uuid4

import pytest

from minions.sage.consolidation import ConsolidationService
from minions.sage.control import PolicyCenter
from minions.sage.errors import SageConflict
from minions.sage.models import (
    ActivationMode,
    CandidateState,
    ConsolidationKind,
    ItemKind,
    ItemState,
    Principal,
    ScopeRef,
    ScopeType,
    SageCapability,
)
from minions.sage.catalog import SageCatalog
from minions.sage.sqlite_store import SQLiteSageStore
from minions.sage.runtime import SageRuntime


def _principal(*permissions: str) -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="consolidation-session",
        permissions=frozenset(permissions),
    )


def _scope(principal: Principal) -> ScopeRef:
    return ScopeRef(scope_type=ScopeType.USER, scope_id=str(principal.user_id))


@pytest.mark.asyncio
async def test_duplicate_run_is_idempotent_approved_apply_and_rollback(
    tmp_path,
) -> None:
    principal = _principal(
        "sage.consolidation.approve",
        "sage.consolidation.apply",
        "sage.consolidation.rollback",
        "sage.policy.manage",
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        control = PolicyCenter(store)
        service = ConsolidationService(store, control, catalog)
        items = []
        for _ in range(2):
            items.append(
                await catalog.create_item(
                    principal,
                    kind=ItemKind.INSIGHT,
                    scope=_scope(principal),
                    title="Close the books safely",
                    content="Reconcile every source ledger before aggregation.",
                    state=ItemState.ACTIVE,
                ),
            )

        first = await service.consolidate(principal, local_date="2026-07-13")
        second = await service.consolidate(principal, local_date="2026-07-13")
        assert first == second
        candidates = await store.list_consolidation_candidates(principal)
        duplicate = next(
            value for value in candidates if value.kind is ConsolidationKind.DUPLICATE
        )

        with pytest.raises(SageConflict, match="requires approval"):
            await service.apply(principal, duplicate.candidate_id)
        approved = await service.approve(principal, duplicate.candidate_id)
        await control.set_policy(
            principal,
            capability=SageCapability.KNOWLEDGE_MERGE,
            mode=ActivationMode.OFF,
        )
        with pytest.raises(SageConflict, match="disabled"):
            await service.apply(principal, approved.candidate_id)
        await control.set_policy(
            principal,
            capability=SageCapability.KNOWLEDGE_MERGE,
            mode=ActivationMode.APPROVAL,
        )
        applied = await service.apply(principal, approved.candidate_id)
        assert applied.state is CandidateState.APPLIED
        states = {
            (await store.get_item(principal, item.item_id)).state for item in items
        }
        assert states == {ItemState.ACTIVE, ItemState.SUPERSEDED}

        rolled_back = await service.rollback(principal, applied.candidate_id)
        assert rolled_back.state is CandidateState.ROLLED_BACK
        restored = [await store.get_item(principal, item.item_id) for item in items]
        assert all(
            item is not None and item.state is ItemState.ACTIVE for item in restored
        )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_candidate_becomes_stale_when_a_source_changes(tmp_path) -> None:
    principal = _principal(
        "sage.consolidation.approve",
        "sage.consolidation.apply",
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        service = ConsolidationService(store, PolicyCenter(store), catalog)
        items = [
            await catalog.create_item(
                principal,
                kind=ItemKind.FACT,
                scope=_scope(principal),
                title="Shared duplicate",
                content="Same content",
                state=ItemState.ACTIVE,
            )
            for _ in range(2)
        ]
        await service.consolidate(principal, local_date="2026-07-14")
        candidate = next(
            value
            for value in await store.list_consolidation_candidates(principal)
            if value.kind is ConsolidationKind.DUPLICATE
        )
        approved = await service.approve(principal, candidate.candidate_id)
        changed = items[0].model_copy(update={"content": "Changed after review"})
        await store.save_item(principal, changed)

        with pytest.raises(SageConflict, match="sources changed"):
            await service.apply(principal, approved.candidate_id)
        stale = await store.get_consolidation_candidate(
            principal,
            approved.candidate_id,
        )
        assert stale is not None and stale.state is CandidateState.STALE
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_explicit_auto_mode_applies_only_low_risk_private_merge(tmp_path) -> None:
    principal = _principal(
        "sage.consolidation.apply",
        "sage.policy.manage",
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        control = PolicyCenter(store)
        service = ConsolidationService(store, control, catalog)
        for _ in range(2):
            await catalog.create_item(
                principal,
                kind=ItemKind.FACT,
                scope=_scope(principal),
                title="Private duplicate",
                content="A repeatable low-risk instruction",
                state=ItemState.ACTIVE,
            )
        await control.set_policy(
            principal,
            capability=SageCapability.NIGHTLY_CONSOLIDATION,
            mode=ActivationMode.AUTO,
        )
        await control.set_policy(
            principal,
            capability=SageCapability.KNOWLEDGE_MERGE,
            mode=ActivationMode.AUTO,
        )

        run = await service.consolidate(principal, local_date="2026-07-16")
        assert run is not None and run.stats["auto_applied"] == 1
        candidate = next(
            value
            for value in await store.list_consolidation_candidates(principal)
            if value.kind is ConsolidationKind.DUPLICATE
        )
        assert candidate.state is CandidateState.APPLIED
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_candidates_remain_tenant_isolated(tmp_path) -> None:
    principal = _principal()
    intruder = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        for _ in range(2):
            await catalog.create_item(
                principal,
                kind=ItemKind.FACT,
                scope=_scope(principal),
                title="Tenant private",
                content="Never cross tenant boundaries",
                state=ItemState.ACTIVE,
            )
        await ConsolidationService(
            store,
            PolicyCenter(store),
            catalog,
        ).consolidate(principal, local_date="2026-07-15")
        assert await store.list_consolidation_candidates(intruder) == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_semantic_similarity_creates_review_only_candidate(tmp_path) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        first = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=_scope(principal),
            title="客户月度对账流程",
            content="先核对源台账，再汇总差异。",
            state=ItemState.ACTIVE,
        )
        second = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=_scope(principal),
            title="月度客户对账操作",
            content="核验源台账后再汇总差异。",
            state=ItemState.ACTIVE,
        )

        run = await runtime.consolidation.consolidate(
            principal,
            local_date="2026-07-17",
        )

        assert run is not None
        candidate = next(
            value
            for value in await runtime.store.list_consolidation_candidates(principal)
            if set(value.source_ids) == {first.item_id, second.item_id}
        )
        assert candidate.kind is ConsolidationKind.DUPLICATE
        assert candidate.state is CandidateState.PROPOSED
        assert float(candidate.proposed_change["semantic_score"]) >= 0.5
    finally:
        await runtime.close()
