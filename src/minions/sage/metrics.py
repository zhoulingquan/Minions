"""Bounded operational and learning metrics for SAGE."""

from __future__ import annotations

from .models import (
    CandidateState,
    ConsolidationRunState,
    EvaluationSnapshot,
    GrowthJobState,
    ItemState,
    Principal,
    TraceType,
)
from .store import SageStore


class SageMetrics:
    """Build tenant-scoped snapshots from already-authorized store reads."""

    def __init__(self, store: SageStore) -> None:
        self._store = store

    async def snapshot(self, principal: Principal) -> EvaluationSnapshot:
        items = await self._store.list_items(principal, limit=5000)
        signals = await self._store.list_knowledge_signals(principal, limit=5000)
        traces = await self._store.list_traces(principal, limit=5000)
        candidates = await self._store.list_consolidation_candidates(
            principal,
            limit=5000,
        )
        runs = await self._store.list_consolidation_runs(principal, limit=5000)
        jobs = await self._store.list_growth_jobs(principal, limit=5000)

        recall = [trace for trace in traces if trace.trace_type is TraceType.RECALL]
        degradations = 0
        for trace in recall:
            receipt = trace.payload.get("receipt")
            if isinstance(receipt, dict):
                degradations += len(receipt.get("degradations", ()))
        positive = sum(signal.value > 0 for signal in signals)
        completed_jobs = [
            job for job in jobs if job.state is GrowthJobState.COMPLETED
        ]
        average_latency = (
            sum(
                max(0.0, (job.updated_at - job.created_at).total_seconds() * 1000)
                for job in completed_jobs
            )
            / len(completed_jobs)
            if completed_jobs
            else 0.0
        )
        return EvaluationSnapshot(
            tenant_id=principal.tenant_id,
            knowledge_total=len(items),
            active_knowledge=sum(item.state is ItemState.ACTIVE for item in items),
            signal_count=len(signals),
            positive_signal_rate=positive / len(signals) if signals else 0.0,
            recall_count=len(recall),
            degradation_count=degradations,
            degradation_rate=degradations / len(recall) if recall else 0.0,
            pending_candidates=sum(
                value.state in {CandidateState.PROPOSED, CandidateState.APPROVED}
                for value in candidates
            ),
            applied_candidates=sum(
                value.state is CandidateState.APPLIED for value in candidates
            ),
            rolled_back_candidates=sum(
                value.state is CandidateState.ROLLED_BACK for value in candidates
            ),
            completed_runs=sum(
                value.state is ConsolidationRunState.COMPLETED for value in runs
            ),
            failed_runs=sum(
                value.state is ConsolidationRunState.FAILED for value in runs
            ),
            pending_jobs=sum(
                value.state in {GrowthJobState.PENDING, GrowthJobState.LEASED}
                for value in jobs
            ),
            completed_jobs=len(completed_jobs),
            failed_jobs=sum(value.state is GrowthJobState.FAILED for value in jobs),
            average_job_latency_ms=average_latency,
        )


__all__ = ["SageMetrics"]
