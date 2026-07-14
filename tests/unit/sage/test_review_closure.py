from __future__ import annotations

from uuid import uuid4

import pytest

from minions.sage.models import (
    CaseOutcome,
    CaseState,
    InsightState,
    Principal,
    ScopeRef,
    ScopeType,
    TraceType,
)
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


@pytest.mark.asyncio
async def test_authenticated_review_closes_case_and_forms_draft(tmp_path):
    principal = Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="http",
        session_id="review-session",
        permissions=frozenset({"sage.insight.approve"}),
    )
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        turn = await runtime.begin(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            user_input="完成月度对账",
            process="monthly-close",
            goal="形成已核验的月结包",
        )
        await runtime.observe(
            principal,
            turn,
            trace_type=TraceType.AGENT_OUTPUT,
            content="先核对源台账，再汇总差异。",
        )
        await runtime.cases.mark_pending_review(principal, turn.case_id)

        case, insight = await runtime.review_pending_case(
            principal,
            turn.case_id,
            outcome=CaseOutcome.SUCCESS,
            decision_summary="先核对源台账，再汇总差异。",
        )

        assert case.state is CaseState.COMPLETED
        assert insight is not None and insight.state is InsightState.DRAFT
        assert (await runtime.store.list_cases(principal))[0].case_id == case.case_id
        assert (await runtime.store.list_insights(principal))[0].insight_id == insight.insight_id
        traces = await runtime.store.list_traces(principal, case_id=case.case_id)
        assert traces[-1].payload["attestation"] == "authenticated-review"
    finally:
        await runtime.close()
