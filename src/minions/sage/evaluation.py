"""Feedback and outcome evaluation for bounded SAGE utility learning."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID, uuid5

from .catalog import SageCatalog
from .control import PolicyCenter
from .models import (
    CaseOutcome,
    FeedbackVerdict,
    ItemState,
    KnowledgeSignal,
    Principal,
    RiskLevel,
    SageCapability,
    SignalKind,
    SourceQuality,
)
from .store import SageStore


_FEEDBACK_VALUES = {
    FeedbackVerdict.USEFUL: 1.0,
    FeedbackVerdict.IRRELEVANT: -0.25,
    FeedbackVerdict.WRONG: -1.0,
    FeedbackVerdict.OUTDATED: -0.8,
}

_OUTCOME_VALUES = {
    CaseOutcome.SUCCESS: 0.5,
    CaseOutcome.PARTIAL: 0.2,
    CaseOutcome.FAILURE: -0.5,
    CaseOutcome.CANCELLED: 0.0,
    CaseOutcome.UNKNOWN: 0.0,
}


class EvaluationEngine:
    """Turn immutable signals into slow, policy-controlled utility changes."""

    _MIN_SAMPLES = 2
    _MAX_SIGNALS_PER_ACTOR = 5
    _MAX_UTILITY_STEP = 0.1

    def __init__(
        self,
        store: SageStore,
        control: PolicyCenter,
        catalog: SageCatalog,
    ) -> None:
        self._store = store
        self._control = control
        self._catalog = catalog

    async def record_feedback(
        self,
        principal: Principal,
        *,
        event_id: UUID,
        receipt_id: UUID,
        source_id: UUID,
        verdict: FeedbackVerdict,
    ) -> SourceQuality:
        signal = KnowledgeSignal(
            signal_id=event_id,
            tenant_id=principal.tenant_id,
            source_id=source_id,
            actor_user_id=principal.user_id,
            kind=SignalKind.FEEDBACK,
            value=_FEEDBACK_VALUES[verdict],
            receipt_id=receipt_id,
            verdict=verdict,
        )
        await self._store.save_knowledge_signal(principal, signal)
        return await self.recalculate(principal, source_id)

    async def record_outcome(
        self,
        principal: Principal,
        *,
        case_id: UUID,
        receipt_id: UUID,
        source_id: UUID,
        outcome: CaseOutcome,
    ) -> SourceQuality:
        signal = KnowledgeSignal(
            signal_id=uuid5(case_id, f"sage-outcome:{source_id}"),
            tenant_id=principal.tenant_id,
            source_id=source_id,
            actor_user_id=principal.user_id,
            kind=SignalKind.OUTCOME,
            value=_OUTCOME_VALUES[outcome],
            weight=0.6,
            receipt_id=receipt_id,
            case_id=case_id,
        )
        await self._store.save_knowledge_signal(principal, signal)
        return await self.recalculate(principal, source_id)

    async def recalculate(
        self,
        principal: Principal,
        source_id: UUID,
    ) -> SourceQuality:
        signals = await self._store.list_knowledge_signals(
            principal,
            source_id=source_id,
        )
        item = await self._store.get_item(principal, source_id)
        current_utility = item.utility if item is not None else 0.0
        quality = self._quality(source_id, signals, current_utility)
        if (
            item is None
            or item.state is not ItemState.ACTIVE
            or quality.sample_count < self._MIN_SAMPLES
        ):
            return quality
        risk = self._item_risk(item.structured_data)
        decision = await self._control.decision(
            principal,
            SageCapability.FEEDBACK_LEARNING,
            scope=item.scope,
            risk=risk,
        )
        if not decision.apply or quality.proposed_utility == item.utility:
            return quality
        learned = await self._catalog.adjust_utility(
            principal,
            item.item_id,
            utility=quality.proposed_utility,
        )
        return quality.model_copy(update={"applied_item_id": learned.item_id})

    @classmethod
    def _quality(
        cls,
        source_id: UUID,
        signals: list[KnowledgeSignal],
        current_utility: float,
    ) -> SourceQuality:
        actor_counts: dict[UUID, int] = defaultdict(int)
        accepted: list[KnowledgeSignal] = []
        for signal in signals:
            if actor_counts[signal.actor_user_id] >= cls._MAX_SIGNALS_PER_ACTOR:
                continue
            actor_counts[signal.actor_user_id] += 1
            accepted.append(signal)
        total_weight = sum(signal.weight for signal in accepted)
        score = (
            sum(signal.value * signal.weight for signal in accepted) / total_weight
            if total_weight
            else 0.0
        )
        if len(accepted) < cls._MIN_SAMPLES:
            proposed = current_utility
        else:
            step = max(-cls._MAX_UTILITY_STEP, min(score * 0.1, cls._MAX_UTILITY_STEP))
            proposed = max(0.0, min(current_utility + step, 1.0))
        return SourceQuality(
            source_id=source_id,
            sample_count=len(accepted),
            positive_count=sum(signal.value > 0 for signal in accepted),
            negative_count=sum(signal.value < 0 for signal in accepted),
            score=score,
            proposed_utility=proposed,
        )

    @staticmethod
    def _item_risk(structured_data: dict[str, object]) -> RiskLevel:
        try:
            return RiskLevel(str(structured_data.get("risk_level", "low")))
        except ValueError:
            return RiskLevel.HIGH


__all__ = ["EvaluationEngine"]
