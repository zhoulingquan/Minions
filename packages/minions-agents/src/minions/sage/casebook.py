"""Business case lifecycle for SAGE."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .errors import SageConflict, SageNotFound
from .models import (
    CaseOutcome,
    CaseRecord,
    CaseState,
    Classification,
    Principal,
    ScopeRef,
    utc_now,
)
from .policy import ScopePolicy
from .store import SageStore


class CaseBook:
    """Builds auditable business cases from work performed by an agent."""

    def __init__(self, store: SageStore) -> None:
        self._store = store

    async def open_case(
        self,
        principal: Principal,
        *,
        scope: ScopeRef,
        domain: str = "",
        process: str = "",
        task_type: str = "",
        goal: str = "",
        constraints: dict[str, Any] | None = None,
        scenario: dict[str, Any] | None = None,
        classification: Classification = Classification.INTERNAL,
    ) -> CaseRecord:
        ScopePolicy.require_scope(principal, scope)
        case = CaseRecord(
            tenant_id=principal.tenant_id,
            owner_user_id=principal.user_id,
            agent_uid=principal.agent_uid,
            scope=scope,
            classification=classification,
            domain=domain,
            process=process,
            task_type=task_type,
            goal=goal,
            constraints=constraints or {},
            scenario=scenario or {},
        )
        return await self._store.save_case(principal, case)

    async def finish_case(
        self,
        principal: Principal,
        case_id: UUID,
        *,
        outcome: CaseOutcome,
        decision_summary: str = "",
        outcome_metrics: dict[str, Any] | None = None,
    ) -> CaseRecord:
        case = await self._required_case(principal, case_id)
        if case.state not in {CaseState.OPEN, CaseState.PENDING_REVIEW}:
            raise SageConflict(f"case cannot finish from state {case.state}")
        if outcome is CaseOutcome.UNKNOWN:
            raise SageConflict("a verified case outcome is required")
        finished = case.model_copy(
            update={
                "state": CaseState.COMPLETED,
                "outcome": outcome,
                "decision_summary": decision_summary,
                "outcome_metrics": outcome_metrics or {},
                "completed_at": utc_now(),
            },
        )
        return await self._store.save_case(principal, finished)

    async def mark_pending_review(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> CaseRecord:
        case = await self._required_case(principal, case_id)
        if case.state is not CaseState.OPEN:
            raise SageConflict(f"case cannot enter review from state {case.state}")
        pending = case.model_copy(update={"state": CaseState.PENDING_REVIEW})
        return await self._store.save_case(principal, pending)

    async def attach_trace(
        self,
        principal: Principal,
        case_id: UUID,
        trace_id: UUID,
    ) -> CaseRecord:
        case = await self._required_case(principal, case_id)
        if case.state not in {CaseState.OPEN, CaseState.PENDING_REVIEW}:
            raise SageConflict("cannot add evidence to a closed case")
        if trace_id in case.trace_ids:
            return case
        updated = case.model_copy(update={"trace_ids": (*case.trace_ids, trace_id)})
        return await self._store.save_case(principal, updated)

    async def _required_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> CaseRecord:
        case = await self._store.get_case(principal, case_id)
        if case is None:
            raise SageNotFound(f"SAGE case not found: {case_id}")
        return case
