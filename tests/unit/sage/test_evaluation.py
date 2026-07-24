# -*- coding: utf-8 -*-
"""Tests for feedback signals and bounded SAGE utility learning."""

from uuid import uuid4

import pytest

from minions.sage.catalog import SageCatalog
from minions.sage.control import PolicyCenter
from minions.sage.evaluation import EvaluationEngine
from minions.sage.models import (
    ActivationMode,
    FeedbackVerdict,
    ItemKind,
    ItemState,
    Principal,
    SageCapability,
    ScopeRef,
    ScopeType,
    SignalKind,
)
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*permissions: str, tenant_id=None) -> Principal:
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="evaluation-session",
        permissions=frozenset(permissions),
    )


@pytest.mark.asyncio
async def test_feedback_signal_is_idempotent_and_tenant_isolated(
    tmp_path,
) -> None:
    owner = _principal()
    intruder = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        evaluator = EvaluationEngine(
            store,
            PolicyCenter(store),
            SageCatalog(store),
        )
        source_id = uuid4()
        event_id = uuid4()
        first = await evaluator.record_feedback(
            owner,
            event_id=event_id,
            receipt_id=uuid4(),
            source_id=source_id,
            verdict=FeedbackVerdict.USEFUL,
        )
        repeated = await evaluator.record_feedback(
            owner,
            event_id=event_id,
            receipt_id=uuid4(),
            source_id=source_id,
            verdict=FeedbackVerdict.WRONG,
        )

        assert first.sample_count == 1
        assert repeated.sample_count == 1
        signals = await store.list_knowledge_signals(
            owner,
            source_id=source_id,
        )
        assert len(signals) == 1
        assert signals[0].kind is SignalKind.FEEDBACK
        assert await store.list_knowledge_signals(intruder) == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_shadow_learning_proposes_but_does_not_change_item(
    tmp_path,
) -> None:
    principal = _principal()
    scope = ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        item = await catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=scope,
            title="Invoice lesson",
            content="Review invoice exceptions before totals.",
            state=ItemState.ACTIVE,
        )
        evaluator = EvaluationEngine(store, PolicyCenter(store), catalog)
        quality = None
        for _ in range(2):
            quality = await evaluator.record_feedback(
                principal,
                event_id=uuid4(),
                receipt_id=uuid4(),
                source_id=item.item_id,
                verdict=FeedbackVerdict.USEFUL,
            )

        assert quality is not None
        assert quality.proposed_utility > item.utility
        assert quality.applied_item_id is None
        assert (
            await store.get_item(principal, item.item_id)
        ).utility == item.utility
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_auto_learning_creates_bounded_active_item_version(
    tmp_path,
) -> None:
    principal = _principal("sage.policy.manage")
    scope = ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        control = PolicyCenter(store)
        await control.set_policy(
            principal,
            capability=SageCapability.FEEDBACK_LEARNING,
            mode=ActivationMode.AUTO,
        )
        item = await catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=scope,
            title="Useful close lesson",
            content="Reconcile ledgers before aggregation.",
            state=ItemState.ACTIVE,
        )
        evaluator = EvaluationEngine(store, control, catalog)
        quality = None
        for _ in range(2):
            quality = await evaluator.record_feedback(
                principal,
                event_id=uuid4(),
                receipt_id=uuid4(),
                source_id=item.item_id,
                verdict=FeedbackVerdict.USEFUL,
            )

        assert quality is not None and quality.applied_item_id is not None
        original = await store.get_item(principal, item.item_id)
        applied = await store.get_item(principal, quality.applied_item_id)
        assert original is not None and original.state is ItemState.SUPERSEDED
        assert applied is not None and applied.state is ItemState.ACTIVE
        assert applied.version == 2
        assert 0 < applied.utility <= 0.2
    finally:
        await store.close()
