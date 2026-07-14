"""Tests for automatic case reflection and governed promotion."""

from uuid import uuid4

import pytest

from minions.sage.foundry import InsightFoundry
from minions.sage.models import (
    CaseOutcome,
    InsightState,
    Principal,
    ScopeRef,
    ScopeType,
)
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


@pytest.mark.asyncio
async def test_repeated_successes_form_candidate_but_do_not_self_approve(
    tmp_path,
) -> None:
    principal = Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="web",
        session_id="foundry-session",
    )
    scope = ScopeRef(
        scope_type=ScopeType.AGENT,
        scope_id=str(principal.agent_uid),
    )
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        lesson = "Reconcile source ledgers before aggregation."
        for number in range(2):
            turn = await runtime.begin(
                principal,
                scope=scope,
                user_input=f"Prepare monthly close {number}",
                domain="finance",
                process="monthly-close",
                task_type="close-package",
            )
            await runtime.finish(
                principal,
                turn,
                outcome=CaseOutcome.SUCCESS,
                agent_output="Close package accepted.",
                decision_summary=lesson,
            )

        await runtime.wait_for_growth()

        fingerprint = InsightFoundry.fingerprint_for(
            scope_type=ScopeType.AGENT.value,
            domain="finance",
            process="monthly-close",
            task_type="close-package",
            lesson=lesson,
        )
        candidates = await runtime.store.search_insights(
            principal,
            fingerprint,
            states=(InsightState.VALIDATING,),
        )
        assert len(candidates) == 1
        candidate = candidates[0]
        assert len(candidate.evidence_case_ids) == 2
        assert candidate.approved_by is None
        assert (await runtime.prepare(principal, "source ledgers")).source_ids == ()

        approver = principal.model_copy(
            update={"permissions": frozenset({"sage.insight.approve"})},
        )
        await runtime.growth.approve(approver, candidate.insight_id)
        active = await runtime.growth.activate(approver, candidate.insight_id)
        recalled = await runtime.prepare(principal, "source ledgers")
        assert recalled.source_ids == (active.published_item_id,)
    finally:
        await runtime.close()
