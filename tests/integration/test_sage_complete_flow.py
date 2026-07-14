"""Complete governed SAGE evolution, recovery, and isolation flow."""

from uuid import uuid4

import pytest

from minions.sage.identity import SAGE_ADMIN_PERMISSIONS
from minions.sage.models import (
    ActivationMode,
    CaseOutcome,
    CandidateState,
    ConsolidationKind,
    FeedbackVerdict,
    ItemKind,
    ItemState,
    InsightState,
    Principal,
    SageCapability,
    ScopeRef,
    ScopeType,
)
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*, tenant_id=None) -> Principal:
    resolved_tenant = tenant_id or uuid4()
    return Principal(
        tenant_id=resolved_tenant,
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="integration",
        session_id="complete-flow",
        permissions=SAGE_ADMIN_PERMISSIONS,
    )


@pytest.mark.asyncio
async def test_shadow_approval_auto_restart_and_tenant_isolation(tmp_path) -> None:
    path = tmp_path / "sage.db"
    principal = _principal()
    scope = ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )
    first = SageRuntime(SQLiteSageStore(path))
    await first.start()
    items = []
    try:
        for _ in range(2):
            items.append(
                await first.catalog.create_item(
                    principal,
                    kind=ItemKind.INSIGHT,
                    scope=scope,
                    title="Month-end close lesson",
                    content="Reconcile source ledgers before aggregation.",
                    state=ItemState.ACTIVE,
                    structured_data={
                        "applicability": {
                            "domain": "finance",
                            "process": "month-end-close",
                        },
                    },
                ),
            )

        pack = await first.prepare(principal, "month-end close ledgers")
        assert items[0].item_id in pack.source_ids

        # Default feedback learning is SHADOW: evidence accumulates without a
        # catalog mutation.
        for verdict in (FeedbackVerdict.USEFUL, FeedbackVerdict.USEFUL):
            await first.evaluation.record_feedback(
                principal,
                event_id=uuid4(),
                receipt_id=pack.receipt.receipt_id,
                source_id=items[0].item_id,
                verdict=verdict,
            )
        shadow_item = await first.store.get_item(principal, items[0].item_id)
        assert shadow_item is not None and shadow_item.state is ItemState.ACTIVE
        assert shadow_item.utility == 0

        # Move the low-risk capability to AUTO only after shadow evidence.
        await first.control.set_policy(
            principal,
            capability=SageCapability.FEEDBACK_LEARNING,
            mode=ActivationMode.AUTO,
        )
        quality = await first.evaluation.recalculate(
            principal,
            items[0].item_id,
        )
        assert quality.applied_item_id is not None

        # Jobs are durable and deterministic. Simulate process shutdown before
        # a worker claims them.
        jobs = await first.maintenance.schedule_due(
            principal,
            local_date="2026-07-13",
        )
        assert len(jobs) == 3
    finally:
        await first.close()

    second = SageRuntime(SQLiteSageStore(path))
    await second.start()
    try:
        processed = 0
        while await second.run_growth_once(principal):
            processed += 1
        assert processed == 3

        candidates = await second.store.list_consolidation_candidates(principal)
        duplicate = next(
            candidate
            for candidate in candidates
            if candidate.kind is ConsolidationKind.DUPLICATE
        )
        approved = await second.consolidation.approve(
            principal,
            duplicate.candidate_id,
        )
        applied = await second.consolidation.apply(
            principal,
            approved.candidate_id,
        )
        assert applied.state is CandidateState.APPLIED
        rolled_back = await second.consolidation.rollback(
            principal,
            applied.candidate_id,
        )
        assert rolled_back.state is CandidateState.ROLLED_BACK

        snapshot = await second.metrics.snapshot(principal)
        assert snapshot.completed_jobs == 3
        assert snapshot.completed_runs == 1
        assert snapshot.rolled_back_candidates == 1

        intruder = _principal()
        assert await second.store.list_items(intruder) == []
        assert await second.store.list_consolidation_candidates(intruder) == []
        assert (await second.metrics.snapshot(intruder)).knowledge_total == 0
    finally:
        await second.close()


@pytest.mark.asyncio
async def test_normal_work_grows_into_recallable_chinese_experience(
    tmp_path,
    monkeypatch,
) -> None:
    """Prove the real work-to-review-to-publish-to-recall learning loop."""

    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "operational-loop.db"))
    await runtime.start()
    try:
        # Keep the test deterministic while still exercising the durable jobs.
        monkeypatch.setattr(runtime, "_spawn_growth", lambda _principal: None)
        scope = ScopeRef(
            scope_type=ScopeType.USER,
            scope_id=str(principal.user_id),
        )
        verified_summary = "先核对源台账余额，再汇总异常差异。"
        verified_insights = []

        for user_input in (
            "完成本月客户应收对账",
            "复核下个月度客户往来账",
        ):
            turn = await runtime.begin(
                principal,
                scope=scope,
                user_input=user_input,
                domain="财务",
                process="月度应收对账",
                task_type="客户账务复核",
                goal="形成可确认的客户对账结果",
            )
            pending = await runtime.complete_turn_for_review(
                principal,
                turn,
                agent_output="已逐项核验来源台账，并整理异常差异。",
            )
            assert pending.state.value == "pending_review"
            assert await runtime.run_growth_once(principal) is True

            provisional = next(
                insight
                for insight in await runtime.store.list_insights(principal)
                if turn.case_id in insight.evidence_case_ids
                and insight.state is InsightState.OBSERVED
            )
            assert provisional.applicability["provisional"] is True

            _, verified = await runtime.review_pending_case(
                principal,
                turn.case_id,
                outcome=CaseOutcome.SUCCESS,
                decision_summary=verified_summary,
            )
            assert verified is not None
            verified_insights.append(verified)

        candidate = verified_insights[-1]
        assert candidate.state is InsightState.VALIDATING
        assert len(candidate.evidence_case_ids) == 2
        approved = await runtime.growth.approve(principal, candidate.insight_id)
        active = await runtime.growth.activate(principal, approved.insight_id)
        assert active.published_item_id is not None

        pack = await runtime.prepare(
            principal,
            "客户月末核账时怎样先检查来源账本并整理差额？",
        )
        assert active.published_item_id in pack.source_ids
        assert pack.receipt is not None
        assert pack.receipt.ranking_mode == "hybrid"

        intruder = _principal()
        assert await runtime.store.list_cases(intruder) == []
        assert await runtime.store.list_insights(intruder) == []
        assert await runtime.store.list_items(intruder) == []
    finally:
        await runtime.close()
