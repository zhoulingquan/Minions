"""Application-facing facade for the standalone SAGE subsystem."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field

from .casebook import CaseBook
from .catalog import SageCatalog
from .control import PolicyCenter
from .errors import SageAccessDenied, SageConflict, SageNotFound
from .evaluation import EvaluationEngine
from .embeddings import EmbeddingService, build_embedding_service_from_env
from .foundry import InsightFoundry
from .growth import GrowthCycle
from .maintenance import MaintenanceCoordinator
from .metrics import SageMetrics
from .models import (
    ActionPack,
    CaseOutcome,
    CaseRecord,
    CaseState,
    Classification,
    FeedbackVerdict,
    GrowthJob,
    GrowthJobType,
    InsightDraft,
    Principal,
    RecallQuery,
    RiskLevel,
    SageCapability,
    ScopeRef,
    Trace,
    TraceType,
    utc_now,
)
from .recall import RecallPlanner
from .consolidation import ConsolidationService
from .store import SageStore
from .semantic import SemanticIndexer

logger = logging.getLogger(__name__)


class SageTurn(BaseModel):
    """Immutable identity handle for one SAGE-observed agent turn."""

    model_config = ConfigDict(frozen=True)

    turn_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    user_id: UUID
    agent_uid: UUID
    session_id: str
    case_id: UUID
    scope: ScopeRef


class SageRuntime:
    """Coordinates TraceBook, CaseBook, GrowthCycle, and RecallPlanner."""

    def __init__(
        self,
        store: SageStore,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.store = store
        self.embeddings = embedding_service or build_embedding_service_from_env()
        self.semantic = (
            SemanticIndexer(store, self.embeddings)
            if self.embeddings is not None
            else None
        )
        self.cases = CaseBook(store)
        self.catalog = SageCatalog(store, self.semantic)
        self.control = PolicyCenter(store)
        self.evaluation = EvaluationEngine(store, self.control, self.catalog)
        self.growth = GrowthCycle(store, self.semantic)
        self.foundry = InsightFoundry(store, self.growth)
        self.recall = RecallPlanner(store, self.embeddings)
        self.consolidation = ConsolidationService(
            store,
            self.control,
            self.catalog,
            self.semantic,
            self.embeddings,
        )
        self.maintenance = MaintenanceCoordinator(store, self.control)
        self.metrics = SageMetrics(store)
        self._worker_id = f"sage-runtime:{uuid4()}"
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._growth_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.store.start()

    async def close(self) -> None:
        tasks = tuple(self._background_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.store.close()

    async def wait_for_growth(self) -> None:
        """Wait until the reflection work already scheduled by this runtime ends."""

        while self._background_tasks:
            await asyncio.gather(
                *tuple(self._background_tasks),
                return_exceptions=True,
            )

    async def begin(
        self,
        principal: Principal,
        *,
        scope: ScopeRef,
        user_input: str,
        domain: str = "",
        process: str = "",
        task_type: str = "",
        goal: str = "",
        constraints: dict[str, Any] | None = None,
        scenario: dict[str, Any] | None = None,
        classification: Classification = Classification.INTERNAL,
    ) -> SageTurn:
        self._spawn_growth(principal)
        case = await self.cases.open_case(
            principal,
            scope=scope,
            domain=domain,
            process=process,
            task_type=task_type,
            goal=goal,
            constraints=constraints,
            scenario=scenario,
            classification=classification,
        )
        turn = SageTurn(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            agent_uid=principal.agent_uid,
            session_id=principal.session_id,
            case_id=case.case_id,
            scope=scope,
        )
        await self.observe(
            principal,
            turn,
            trace_type=TraceType.USER_INPUT,
            content=user_input,
            event_key=f"turn:{turn.turn_id}:user-input",
            classification=classification,
        )
        return turn

    async def observe(
        self,
        principal: Principal,
        turn: SageTurn,
        *,
        trace_type: TraceType,
        content: str = "",
        payload: dict[str, Any] | None = None,
        event_key: str | None = None,
        classification: Classification = Classification.INTERNAL,
    ) -> Trace:
        self._require_turn_identity(principal, turn)
        trace = Trace.from_principal(
            principal,
            event_key=event_key or f"turn:{turn.turn_id}:trace:{uuid4()}",
            case_id=turn.case_id,
            trace_type=trace_type,
            content=content,
            payload=payload or {},
            classification=classification,
        )
        persisted = await self.store.append_trace(principal, trace)
        await self.cases.attach_trace(principal, turn.case_id, persisted.trace_id)
        return persisted

    async def finish(
        self,
        principal: Principal,
        turn: SageTurn,
        *,
        outcome: CaseOutcome,
        agent_output: str,
        decision_summary: str = "",
        outcome_metrics: dict[str, Any] | None = None,
        classification: Classification = Classification.INTERNAL,
    ) -> CaseRecord:
        self._require_turn_identity(principal, turn)
        if outcome is CaseOutcome.UNKNOWN:
            raise SageConflict("a verified case outcome is required")
        case = await self.store.get_case(principal, turn.case_id)
        if case is None:
            raise SageNotFound(f"SAGE case not found: {turn.case_id}")
        if case.state not in {CaseState.OPEN, CaseState.PENDING_REVIEW}:
            raise SageConflict(f"case cannot finish from state {case.state}")
        output_occurred_at = utc_now()
        output_trace = Trace.from_principal(
            principal,
            case_id=turn.case_id,
            trace_type=TraceType.AGENT_OUTPUT,
            content=agent_output,
            event_key=f"turn:{turn.turn_id}:agent-output",
            classification=classification,
            occurred_at=output_occurred_at,
        )
        outcome_trace = Trace.from_principal(
            principal,
            case_id=turn.case_id,
            trace_type=TraceType.OUTCOME,
            content=outcome.value,
            payload={"metrics": outcome_metrics or {}},
            event_key=f"turn:{turn.turn_id}:outcome",
            classification=classification,
            occurred_at=output_occurred_at + timedelta(microseconds=1),
        )
        desired = case.model_copy(
            update={
                "state": CaseState.COMPLETED,
                "outcome": outcome,
                "decision_summary": decision_summary,
                "outcome_metrics": outcome_metrics or {},
                "completed_at": utc_now(),
            },
        )
        job = (
            self._reflection_job(principal, desired.case_id, stage="verified")
            if outcome in {CaseOutcome.SUCCESS, CaseOutcome.PARTIAL}
            else None
        )
        finished, _, _ = await self.store.commit_case_bundle(
            principal,
            desired,
            traces=(output_trace, outcome_trace),
            growth_job=job,
        )
        try:
            await self._record_outcome_signals(principal, finished)
        except Exception:
            logger.warning("SAGE outcome evaluation failed", exc_info=True)
        if job is not None:
            self._spawn_growth(principal)
        return finished

    async def complete_turn_for_review(
        self,
        principal: Principal,
        turn: SageTurn,
        *,
        agent_output: str,
        classification: Classification = Classification.INTERNAL,
    ) -> CaseRecord:
        """Atomically record output, pending-review state, and reflection work."""

        self._require_turn_identity(principal, turn)
        case = await self.store.get_case(principal, turn.case_id)
        if case is None:
            raise SageNotFound(f"SAGE case not found: {turn.case_id}")
        if case.state not in {CaseState.OPEN, CaseState.PENDING_REVIEW}:
            raise SageConflict(f"case cannot enter review from state {case.state}")
        trace = Trace.from_principal(
            principal,
            case_id=turn.case_id,
            trace_type=TraceType.AGENT_OUTPUT,
            content=agent_output,
            event_key=f"turn:{turn.turn_id}:agent-output",
            classification=classification,
        )
        pending = case.model_copy(update={"state": CaseState.PENDING_REVIEW})
        job = self._reflection_job(principal, case.case_id, stage="observed")
        saved, _, _ = await self.store.commit_case_bundle(
            principal,
            pending,
            traces=(trace,),
            growth_job=job,
        )
        self._spawn_growth(principal)
        return saved

    async def schedule_case_reflection(
        self,
        principal: Principal,
        case_id: UUID,
        *,
        stage: str = "observed",
    ) -> GrowthJob:
        """Durably schedule idempotent reflection for one tenant case."""

        job = self._reflection_job(principal, case_id, stage=stage)
        saved = await self.store.enqueue_growth_job(principal, job)
        self._spawn_growth(principal)
        return saved

    async def review_pending_case(
        self,
        principal: Principal,
        case_id: UUID,
        *,
        outcome: CaseOutcome,
        decision_summary: str,
        outcome_metrics: dict[str, Any] | None = None,
    ) -> tuple[CaseRecord, InsightDraft | None]:
        """Close a pending case from an authenticated management decision."""
        case = await self.store.get_case(principal, case_id)
        if case is None:
            raise SageNotFound(f"SAGE case not found: {case_id}")
        if case.state is not CaseState.PENDING_REVIEW:
            raise SageConflict("only pending cases can be reviewed")
        trace = Trace.from_principal(
            principal,
            event_key=f"case:{case_id}:reviewed-outcome",
            case_id=case_id,
            trace_type=TraceType.OUTCOME,
            content=outcome.value,
            payload={
                "metrics": outcome_metrics or {},
                "attestation": "authenticated-review",
            },
            classification=case.classification,
        )
        desired = case.model_copy(
            update={
                "state": CaseState.COMPLETED,
                "outcome": outcome,
                "decision_summary": decision_summary,
                "outcome_metrics": outcome_metrics or {},
                "completed_at": utc_now(),
            },
        )
        job = (
            self._reflection_job(principal, case_id, stage="verified")
            if outcome in {CaseOutcome.SUCCESS, CaseOutcome.PARTIAL}
            else None
        )
        insight = None
        try:
            # Keep the synchronous reviewer and background worker from
            # claiming the same transactional outbox item concurrently.
            async with self._growth_lock:
                finished, _, _ = await self.store.commit_case_bundle(
                    principal,
                    desired,
                    traces=(trace,),
                    growth_job=job,
                )
                try:
                    await self._record_outcome_signals(principal, finished)
                except Exception:
                    logger.warning(
                        "SAGE reviewed outcome evaluation failed",
                        exc_info=True,
                    )
                if outcome in {CaseOutcome.SUCCESS, CaseOutcome.PARTIAL}:
                    insight = await self.foundry.review_case(principal, case_id)
                    if job is not None:
                        await self.store.acknowledge_growth_job(
                            principal,
                            job.job_id,
                        )
        finally:
            # The verified-reflection job is a transactional outbox fallback:
            # if synchronous reflection fails, a worker can safely retry it.
            if job is not None:
                self._spawn_growth(principal)
        return finished, insight

    async def prepare(
        self,
        principal: Principal,
        query: str | RecallQuery,
        *,
        token_budget: int = 1250,
    ) -> ActionPack:
        decision = await self.control.decision(
            principal,
            SageCapability.HYBRID_RECALL,
            risk=RiskLevel.LOW,
        )
        if self.semantic is not None and decision.execute:
            await self.semantic.ensure_active(principal)
        return await self.recall.prepare(
            principal,
            query,
            token_budget=token_budget,
            hybrid=decision.apply,
            shadow=decision.execute and not decision.apply,
        )

    async def prepare_for_turn(
        self,
        principal: Principal,
        turn: SageTurn,
        query: str | RecallQuery,
        *,
        token_budget: int = 1250,
    ) -> ActionPack:
        """Prepare context and persist the exact recall decision on the case."""

        self._require_turn_identity(principal, turn)
        pack = await self.prepare(
            principal,
            query,
            token_budget=token_budget,
        )
        if pack.receipt is not None:
            await self.observe(
                principal,
                turn,
                trace_type=TraceType.RECALL,
                payload={"receipt": pack.receipt.model_dump(mode="json")},
                event_key=f"turn:{turn.turn_id}:recall",
            )
        return pack

    async def feedback(
        self,
        principal: Principal,
        *,
        receipt_id: UUID,
        verdict: FeedbackVerdict,
        source_id: UUID | None = None,
        comment: str = "",
    ) -> Trace:
        """Record user correction signals without mutating source knowledge."""

        traces = await self.store.list_traces(principal, limit=1000)
        receipt = next(
            (
                trace.payload.get("receipt")
                for trace in traces
                if trace.trace_type is TraceType.RECALL
                and isinstance(trace.payload.get("receipt"), dict)
                and str(trace.payload["receipt"].get("receipt_id")) == str(receipt_id)
            ),
            None,
        )
        if receipt is None:
            raise SageNotFound(f"SAGE recall receipt not found: {receipt_id}")
        allowed_sources = {
            UUID(str(value["source_id"]))
            for value in receipt.get("selections", ())
            if isinstance(value, dict) and value.get("source_id")
        }
        if source_id is not None and source_id not in allowed_sources:
            raise SageConflict("feedback source was not selected by this receipt")

        trace = Trace.from_principal(
            principal,
            event_key=f"recall:{receipt_id}:feedback:{uuid4()}",
            trace_type=TraceType.FEEDBACK,
            content=comment[:4000],
            payload={
                "receipt_id": str(receipt_id),
                "source_id": str(source_id) if source_id is not None else None,
                "verdict": verdict.value,
            },
        )
        persisted = await self.store.append_trace(principal, trace)
        if source_id is not None:
            await self.evaluation.record_feedback(
                principal,
                event_id=persisted.trace_id,
                receipt_id=receipt_id,
                source_id=source_id,
                verdict=verdict,
            )
        return persisted

    async def _record_outcome_signals(
        self,
        principal: Principal,
        case: CaseRecord,
    ) -> None:
        traces = await self.store.list_traces(
            principal,
            case_id=case.case_id,
            limit=1000,
        )
        for trace in traces:
            if trace.trace_type is not TraceType.RECALL:
                continue
            receipt = trace.payload.get("receipt")
            if not isinstance(receipt, dict):
                continue
            receipt_id = UUID(str(receipt["receipt_id"]))
            for selection in receipt.get("selections", ()):
                if not isinstance(selection, dict) or "source_id" not in selection:
                    continue
                await self.evaluation.record_outcome(
                    principal,
                    case_id=case.case_id,
                    receipt_id=receipt_id,
                    source_id=UUID(str(selection["source_id"])),
                    outcome=case.outcome,
                )

    async def run_growth_once(self, principal: Principal) -> bool:
        """Process one durable growth job visible to this tenant."""

        async with self._growth_lock:
            return await self._run_growth_once(principal)

    async def _run_growth_once(self, principal: Principal) -> bool:
        """Worker implementation serialized with authenticated review."""

        jobs = await self.store.claim_growth_jobs(
            principal,
            worker_id=self._worker_id,
            limit=1,
        )
        if not jobs:
            return False
        job = jobs[0]
        try:
            origin = Principal.model_validate(job.payload["principal"])
            if origin.tenant_id != principal.tenant_id:
                raise SageAccessDenied("growth job tenant substitution denied")
            if job.job_type is GrowthJobType.REFLECT_CASE:
                case_id = UUID(str(job.payload["case_id"]))
                await self.foundry.reflect_case(origin, case_id)
            elif job.job_type is GrowthJobType.CONSOLIDATE_TENANT:
                await self.consolidation.consolidate(
                    origin,
                    local_date=str(job.payload["local_date"]),
                )
            elif job.job_type is GrowthJobType.RECALCULATE_UTILITY:
                await self._recalculate_tenant_utility(origin)
            elif job.job_type is GrowthJobType.EVALUATE_RECALL:
                await self._evaluate_recall_shadow(origin)
            else:
                raise ValueError(f"unsupported growth job: {job.job_type}")
            await self.store.complete_growth_job(
                principal,
                job.job_id,
                worker_id=self._worker_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("SAGE automatic reflection failed", exc_info=True)
            await self.store.fail_growth_job(
                principal,
                job.job_id,
                worker_id=self._worker_id,
                error=str(exc),
                retry_delay_seconds=60 if job.attempts < 3 else None,
            )
        return True

    async def schedule_maintenance(
        self,
        principal: Principal,
        *,
        local_date: str | None = None,
    ) -> list[GrowthJob]:
        """Durably schedule a tenant's nightly work and start its worker."""

        jobs = await self.maintenance.schedule_due(
            principal,
            local_date=local_date,
        )
        if jobs:
            self._spawn_growth(principal)
        return jobs

    async def _recalculate_tenant_utility(self, principal: Principal) -> None:
        signals = await self.store.list_knowledge_signals(principal, limit=5000)
        for source_id in dict.fromkeys(signal.source_id for signal in signals):
            await self.evaluation.recalculate(principal, source_id)

    async def _evaluate_recall_shadow(self, principal: Principal) -> None:
        """Persist a bounded audit summary for offline recall evaluation."""

        traces = await self.store.list_traces(principal, limit=1000)
        recall_count = sum(trace.trace_type is TraceType.RECALL for trace in traces)
        degradation_count = 0
        for trace in traces:
            receipt = trace.payload.get("receipt")
            if trace.trace_type is TraceType.RECALL and isinstance(receipt, dict):
                degradation_count += len(receipt.get("degradations", ()))
        await self.store.append_trace(
            principal,
            Trace.from_principal(
                principal,
                event_key=f"evaluation:recall:{uuid4()}",
                trace_type=TraceType.GOVERNANCE,
                payload={
                    "kind": "recall_evaluation",
                    "recall_count": recall_count,
                    "degradation_count": degradation_count,
                },
            ),
        )

    @staticmethod
    def _reflection_job(
        principal: Principal,
        case_id: UUID,
        *,
        stage: str,
    ) -> GrowthJob:
        if stage not in {"observed", "verified"}:
            raise ValueError("reflection stage must be observed or verified")
        return GrowthJob(
            job_id=uuid5(case_id, f"sage:reflect-case:{stage}"),
            tenant_id=principal.tenant_id,
            job_type=GrowthJobType.REFLECT_CASE,
            payload={
                "case_id": str(case_id),
                "stage": stage,
                "principal": principal.model_dump(mode="json"),
            },
        )

    def _spawn_growth(self, principal: Principal) -> None:
        task = asyncio.create_task(
            self._coordinate_growth(principal),
            name=f"sage-growth:{principal.tenant_id}",
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _coordinate_growth(self, principal: Principal) -> None:
        """Schedule today's maintenance idempotently, then drain bounded work."""

        try:
            await self.maintenance.schedule_due(principal)
        except Exception:
            logger.warning("SAGE maintenance scheduling failed", exc_info=True)
        for _ in range(20):
            if not await self.run_growth_once(principal):
                break

    @staticmethod
    def _require_turn_identity(
        principal: Principal,
        turn: SageTurn,
    ) -> None:
        expected = (
            principal.tenant_id,
            principal.user_id,
            principal.agent_uid,
            principal.session_id,
        )
        actual = (
            turn.tenant_id,
            turn.user_id,
            turn.agent_uid,
            turn.session_id,
        )
        if actual != expected:
            raise SageAccessDenied("SAGE turn identity substitution denied")
