"""Governed self-improvement lifecycle for SAGE."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID, uuid5

from .errors import SageConflict, SageInvalidTransition, SageNotFound
from .models import (
    CaseOutcome,
    CaseState,
    Classification,
    InsightDraft,
    InsightState,
    ItemKind,
    ItemState,
    KnowledgeItem,
    Principal,
    RiskLevel,
    ScopeRef,
    ScopeType,
    utc_now,
)
from .policy import ScopePolicy
from .store import SageStore


class GrowthCycle:
    """Turns observations into governed experience without self-promotion."""

    _EVIDENCE_THRESHOLDS = {
        ScopeType.SESSION: 2,
        ScopeType.CASE: 2,
        ScopeType.USER: 2,
        ScopeType.AGENT: 2,
        ScopeType.PROJECT: 2,
        ScopeType.TEAM: 3,
        ScopeType.TENANT: 5,
    }

    def __init__(self, store: SageStore, semantic=None) -> None:
        self._store = store
        self._semantic = semantic

    async def propose(
        self,
        principal: Principal,
        *,
        scope: ScopeRef,
        title: str,
        content: str,
        evidence_case_ids: Iterable[UUID] = (),
        applicability: dict[str, object] | None = None,
        confidence: float = 0.3,
        risk_level: RiskLevel = RiskLevel.LOW,
        classification: Classification = Classification.INTERNAL,
        fingerprint: str = "",
        state: InsightState = InsightState.DRAFT,
    ) -> InsightDraft:
        ScopePolicy.require_scope(principal, scope)
        if state not in {InsightState.OBSERVED, InsightState.DRAFT}:
            raise SageConflict("new insight must start as observed or draft")
        insight = InsightDraft(
            tenant_id=principal.tenant_id,
            scope=scope,
            classification=classification,
            title=title,
            content=content,
            fingerprint=fingerprint,
            applicability=applicability or {},
            evidence_case_ids=tuple(dict.fromkeys(evidence_case_ids)),
            confidence=confidence,
            risk_level=risk_level,
            state=state,
        )
        return await self._store.save_insight(principal, insight)

    async def revise(
        self,
        principal: Principal,
        insight_id: UUID,
        *,
        title: str,
        content: str,
        applicability: dict[str, object] | None = None,
    ) -> InsightDraft:
        """Revise a non-published lesson and require validation again."""

        insight = await self._required(principal, insight_id)
        if insight.state not in {
            InsightState.OBSERVED,
            InsightState.DRAFT,
            InsightState.VALIDATING,
        }:
            raise SageConflict(
                f"insight cannot be revised from state {insight.state}",
            )
        ScopePolicy.require_write_scope(principal, insight.scope)
        updated = insight.model_copy(
            update={
                "title": title.strip(),
                "content": content.strip(),
                "applicability": (
                    applicability
                    if applicability is not None
                    else insight.applicability
                ),
                "state": InsightState.DRAFT,
                "approved_by": None,
                "version": insight.version + 1,
                "updated_at": utc_now(),
            },
        )
        return await self._store.save_insight(principal, updated)

    async def add_evidence(
        self,
        principal: Principal,
        insight_id: UUID,
        case_id: UUID,
    ) -> InsightDraft:
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.DRAFT)
        if case_id in insight.evidence_case_ids:
            return insight
        updated = insight.model_copy(
            update={
                "evidence_case_ids": (*insight.evidence_case_ids, case_id),
                "updated_at": utc_now(),
            },
        )
        return await self._store.save_insight(principal, updated)

    @classmethod
    def evidence_threshold(cls, scope_type: ScopeType) -> int:
        return cls._EVIDENCE_THRESHOLDS[scope_type]

    async def start_validation(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.DRAFT)
        required = self._EVIDENCE_THRESHOLDS[insight.scope.scope_type]
        evidence_ids = set(insight.evidence_case_ids)
        if len(evidence_ids) < required:
            raise SageConflict(
                f"{required} independent cases required; got {len(evidence_ids)}",
            )
        verified = 0
        for case_id in evidence_ids:
            case = await self._store.get_case(principal, case_id)
            if (
                case is not None
                and case.state is CaseState.COMPLETED
                and (case.outcome in {CaseOutcome.SUCCESS, CaseOutcome.PARTIAL})
            ):
                verified += 1
        if verified < required:
            raise SageConflict(
                f"{required} verified completed cases required; got {verified}",
            )
        return await self._save_state(
            principal,
            insight,
            InsightState.VALIDATING,
        )

    async def approve(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        ScopePolicy.require_permission(principal, "sage.insight.approve")
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.VALIDATING)
        approved = insight.model_copy(
            update={
                "state": InsightState.APPROVED,
                "approved_by": principal.user_id,
                "updated_at": utc_now(),
            },
        )
        return await self._store.save_insight(principal, approved)

    async def reject(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        ScopePolicy.require_permission(principal, "sage.insight.approve")
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.VALIDATING)
        return await self._save_state(
            principal,
            insight,
            InsightState.REJECTED,
        )

    async def activate(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.APPROVED)
        if insight.approved_by is None:
            raise SageConflict("an approved_by identity is required")
        if insight.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            ScopePolicy.require_permission(
                principal,
                "sage.insight.publish.high_risk",
            )
        published_item_id = insight.published_item_id or uuid5(
            insight.insight_id,
            "sage-published-insight",
        )
        published = KnowledgeItem(
            item_id=published_item_id,
            tenant_id=insight.tenant_id,
            kind=ItemKind.INSIGHT,
            scope=insight.scope,
            classification=insight.classification,
            title=insight.title,
            content=insight.content,
            structured_data={
                "source_insight_id": str(insight.insight_id),
                "evidence_case_ids": [
                    str(case_id) for case_id in insight.evidence_case_ids
                ],
                "applicability": insight.applicability,
                "risk_level": insight.risk_level.value,
            },
            confidence=insight.confidence,
            importance=0.7,
            state=ItemState.ACTIVE,
        )
        await self._store.save_item(principal, published)
        if self._semantic is not None:
            await self._semantic.index_item(principal, published)
        active = insight.model_copy(
            update={
                "state": InsightState.ACTIVE,
                "published_item_id": published_item_id,
                "updated_at": utc_now(),
            },
        )
        return await self._store.save_insight(principal, active)

    async def rollback(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        ScopePolicy.require_permission(principal, "sage.insight.rollback")
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.ACTIVE)
        await self._retire_published(principal, insight, ItemState.ARCHIVED)
        return await self._save_state(
            principal,
            insight,
            InsightState.ROLLED_BACK,
        )

    async def supersede(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        insight = await self._required(principal, insight_id)
        self._require_state(insight, InsightState.ACTIVE)
        await self._retire_published(principal, insight, ItemState.SUPERSEDED)
        return await self._save_state(
            principal,
            insight,
            InsightState.SUPERSEDED,
        )

    async def archive(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        insight = await self._required(principal, insight_id)
        if insight.state not in {
            InsightState.ACTIVE,
            InsightState.REJECTED,
            InsightState.ROLLED_BACK,
            InsightState.SUPERSEDED,
        }:
            raise SageInvalidTransition(
                f"insight cannot be archived from state {insight.state}",
            )
        await self._retire_published(principal, insight, ItemState.ARCHIVED)
        return await self._save_state(
            principal,
            insight,
            InsightState.ARCHIVED,
        )

    async def _required(
        self,
        principal: Principal,
        insight_id: UUID,
    ) -> InsightDraft:
        insight = await self._store.get_insight(principal, insight_id)
        if insight is None:
            raise SageNotFound(f"SAGE insight not found: {insight_id}")
        return insight

    @staticmethod
    def _require_state(insight: InsightDraft, expected: InsightState) -> None:
        if insight.state is not expected:
            raise SageInvalidTransition(
                f"insight transition requires {expected}; got {insight.state}",
            )

    async def _save_state(
        self,
        principal: Principal,
        insight: InsightDraft,
        state: InsightState,
    ) -> InsightDraft:
        updated = insight.model_copy(
            update={"state": state, "updated_at": utc_now()},
        )
        return await self._store.save_insight(principal, updated)

    async def _retire_published(
        self,
        principal: Principal,
        insight: InsightDraft,
        state: ItemState,
    ) -> None:
        if insight.published_item_id is None:
            return
        item = await self._store.get_item(principal, insight.published_item_id)
        if item is None:
            raise SageConflict("published insight catalog item is missing")
        retired = item.model_copy(
            update={"state": state, "updated_at": utc_now()},
        )
        await self._store.save_item(principal, retired)
