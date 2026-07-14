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
from minions.sage.reflection import ReflectionEngine
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


def _principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="reflection-session",
        permissions=frozenset({"sage.insight.approve"}),
    )


@pytest.mark.asyncio
async def test_pending_case_creates_non_recallable_observed_draft(tmp_path) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        turn = await runtime.begin(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            user_input="为客户准备月度对账包",
            domain="财务",
            process="月度对账",
            task_type="交付检查",
            goal="交付无差异的对账包",
        )
        await runtime.observe(
            principal,
            turn,
            trace_type=TraceType.TOOL_RESULT,
            content="源台账核对完成，发现并修正两处差异。",
        )
        await runtime.observe(
            principal,
            turn,
            trace_type=TraceType.AGENT_OUTPUT,
            content="已先核对源台账，再汇总差异并生成交付包。",
            event_key=f"turn:{turn.turn_id}:agent-output",
        )
        case = await runtime.cases.mark_pending_review(principal, turn.case_id)

        insight = await runtime.foundry.reflect_case(principal, case.case_id)

        assert insight is not None
        assert insight.state is InsightState.OBSERVED
        assert insight.evidence_case_ids == (case.case_id,)
        assert insight.applicability["provisional"] is True
        assert "业务目标：交付无差异的对账包" in insight.content
        assert "已采取的做法" in insight.content
        assert "等待有权限的成员确认" in insight.content
        assert (await runtime.prepare(principal, "月度客户账务核验")).source_ids == ()
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_authenticated_review_promotes_observed_draft_to_verified(
    tmp_path,
) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        turn = await runtime.begin(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            user_input="复核供应商发票",
            domain="财务",
            process="发票复核",
            task_type="合规检查",
        )
        await runtime.observe(
            principal,
            turn,
            trace_type=TraceType.AGENT_OUTPUT,
            content="逐项核对合同、验收单和发票金额。",
            event_key=f"turn:{turn.turn_id}:agent-output",
        )
        await runtime.cases.mark_pending_review(principal, turn.case_id)
        observed = await runtime.foundry.reflect_case(principal, turn.case_id)
        assert observed is not None and observed.state is InsightState.OBSERVED

        case, verified = await runtime.review_pending_case(
            principal,
            turn.case_id,
            outcome=CaseOutcome.SUCCESS,
            decision_summary="先核对合同与验收证据，再确认发票金额。",
        )

        assert case.state is CaseState.COMPLETED
        assert verified is not None
        assert verified.insight_id == observed.insight_id
        assert verified.state is InsightState.DRAFT
        assert verified.applicability["provisional"] is False
        assert verified.version == observed.version + 1
        assert "先核对合同与验收证据" in verified.content
    finally:
        await runtime.close()


def test_reflection_redacts_secret_like_lines() -> None:
    engine = ReflectionEngine(None)  # type: ignore[arg-type]
    assert engine.safe_excerpt("结果正常\napi_key=secret-value\n继续执行") == (
        "结果正常\n[敏感内容已省略]\n继续执行"
    )
