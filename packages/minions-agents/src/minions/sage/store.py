"""Storage port for SAGE domain services."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from .models import (
    CapabilityPolicy,
    CandidateState,
    CaseRecord,
    CaseState,
    ConsolidationCandidate,
    ConsolidationRun,
    GrowthJob,
    InsightDraft,
    InsightState,
    ItemKind,
    ItemState,
    KnowledgeItem,
    KnowledgeSignal,
    Playbook,
    PlaybookState,
    Principal,
    SageCapability,
    Trace,
)


class SageStore(Protocol):
    """Persistence contract implemented by SAGE storage adapters."""

    async def start(self) -> None: ...

    async def close(self) -> None: ...

    async def append_trace(
        self,
        principal: Principal,
        trace: Trace,
    ) -> Trace: ...

    async def list_traces(
        self,
        principal: Principal,
        *,
        case_id: UUID | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[Trace]: ...

    async def save_case(
        self,
        principal: Principal,
        case: CaseRecord,
    ) -> CaseRecord: ...

    async def commit_case_bundle(
        self,
        principal: Principal,
        case: CaseRecord,
        *,
        traces: tuple[Trace, ...] = (),
        growth_job: GrowthJob | None = None,
    ) -> tuple[CaseRecord, tuple[Trace, ...], GrowthJob | None]:
        """Atomically persist evidence, case state, and durable growth work."""
        ...

    async def get_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> CaseRecord | None: ...

    async def list_cases(
        self,
        principal: Principal,
        *,
        states: tuple[CaseState, ...] | None = None,
        limit: int = 100,
    ) -> list[CaseRecord]: ...

    async def save_item(
        self,
        principal: Principal,
        item: KnowledgeItem,
    ) -> KnowledgeItem: ...

    async def get_item(
        self,
        principal: Principal,
        item_id: UUID,
    ) -> KnowledgeItem | None: ...

    async def search_items(
        self,
        principal: Principal,
        query: str,
        *,
        states: tuple[ItemState, ...] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeItem]: ...

    async def list_items(
        self,
        principal: Principal,
        *,
        states: tuple[ItemState, ...] | None = None,
        kinds: tuple[ItemKind, ...] | None = None,
        limit: int = 100,
    ) -> list[KnowledgeItem]: ...

    async def save_insight(
        self,
        principal: Principal,
        insight: InsightDraft,
    ) -> InsightDraft: ...

    async def get_insight(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft | None: ...

    async def search_insights(
        self,
        principal: Principal,
        fingerprint: str,
        *,
        states: tuple[InsightState, ...] | None = None,
        limit: int = 20,
    ) -> list[InsightDraft]: ...

    async def list_insights(
        self,
        principal: Principal,
        *,
        states: tuple[InsightState, ...] | None = None,
        limit: int = 100,
    ) -> list[InsightDraft]: ...

    async def save_playbook(
        self,
        principal: Principal,
        playbook: Playbook,
    ) -> Playbook: ...

    async def get_playbook(
        self,
        principal: Principal,
        playbook_id: UUID,
    ) -> Playbook | None: ...

    async def search_playbooks(
        self,
        principal: Principal,
        query: str,
        *,
        limit: int = 10,
    ) -> list[Playbook]: ...

    async def list_playbooks(
        self,
        principal: Principal,
        *,
        states: tuple[PlaybookState, ...] | None = None,
        limit: int = 100,
    ) -> list[Playbook]: ...

    async def save_capability_policy(
        self,
        principal: Principal,
        policy: CapabilityPolicy,
    ) -> CapabilityPolicy: ...

    async def get_capability_policy(
        self,
        principal: Principal,
        policy_id: UUID,
    ) -> CapabilityPolicy | None: ...

    async def list_capability_policies(
        self,
        principal: Principal,
        *,
        capability: SageCapability | None = None,
        limit: int = 100,
    ) -> list[CapabilityPolicy]: ...

    async def save_knowledge_signal(
        self,
        principal: Principal,
        signal: KnowledgeSignal,
    ) -> KnowledgeSignal: ...

    async def list_knowledge_signals(
        self,
        principal: Principal,
        *,
        source_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[KnowledgeSignal]: ...

    async def save_item_embedding(
        self,
        principal: Principal,
        item_id: UUID,
        embedding: tuple[float, ...],
        *,
        model: str = "",
        item_version: int = 1,
    ) -> None: ...

    async def semantic_search_items(
        self,
        principal: Principal,
        embedding: tuple[float, ...],
        *,
        limit: int = 20,
    ) -> list[tuple[KnowledgeItem, float]]: ...

    async def save_consolidation_run(
        self,
        principal: Principal,
        run: ConsolidationRun,
    ) -> ConsolidationRun: ...

    async def get_consolidation_run(
        self,
        principal: Principal,
        run_id: UUID,
    ) -> ConsolidationRun | None: ...

    async def list_consolidation_runs(
        self,
        principal: Principal,
        *,
        limit: int = 100,
    ) -> list[ConsolidationRun]: ...

    async def save_consolidation_candidate(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
    ) -> ConsolidationCandidate: ...

    async def get_consolidation_candidate(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate | None: ...

    async def list_consolidation_candidates(
        self,
        principal: Principal,
        *,
        states: tuple[CandidateState, ...] | None = None,
        limit: int = 100,
    ) -> list[ConsolidationCandidate]: ...

    async def enqueue_growth_job(
        self,
        principal: Principal,
        job: GrowthJob,
    ) -> GrowthJob: ...

    async def list_growth_jobs(
        self,
        principal: Principal,
        *,
        limit: int = 100,
    ) -> list[GrowthJob]: ...

    async def acknowledge_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
    ) -> GrowthJob:
        """Mark a still-pending outbox job complete after inline success."""
        ...

    async def claim_growth_jobs(
        self,
        principal: Principal,
        *,
        worker_id: str,
        limit: int = 1,
        lease_seconds: int = 60,
    ) -> list[GrowthJob]: ...

    async def complete_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
        *,
        worker_id: str,
    ) -> GrowthJob: ...

    async def fail_growth_job(
        self,
        principal: Principal,
        job_id: UUID,
        *,
        worker_id: str,
        error: str,
        retry_delay_seconds: int | None = 60,
    ) -> GrowthJob: ...
