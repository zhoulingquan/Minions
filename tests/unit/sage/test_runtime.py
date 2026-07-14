"""End-to-end tests for the SAGE runtime facade."""

from uuid import uuid4

import pytest

from minions.sage.errors import SageAccessDenied
from minions.sage.models import (
    CaseOutcome,
    CaseState,
    FeedbackVerdict,
    GrowthJobState,
    ItemKind,
    ItemState,
    Principal,
    ScopeRef,
    ScopeType,
    TraceType,
)
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


def _principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="web",
        session_id="runtime-session",
    )


def _scope(principal: Principal) -> ScopeRef:
    return ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )


@pytest.mark.asyncio
async def test_runtime_begin_observe_finish_prepare_flow(tmp_path) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        assert runtime.control is not None
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="Prepare the monthly finance close.",
            domain="finance",
            process="monthly-close",
            goal="Prepare an accepted close package",
        )
        tool_trace = await runtime.observe(
            principal,
            turn,
            trace_type=TraceType.TOOL_RESULT,
            content="All source ledgers reconciled.",
            event_key="ledger-reconciliation-result",
        )
        finished = await runtime.finish(
            principal,
            turn,
            outcome=CaseOutcome.SUCCESS,
            agent_output="The close package is ready.",
            decision_summary="Reconciled ledgers before aggregation.",
            outcome_metrics={"accepted": True},
        )

        assert finished.state is CaseState.COMPLETED
        assert tool_trace.trace_id in finished.trace_ids
        traces = await runtime.store.list_traces(
            principal,
            case_id=turn.case_id,
        )
        assert [trace.trace_type for trace in traces] == [
            TraceType.USER_INPUT,
            TraceType.TOOL_RESULT,
            TraceType.AGENT_OUTPUT,
            TraceType.OUTCOME,
        ]

        item = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=_scope(principal),
            title="Monthly close lesson",
            content="For monthly close, reconcile ledgers before aggregation.",
            state=ItemState.ACTIVE,
        )
        pack = await runtime.prepare(principal, "monthly close")
        assert pack.source_ids == (item.item_id,)
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_runtime_state_survives_restart(tmp_path) -> None:
    principal = _principal()
    path = tmp_path / "sage.db"
    first = SageRuntime(SQLiteSageStore(path))
    await first.start()
    turn = await first.begin(
        principal,
        scope=_scope(principal),
        user_input="Durable task",
        goal="Persist the case",
    )
    await first.finish(
        principal,
        turn,
        outcome=CaseOutcome.PARTIAL,
        agent_output="Task partially completed.",
    )
    await first.close()

    second = SageRuntime(SQLiteSageStore(path))
    await second.start()
    try:
        case = await second.store.get_case(principal, turn.case_id)
        traces = await second.store.list_traces(
            principal,
            case_id=turn.case_id,
        )
        assert case is not None
        assert case.outcome is CaseOutcome.PARTIAL
        assert len(traces) == 3
    finally:
        await second.close()


@pytest.mark.asyncio
async def test_runtime_rejects_turn_identity_substitution(tmp_path) -> None:
    principal = _principal()
    intruder = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="Sensitive work",
        )
        with pytest.raises(SageAccessDenied, match="identity"):
            await runtime.observe(
                intruder,
                turn,
                trace_type=TraceType.FEEDBACK,
                content="Injected feedback",
            )
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_prepare_for_turn_persists_recall_receipt_trace(tmp_path) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        await runtime.catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=_scope(principal),
            title="Quarter close date",
            content="Quarter close is due on business day four.",
            state=ItemState.ACTIVE,
        )
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="When is quarter close?",
        )
        pack = await runtime.prepare_for_turn(
            principal,
            turn,
            "quarter close",
        )

        traces = await runtime.store.list_traces(
            principal,
            case_id=turn.case_id,
        )
        recall = next(trace for trace in traces if trace.trace_type is TraceType.RECALL)
        assert pack.receipt is not None
        assert recall.payload["receipt"]["receipt_id"] == str(
            pack.receipt.receipt_id,
        )
        assert recall.payload["receipt"]["selections"]
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_feedback_is_recorded_against_recall_receipt(tmp_path) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        item = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=_scope(principal),
            title="Current policy date",
            content="The policy was updated last week.",
            state=ItemState.ACTIVE,
        )
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="When was the policy updated?",
        )
        pack = await runtime.prepare_for_turn(principal, turn, "policy updated")
        receipt_id = pack.receipt.receipt_id
        source_id = item.item_id
        feedback = await runtime.feedback(
            principal,
            receipt_id=receipt_id,
            verdict=FeedbackVerdict.OUTDATED,
            source_id=source_id,
            comment="Policy changed last week.",
        )
        assert feedback.trace_type is TraceType.FEEDBACK
        assert feedback.payload["receipt_id"] == str(receipt_id)
        assert feedback.payload["source_id"] == str(source_id)
        assert feedback.payload["verdict"] == "outdated"
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_finish_durably_enqueues_growth_before_background_work(
    tmp_path,
    monkeypatch,
) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        monkeypatch.setattr(runtime, "_spawn_growth", lambda _principal: None)
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="Complete durable work",
        )
        await runtime.finish(
            principal,
            turn,
            outcome=CaseOutcome.SUCCESS,
            agent_output="Done",
        )
        jobs = await runtime.store.claim_growth_jobs(
            principal,
            worker_id="test-worker",
        )
        assert len(jobs) == 1
        assert jobs[0].state is GrowthJobState.LEASED
        assert jobs[0].payload["case_id"] == str(turn.case_id)
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_growth_worker_reflects_case_and_completes_job(
    tmp_path,
    monkeypatch,
) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        monkeypatch.setattr(runtime, "_spawn_growth", lambda _principal: None)
        reviewed: list = []

        async def reflect_case(origin, case_id):
            reviewed.append((origin, case_id))

        monkeypatch.setattr(runtime.foundry, "reflect_case", reflect_case)
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="Learn from this case",
        )
        await runtime.finish(
            principal,
            turn,
            outcome=CaseOutcome.SUCCESS,
            agent_output="Learned",
        )

        assert await runtime.run_growth_once(principal) is True
        assert reviewed[0][1] == turn.case_id
        assert reviewed[0][0] == principal
        assert await runtime.run_growth_once(principal) is False
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_pending_completion_bundle_rolls_back_as_one_unit(
    tmp_path,
    monkeypatch,
) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        monkeypatch.setattr(runtime, "_spawn_growth", lambda _principal: None)
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="Atomic business request",
        )

        def fail_job_write(_job):
            raise RuntimeError("simulated outbox failure")

        monkeypatch.setattr(runtime.store, "_growth_job_values", fail_job_write)
        with pytest.raises(RuntimeError, match="outbox failure"):
            await runtime.complete_turn_for_review(
                principal,
                turn,
                agent_output="This must roll back with the case.",
            )

        case = await runtime.store.get_case(principal, turn.case_id)
        traces = await runtime.store.list_traces(
            principal,
            case_id=turn.case_id,
        )
        assert case is not None
        assert case.state is CaseState.OPEN
        assert [trace.trace_type for trace in traces] == [TraceType.USER_INPUT]
        assert await runtime.store.list_growth_jobs(principal) == []
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_observed_and_verified_reflections_use_distinct_durable_jobs(
    tmp_path,
    monkeypatch,
) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        monkeypatch.setattr(runtime, "_spawn_growth", lambda _principal: None)
        turn = await runtime.begin(
            principal,
            scope=_scope(principal),
            user_input="Review then verify this work",
        )
        await runtime.complete_turn_for_review(
            principal,
            turn,
            agent_output="Prepared the requested result.",
        )
        await runtime.review_pending_case(
            principal,
            turn.case_id,
            outcome=CaseOutcome.SUCCESS,
            decision_summary="The result was accepted by the reviewer.",
        )

        jobs = await runtime.store.list_growth_jobs(principal)
        assert {job.payload["stage"] for job in jobs} == {
            "observed",
            "verified",
        }
    finally:
        await runtime.close()
