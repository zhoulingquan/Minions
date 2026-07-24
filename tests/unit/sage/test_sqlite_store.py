# -*- coding: utf-8 -*-
"""Durability and isolation tests for the SAGE SQLite adapter."""

import asyncio
import threading
from uuid import uuid4

import pytest

from minions.sage.errors import SageAccessDenied, SageConflict
from minions.sage.models import (
    ActivationMode,
    CapabilityPolicy,
    Classification,
    GrowthJob,
    GrowthJobState,
    GrowthJobType,
    ItemKind,
    ItemState,
    KnowledgeItem,
    Principal,
    ScopeRef,
    ScopeType,
    SageCapability,
    Trace,
    TraceType,
)
from minions.sage.sqlite_store import SQLiteSageStore


@pytest.mark.asyncio
async def test_cancelled_sqlite_call_drains_worker_before_close(
    tmp_path,
) -> None:
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    started = threading.Event()
    release = threading.Event()

    def slow_read() -> int:
        started.set()
        release.wait(timeout=2)
        store._connection().execute("SELECT 1").fetchone()
        return 1

    task = asyncio.create_task(store._call(slow_read))
    await asyncio.to_thread(started.wait, 1)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await store.close()


def _principal(*, tenant_id=None, **overrides) -> Principal:
    values = {
        "tenant_id": tenant_id or uuid4(),
        "user_id": uuid4(),
        "agent_uid": uuid4(),
        "source": "web",
        "session_id": "session-1",
    }
    values.update(overrides)
    return Principal(**values)


@pytest.mark.asyncio
async def test_start_creates_schema_and_enables_wal(tmp_path) -> None:
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        assert await store.journal_mode() == "wal"
        assert {
            "sage_trace",
            "sage_case",
            "sage_item",
            "sage_insight",
            "sage_playbook",
            "sage_item_embedding",
            "sage_growth_job",
            "sage_capability_policy",
        }.issubset(await store.table_names())
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_trace_append_is_idempotent_per_tenant(tmp_path) -> None:
    store = SQLiteSageStore(tmp_path / "sage.db")
    principal = _principal()
    await store.start()
    try:
        first = Trace.from_principal(
            principal,
            event_key="request-1:user",
            trace_type=TraceType.USER_INPUT,
            content="hello",
        )
        duplicate = Trace.from_principal(
            principal,
            event_key="request-1:user",
            trace_type=TraceType.USER_INPUT,
            content="different retry payload",
        )

        stored_first = await store.append_trace(principal, first)
        stored_duplicate = await store.append_trace(principal, duplicate)

        assert stored_duplicate.trace_id == stored_first.trace_id
        traces = await store.list_traces(principal)
        assert [item.content for item in traces] == ["hello"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_store_rejects_cross_tenant_write(tmp_path) -> None:
    store = SQLiteSageStore(tmp_path / "sage.db")
    owner = _principal()
    intruder = _principal()
    trace = Trace.from_principal(
        owner,
        event_key="owner-event",
        trace_type=TraceType.USER_INPUT,
    )
    await store.start()
    try:
        with pytest.raises(SageAccessDenied):
            await store.append_trace(intruder, trace)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_reopen_preserves_traces(tmp_path) -> None:
    path = tmp_path / "sage.db"
    principal = _principal()
    first = SQLiteSageStore(path)
    await first.start()
    await first.append_trace(
        principal,
        Trace.from_principal(
            principal,
            event_key="durable",
            trace_type=TraceType.OUTCOME,
            content="accepted",
        ),
    )
    await first.close()

    second = SQLiteSageStore(path)
    await second.start()
    try:
        traces = await second.list_traces(principal)
        assert len(traces) == 1
        assert traces[0].content == "accepted"
    finally:
        await second.close()


@pytest.mark.asyncio
async def test_item_search_is_tenant_and_scope_filtered(tmp_path) -> None:
    path = tmp_path / "sage.db"
    tenant_a = uuid4()
    tenant_b = uuid4()
    alice = _principal(tenant_id=tenant_a)
    bob = _principal(tenant_id=tenant_b)
    store = SQLiteSageStore(path)
    await store.start()
    try:
        await store.save_item(
            alice,
            KnowledgeItem(
                tenant_id=tenant_a,
                kind=ItemKind.FACT,
                scope=ScopeRef(
                    scope_type=ScopeType.USER,
                    scope_id=str(alice.user_id),
                ),
                title="Monthly report deadline",
                content="The monthly report is due on the fifth working day.",
                state=ItemState.ACTIVE,
            ),
        )
        await store.save_item(
            bob,
            KnowledgeItem(
                tenant_id=tenant_b,
                kind=ItemKind.FACT,
                scope=ScopeRef(
                    scope_type=ScopeType.USER,
                    scope_id=str(bob.user_id),
                ),
                title="Other report deadline",
                content="The monthly report is due on the tenth day.",
                state=ItemState.ACTIVE,
            ),
        )

        alice_hits = await store.search_items(alice, "monthly report")
        bob_hits = await store.search_items(bob, "monthly report")

        assert [item.content for item in alice_hits] == [
            "The monthly report is due on the fifth working day.",
        ]
        assert [item.content for item in bob_hits] == [
            "The monthly report is due on the tenth day.",
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_trace_event_key_cannot_cross_user_boundary(tmp_path) -> None:
    tenant_id = uuid4()
    owner = _principal(tenant_id=tenant_id)
    other = _principal(tenant_id=tenant_id)
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        await store.append_trace(
            owner,
            Trace.from_principal(
                owner,
                event_key="shared-key",
                trace_type=TraceType.USER_INPUT,
                content="owner secret",
            ),
        )
        with pytest.raises(SageAccessDenied, match="another user"):
            await store.append_trace(
                other,
                Trace.from_principal(
                    other,
                    event_key="shared-key",
                    trace_type=TraceType.USER_INPUT,
                    content="collision",
                ),
            )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_cross_tenant_item_id_collision_cannot_poison_search(
    tmp_path,
) -> None:
    alice = _principal()
    bob = _principal()
    shared_id = uuid4()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        original = KnowledgeItem(
            item_id=shared_id,
            tenant_id=alice.tenant_id,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(alice.user_id),
            ),
            title="Protected closing rule",
            content="protected original content",
            state=ItemState.ACTIVE,
        )
        await store.save_item(alice, original)
        collision = KnowledgeItem(
            item_id=shared_id,
            tenant_id=bob.tenant_id,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(bob.user_id),
            ),
            title="Protected collision",
            content="poisoned replacement content",
            state=ItemState.ACTIVE,
        )
        with pytest.raises(SageConflict, match="another tenant"):
            await store.save_item(bob, collision)

        hits = await store.search_items(alice, "protected")
        assert [item.content for item in hits] == [
            "protected original content",
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_restricted_items_require_classification_permission(
    tmp_path,
) -> None:
    base = _principal()
    privileged = base.model_copy(
        update={
            "permissions": frozenset(
                {
                    "sage.classification.restricted.read",
                    "sage.classification.restricted.write",
                },
            ),
        },
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        restricted = KnowledgeItem(
            tenant_id=base.tenant_id,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(base.user_id),
            ),
            classification=Classification.RESTRICTED,
            title="Restricted payroll detail",
            content="restricted payroll content",
            state=ItemState.ACTIVE,
        )
        await store.save_item(privileged, restricted)
        assert await store.search_items(base, "payroll") == []
        hits = await store.search_items(privileged, "payroll")
        assert [item.item_id for item in hits] == [restricted.item_id]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_list_items_filters_kind_without_query(tmp_path) -> None:
    principal = _principal()
    scope = ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        anchor = KnowledgeItem(
            tenant_id=principal.tenant_id,
            kind=ItemKind.ANCHOR,
            scope=scope,
            title="Closing control",
            content="Never post an unbalanced journal.",
            state=ItemState.ACTIVE,
        )
        await store.save_item(principal, anchor)
        await store.save_item(
            principal,
            anchor.model_copy(
                update={
                    "item_id": uuid4(),
                    "kind": ItemKind.FACT,
                    "title": "Closing fact",
                },
            ),
        )

        items = await store.list_items(
            principal,
            states=(ItemState.ACTIVE,),
            kinds=(ItemKind.ANCHOR,),
        )
        assert [item.item_id for item in items] == [anchor.item_id]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_growth_outbox_is_idempotent_and_claimable(tmp_path) -> None:
    principal = _principal()
    job = GrowthJob(
        job_id=uuid4(),
        tenant_id=principal.tenant_id,
        job_type=GrowthJobType.REFLECT_CASE,
        payload={"case_id": str(uuid4())},
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        first = await store.enqueue_growth_job(principal, job)
        duplicate = await store.enqueue_growth_job(
            principal,
            job.model_copy(update={"payload": {"case_id": "changed"}}),
        )
        assert duplicate.payload == first.payload

        claimed = await store.claim_growth_jobs(
            principal,
            worker_id="worker-1",
            limit=1,
            lease_seconds=30,
        )
        assert [item.job_id for item in claimed] == [job.job_id]
        assert claimed[0].state is GrowthJobState.LEASED
        assert claimed[0].attempts == 1
        assert (
            await store.claim_growth_jobs(
                principal,
                worker_id="worker-2",
                limit=1,
            )
            == []
        )

        completed = await store.complete_growth_job(
            principal,
            job.job_id,
            worker_id="worker-1",
        )
        assert completed.state is GrowthJobState.COMPLETED
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_growth_outbox_rejects_cross_tenant_access(tmp_path) -> None:
    owner = _principal()
    intruder = _principal()
    job = GrowthJob(
        tenant_id=owner.tenant_id,
        job_type=GrowthJobType.REFLECT_CASE,
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        await store.enqueue_growth_job(owner, job)
        with pytest.raises(SageAccessDenied):
            await store.enqueue_growth_job(intruder, job)
        assert (
            await store.claim_growth_jobs(
                intruder,
                worker_id="intruder",
            )
            == []
        )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_capability_policy_is_versioned_and_scope_addressable(
    tmp_path,
) -> None:
    principal = _principal()
    scope = ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )
    policy = CapabilityPolicy.create(
        tenant_id=principal.tenant_id,
        capability=SageCapability.FEEDBACK_LEARNING,
        mode=ActivationMode.SHADOW,
        scope=scope,
        modified_by=principal.user_id,
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        await store.save_capability_policy(principal, policy)
        updated = policy.model_copy(
            update={"mode": ActivationMode.AUTO, "version": 2},
        )
        await store.save_capability_policy(principal, updated)

        restored = await store.get_capability_policy(
            principal,
            policy.policy_id,
        )
        assert restored == updated
        assert await store.list_capability_policies(
            principal,
            capability=SageCapability.FEEDBACK_LEARNING,
        ) == [updated]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_capability_policy_rejects_cross_tenant_access(tmp_path) -> None:
    owner = _principal()
    intruder = _principal()
    policy = CapabilityPolicy.default_for(
        owner.tenant_id,
        SageCapability.NIGHTLY_CONSOLIDATION,
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        await store.save_capability_policy(owner, policy)
        with pytest.raises(SageAccessDenied):
            await store.save_capability_policy(intruder, policy)
        assert (
            await store.get_capability_policy(
                intruder,
                policy.policy_id,
            )
            is None
        )
        assert await store.list_capability_policies(intruder) == []
    finally:
        await store.close()
