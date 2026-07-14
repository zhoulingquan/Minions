"""Automatic, conservative business reflection for completed SAGE cases."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from uuid import UUID

from .errors import SageConflict, SageNotFound
from .growth import GrowthCycle
from .models import (
    CaseOutcome,
    CaseState,
    InsightDraft,
    InsightState,
    Principal,
)
from .reflection import ReflectionEngine
from .store import SageStore


class InsightFoundry:
    """Forms low-confidence candidates; it never approves its own output."""

    def __init__(
        self,
        store: SageStore,
        growth: GrowthCycle,
        reflection: ReflectionEngine | None = None,
    ) -> None:
        self._store = store
        self._growth = growth
        self._reflection = reflection or ReflectionEngine(store)
        self._review_lock = asyncio.Lock()

    async def reflect_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> InsightDraft | None:
        """Create an observed draft or process a verified completed case."""

        async with self._review_lock:
            case = await self._store.get_case(principal, case_id)
            if case is None:
                raise SageNotFound(f"SAGE case not found: {case_id}")
            if case.state is CaseState.PENDING_REVIEW:
                return await self._observe_case(principal, case)
            return await self._review_case(principal, case_id)

    async def review_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> InsightDraft | None:
        # SQLite is the single-process adapter. Serialize correlation and
        # evidence merging so concurrent completions cannot fork a candidate.
        async with self._review_lock:
            return await self._review_case(principal, case_id)

    async def _review_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> InsightDraft | None:
        case = await self._store.get_case(principal, case_id)
        if case is None:
            raise SageNotFound(f"SAGE case not found: {case_id}")
        if case.state is not CaseState.COMPLETED or case.outcome not in {
            CaseOutcome.SUCCESS,
            CaseOutcome.PARTIAL,
        }:
            raise SageConflict("only completed cases with trusted outcomes can reflect")
        reflection = await self._reflection.reflect(
            principal,
            case,
            provisional=False,
        )
        lesson = reflection.lesson.strip()
        if not lesson:
            return None

        title = reflection.title
        fingerprint = self.fingerprint_for(
            scope_type=case.scope.scope_type.value,
            domain=case.domain,
            process=case.process,
            task_type=case.task_type,
            lesson=lesson,
        )
        existing = await self._store.search_insights(
            principal,
            fingerprint,
            states=(InsightState.DRAFT,),
            limit=1,
        )
        if existing:
            candidate = await self._growth.add_evidence(
                principal,
                existing[0].insight_id,
                case.case_id,
            )
            observed = await self._observed_for_case(principal, case.case_id)
            if observed is not None and observed.insight_id != candidate.insight_id:
                await self._store.save_insight(
                    principal,
                    observed.model_copy(
                        update={
                            "state": InsightState.SUPERSEDED,
                            "updated_at": candidate.updated_at,
                        },
                    ),
                )
        else:
            observed = await self._observed_for_case(principal, case.case_id)
            if observed is not None:
                candidate = observed.model_copy(
                    update={
                        "title": title,
                        "content": reflection.content,
                        "fingerprint": fingerprint,
                        "applicability": reflection.applicability,
                        "confidence": reflection.confidence,
                        "risk_level": reflection.risk_level,
                        "state": InsightState.DRAFT,
                        "version": observed.version + 1,
                        "updated_at": case.completed_at or observed.updated_at,
                    },
                )
                candidate = await self._store.save_insight(principal, candidate)
            else:
                candidate = await self._growth.propose(
                    principal,
                    scope=case.scope,
                    classification=case.classification,
                    title=title,
                    content=reflection.content,
                    fingerprint=fingerprint,
                    evidence_case_ids=(case.case_id,),
                    applicability=reflection.applicability,
                    confidence=reflection.confidence,
                    risk_level=reflection.risk_level,
                )

        threshold = self._growth.evidence_threshold(case.scope.scope_type)
        if len(set(candidate.evidence_case_ids)) >= threshold:
            return await self._growth.start_validation(
                principal,
                candidate.insight_id,
            )
        return candidate

    async def _observe_case(
        self,
        principal: Principal,
        case,
    ) -> InsightDraft:
        existing = await self._observed_for_case(principal, case.case_id)
        if existing is not None:
            return existing
        reflection = await self._reflection.reflect(
            principal,
            case,
            provisional=True,
        )
        return await self._growth.propose(
            principal,
            scope=case.scope,
            classification=case.classification,
            title=reflection.title,
            content=reflection.content,
            fingerprint=f"observed:{case.case_id}",
            evidence_case_ids=(case.case_id,),
            applicability=reflection.applicability,
            confidence=reflection.confidence,
            risk_level=reflection.risk_level,
            state=InsightState.OBSERVED,
        )

    async def _observed_for_case(
        self,
        principal: Principal,
        case_id: UUID,
    ) -> InsightDraft | None:
        values = await self._store.list_insights(
            principal,
            # A reviewer may improve the provisional text before confirming the
            # business outcome. ``revise`` deliberately moves it to DRAFT, but
            # it is still the same case-bound provisional lesson until the
            # fingerprint is replaced by the verified reflection fingerprint.
            states=(InsightState.OBSERVED, InsightState.DRAFT),
            limit=1000,
        )
        return next(
            (
                value
                for value in values
                if case_id in value.evidence_case_ids
                and value.fingerprint.startswith("observed:")
            ),
            None,
        )

    @staticmethod
    def _title(process: str, task_type: str, domain: str) -> str:
        subject = process or task_type or domain or "Business"
        return f"{subject[:220]} lesson"

    @staticmethod
    def fingerprint_for(**values: str) -> str:
        """Return the stable correlation key for a proposed lesson."""
        normalized = {
            key: re.sub(r"\s+", " ", value.strip().casefold())
            for key, value in values.items()
        }
        payload = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = ["InsightFoundry"]
