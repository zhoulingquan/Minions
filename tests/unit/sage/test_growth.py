"""Tests for SAGE's governed learning lifecycle."""

from uuid import UUID, uuid4

import pytest

from minions.sage.errors import SageAccessDenied, SageConflict, SageInvalidTransition
from minions.sage.growth import GrowthCycle
from minions.sage.models import (
    CaseOutcome,
    CaseRecord,
    CaseState,
    InsightState,
    Principal,
    RiskLevel,
    ScopeRef,
    ScopeType,
)
from minions.sage.recall import RecallPlanner
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*permissions: str) -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="web",
        session_id="growth-session",
        permissions=frozenset(permissions),
    )


def _agent_scope(principal: Principal) -> ScopeRef:
    return ScopeRef(scope_type=ScopeType.AGENT, scope_id=str(principal.agent_uid))


async def _evidence_cases(
    store: SQLiteSageStore,
    principal: Principal,
    count: int,
) -> tuple[UUID, ...]:
    ids = []
    for number in range(count):
        case = CaseRecord(
            tenant_id=principal.tenant_id,
            owner_user_id=principal.user_id,
            agent_uid=principal.agent_uid,
            scope=_agent_scope(principal),
            goal=f"Verified case {number}",
            state=CaseState.COMPLETED,
            outcome=CaseOutcome.SUCCESS,
        )
        await store.save_case(principal, case)
        ids.append(case.case_id)
    return tuple(ids)


@pytest.mark.asyncio
async def test_reflection_cannot_activate_its_own_draft(tmp_path) -> None:
    principal = _principal("sage.insight.approve")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        growth = GrowthCycle(store)
        draft = await growth.propose(
            principal,
            scope=_agent_scope(principal),
            title="Reconcile first",
            content="Reconcile source systems before aggregation.",
            evidence_case_ids=(uuid4(), uuid4()),
        )
        with pytest.raises(SageInvalidTransition):
            await growth.activate(principal, draft.insight_id)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_duplicate_case_ids_do_not_satisfy_independent_evidence(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        (case_id,) = await _evidence_cases(store, principal, 1)
        growth = GrowthCycle(store)
        draft = await growth.propose(
            principal,
            scope=_agent_scope(principal),
            title="Repeated observation",
            content="One case cannot count twice.",
            evidence_case_ids=(case_id, case_id),
        )
        assert draft.evidence_case_ids == (case_id,)
        with pytest.raises(SageConflict, match="independent"):
            await growth.start_validation(principal, draft.insight_id)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_low_risk_insight_follows_validation_approval_activation(
    tmp_path,
) -> None:
    principal = _principal("sage.insight.approve")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        growth = GrowthCycle(store)
        evidence = await _evidence_cases(store, principal, 2)
        draft = await growth.propose(
            principal,
            scope=_agent_scope(principal),
            title="Useful lesson",
            content="A lesson supported by two completed cases.",
            evidence_case_ids=evidence,
            confidence=0.8,
        )
        validating = await growth.start_validation(principal, draft.insight_id)
        approved = await growth.approve(principal, validating.insight_id)
        active = await growth.activate(principal, approved.insight_id)

        assert validating.state is InsightState.VALIDATING
        assert approved.state is InsightState.APPROVED
        assert approved.approved_by == principal.user_id
        assert active.state is InsightState.ACTIVE
        assert active.published_item_id is not None
        pack = await RecallPlanner(store).prepare(principal, "Useful lesson")
        assert pack.source_ids == (active.published_item_id,)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_high_risk_insight_needs_separate_publish_authority(tmp_path) -> None:
    approver = _principal("sage.insight.approve")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        growth = GrowthCycle(store)
        evidence = await _evidence_cases(store, approver, 2)
        draft = await growth.propose(
            approver,
            scope=_agent_scope(approver),
            title="High-risk automation",
            content="Changes financial approval behavior.",
            evidence_case_ids=evidence,
            risk_level=RiskLevel.HIGH,
        )
        validating = await growth.start_validation(approver, draft.insight_id)
        approved = await growth.approve(approver, validating.insight_id)
        with pytest.raises(SageAccessDenied, match="high_risk"):
            await growth.activate(approver, approved.insight_id)

        publisher = approver.model_copy(
            update={
                "permissions": frozenset(
                    {"sage.insight.approve", "sage.insight.publish.high_risk"},
                ),
            },
        )
        active = await growth.activate(publisher, approved.insight_id)
        assert active.state is InsightState.ACTIVE
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_active_insight_can_be_rolled_back_but_not_reactivated(tmp_path) -> None:
    principal = _principal("sage.insight.approve", "sage.insight.rollback")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        growth = GrowthCycle(store)
        evidence = await _evidence_cases(store, principal, 2)
        draft = await growth.propose(
            principal,
            scope=_agent_scope(principal),
            title="Reversible lesson",
            content="Published experience remains reversible.",
            evidence_case_ids=evidence,
        )
        await growth.start_validation(principal, draft.insight_id)
        await growth.approve(principal, draft.insight_id)
        active = await growth.activate(principal, draft.insight_id)
        before = await RecallPlanner(store).prepare(principal, "Reversible lesson")
        assert before.source_ids == (active.published_item_id,)
        rolled_back = await growth.rollback(principal, draft.insight_id)
        assert rolled_back.state is InsightState.ROLLED_BACK
        after = await RecallPlanner(store).prepare(principal, "Reversible lesson")
        assert after.source_ids == ()

        with pytest.raises(SageInvalidTransition):
            await growth.activate(principal, draft.insight_id)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_revising_validating_insight_returns_it_to_draft(tmp_path) -> None:
    principal = _principal("sage.insight.approve")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        growth = GrowthCycle(store)
        evidence = await _evidence_cases(store, principal, 2)
        draft = await growth.propose(
            principal,
            scope=_agent_scope(principal),
            title="旧标题",
            content="旧心得",
            evidence_case_ids=evidence,
        )
        validating = await growth.start_validation(principal, draft.insight_id)

        revised = await growth.revise(
            principal,
            validating.insight_id,
            title="发票复核经验",
            content="先核对合同与验收证据，再确认发票金额。",
            applicability={"process": "发票复核"},
        )

        assert revised.state is InsightState.DRAFT
        assert revised.version == validating.version + 1
        assert revised.approved_by is None
        assert revised.applicability == {"process": "发票复核"}
    finally:
        await store.close()
