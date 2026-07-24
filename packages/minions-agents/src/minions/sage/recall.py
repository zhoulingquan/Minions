"""Deterministic, bounded, explainable hybrid retrieval for SAGE."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from .embeddings import EmbeddingService
from .models import (
    ActionPack,
    ItemKind,
    ItemState,
    KnowledgeItem,
    KnowledgeSignal,
    Playbook,
    PlaybookState,
    Principal,
    RecallBudget,
    RecallQuery,
    RecallReceipt,
    RecallSection,
    RecallSelection,
    ScopeType,
)
from .store import SageStore


class RecallPlanner:
    """Prepare authorized context with bounded hybrid and shadow ranking."""

    _SCOPE_WEIGHT = {
        ScopeType.TENANT: 10,
        ScopeType.TEAM: 20,
        ScopeType.AGENT: 30,
        ScopeType.USER: 40,
        ScopeType.PROJECT: 50,
        ScopeType.SESSION: 60,
        ScopeType.CASE: 70,
    }

    def __init__(
        self,
        store: SageStore,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._store = store
        self._embedding_service = embedding_service

    async def prepare(
        self,
        principal: Principal,
        query: str | RecallQuery,
        *,
        token_budget: int = 1250,
        item_limit: int = 40,
        playbook_limit: int = 10,
        hybrid: bool = True,
        shadow: bool = False,
    ) -> ActionPack:
        request = query if isinstance(query, RecallQuery) else RecallQuery(text=query)
        budget = RecallBudget.for_total(token_budget)
        now = request.as_of
        degradations: list[str] = []

        anchors = await self._store.list_items(
            principal,
            states=(ItemState.ACTIVE,),
            kinds=(ItemKind.ANCHOR,),
            limit=max(1, item_limit),
        )
        anchors = [item for item in anchors if self._currently_valid(item, now)]
        anchors.sort(key=self._item_rank, reverse=True)

        lexical_items = await self._store.search_items(
            principal,
            request.text,
            states=(ItemState.ACTIVE,),
            limit=max(1, item_limit * 3),
        )
        item_by_id = {item.item_id: item for item in lexical_items}
        if hybrid and self._has_structured_context(request):
            structured_items = await self._store.list_items(
                principal,
                states=(ItemState.ACTIVE,),
                limit=max(1, item_limit * 5),
            )
            for item in structured_items:
                if self._structured_relevant(item, request):
                    item_by_id.setdefault(item.item_id, item)

        semantic_scores: dict[UUID, float] = {}
        if hybrid and self._embedding_service is not None and request.text.strip():
            if not getattr(self._store, "supports_semantic", False):
                degradations.append("semantic_store_unavailable")
            else:
                result = await self._embedding_service.embed(request.text)
                if result.degradation:
                    degradations.append(result.degradation)
                elif result.vector is not None:
                    try:
                        matches = await self._store.semantic_search_items(
                            principal,
                            result.vector,
                            limit=max(1, item_limit * 2),
                        )
                        minimum = float(
                            getattr(
                                self._embedding_service.provider,
                                "min_similarity",
                                0.25,
                            ),
                        )
                        for item, score in matches:
                            if score < minimum:
                                continue
                            item_by_id.setdefault(item.item_id, item)
                            semantic_scores[item.item_id] = max(0.0, min(score, 1.0))
                    except Exception:
                        degradations.append("semantic_store_error")

        items = [
            item
            for item in item_by_id.values()
            if item.kind is not ItemKind.ANCHOR and self._currently_valid(item, now)
        ]
        signals = await self._store.list_knowledge_signals(principal, limit=5000)
        feedback_scores = self._feedback_scores(signals)
        components = {
            item.item_id: self._score_components(
                item,
                request,
                now,
                feedback_scores.get(item.item_id, 0.0),
                semantic_scores.get(item.item_id, 0.0),
            )
            for item in items
        }
        baseline_items = sorted(items, key=self._item_rank, reverse=True)
        hybrid_items = sorted(
            items,
            key=lambda item: self._hybrid_rank(item, components[item.item_id]),
            reverse=True,
        )
        selected_order = baseline_items if shadow or not hybrid else hybrid_items

        playbooks = await self._store.search_playbooks(
            principal,
            request.text,
            limit=max(1, playbook_limit),
        )
        playbooks = [
            playbook for playbook in playbooks if playbook.state is PlaybookState.ACTIVE
        ]
        playbooks.sort(key=self._playbook_rank, reverse=True)

        facts = [
            item
            for item in selected_order
            if item.kind not in (ItemKind.INSIGHT, ItemKind.WARNING)
        ]
        insights = [item for item in selected_order if item.kind is ItemKind.INSIGHT]
        warnings = [item for item in selected_order if item.kind is ItemKind.WARNING]

        selected_anchors, anchor_tokens = self._select_items(
            anchors,
            budget.anchors,
            item_limit,
        )
        selected_facts, fact_tokens = self._select_items(
            facts,
            budget.facts,
            item_limit,
        )
        selected_insights, insight_tokens = self._select_items(
            insights,
            budget.insights,
            item_limit,
        )
        selected_playbooks, playbook_tokens = self._select_playbooks(
            playbooks,
            budget.playbooks,
            playbook_limit,
        )
        selected_warnings, warning_tokens = self._select_items(
            warnings,
            budget.warnings,
            item_limit,
        )
        section_tokens = {
            RecallSection.ANCHOR: anchor_tokens,
            RecallSection.FACT: fact_tokens,
            RecallSection.INSIGHT: insight_tokens,
            RecallSection.PLAYBOOK: playbook_tokens,
            RecallSection.WARNING: warning_tokens,
        }
        selections = tuple(
            [
                self._item_selection(
                    item,
                    RecallSection.ANCHOR,
                    self._score_components(item, request, now, 0.0, 0.0),
                )
                for item in selected_anchors
            ]
            + [
                self._item_selection(item, RecallSection.FACT, components[item.item_id])
                for item in selected_facts
            ]
            + [
                self._item_selection(
                    item,
                    RecallSection.INSIGHT,
                    components[item.item_id],
                )
                for item in selected_insights
            ]
            + [self._playbook_selection(playbook) for playbook in selected_playbooks]
            + [
                self._item_selection(
                    item,
                    RecallSection.WARNING,
                    components[item.item_id],
                )
                for item in selected_warnings
            ],
        )
        source_ids = tuple(
            [item.item_id for item in selected_anchors]
            + [item.item_id for item in selected_facts]
            + [item.item_id for item in selected_insights]
            + [playbook.playbook_id for playbook in selected_playbooks]
            + [item.item_id for item in selected_warnings],
        )
        shadow_source_ids = (
            tuple(item.item_id for item in hybrid_items[: max(1, item_limit)])
            if shadow
            else ()
        )
        ranking_mode = "shadow" if shadow else ("hybrid" if hybrid else "baseline")
        receipt = RecallReceipt(
            tenant_id=principal.tenant_id,
            query=request.text,
            budget=budget,
            selections=selections,
            section_tokens=section_tokens,
            ranking_mode=ranking_mode,
            shadow_source_ids=shadow_source_ids,
            degradations=tuple(dict.fromkeys(degradations)),
        )
        return ActionPack(
            tenant_id=principal.tenant_id,
            query=request.text,
            anchors=tuple(selected_anchors),
            known_facts=tuple(selected_facts),
            insights=tuple(selected_insights),
            playbooks=tuple(selected_playbooks),
            warnings=tuple(selected_warnings),
            source_ids=source_ids,
            section_tokens=section_tokens,
            receipt=receipt,
            estimated_tokens=sum(section_tokens.values()),
        )

    def _select_items(
        self,
        items: list[KnowledgeItem],
        budget: int,
        limit: int,
    ) -> tuple[list[KnowledgeItem], int]:
        selected: list[KnowledgeItem] = []
        used = 0
        for item in items[: max(1, limit)]:
            cost = self._item_tokens(item)
            if used + cost <= budget:
                selected.append(item)
                used += cost
        return selected, used

    def _select_playbooks(
        self,
        playbooks: list[Playbook],
        budget: int,
        limit: int,
    ) -> tuple[list[Playbook], int]:
        selected: list[Playbook] = []
        used = 0
        for playbook in playbooks[: max(1, limit)]:
            cost = self._playbook_tokens(playbook)
            if used + cost <= budget:
                selected.append(playbook)
                used += cost
        return selected, used

    def _item_selection(
        self,
        item: KnowledgeItem,
        section: RecallSection,
        components: dict[str, float],
    ) -> RecallSelection:
        reasons = [
            "active",
            "within_validity",
            f"scope:{item.scope.scope_type.value}",
        ]
        reasons.extend(
            name
            for name in ("lexical", "entity", "applicability", "feedback", "semantic")
            if components.get(name, 0) > 0
        )
        return RecallSelection(
            source_id=item.item_id,
            section=section,
            scope=item.scope,
            estimated_tokens=self._item_tokens(item),
            reasons=tuple(reasons),
            score_components=components,
        )

    def _playbook_selection(self, playbook: Playbook) -> RecallSelection:
        return RecallSelection(
            source_id=playbook.playbook_id,
            section=RecallSection.PLAYBOOK,
            scope=playbook.scope,
            estimated_tokens=self._playbook_tokens(playbook),
            reasons=("active", f"scope:{playbook.scope.scope_type.value}"),
            score_components={
                "scope": float(self._SCOPE_WEIGHT[playbook.scope.scope_type]),
                "success_rate": playbook.success_rate,
                "evidence_count": float(playbook.evidence_count),
            },
        )

    def _score_components(
        self,
        item: KnowledgeItem,
        query: RecallQuery,
        now: datetime,
        feedback: float,
        semantic: float,
    ) -> dict[str, float]:
        query_terms = self._terms(query.text)
        item_terms = self._terms(f"{item.title} {item.content}")
        lexical = len(query_terms & item_terms) / max(1, len(query_terms))
        wanted_entities = {value.casefold() for value in query.entities}
        item_entities = {
            str(value).casefold()
            for value in item.structured_data.get("entities", ())
            if str(value).strip()
        }
        entity = len(wanted_entities & item_entities) / max(1, len(wanted_entities))
        applicability = self._applicability_score(item, query)
        age_days = max(0.0, (now - item.updated_at).total_seconds() / 86400)
        freshness = 1.0 / (1.0 + age_days / 90.0)
        return {
            "scope": float(self._SCOPE_WEIGHT[item.scope.scope_type]),
            "lexical": lexical,
            "entity": entity,
            "applicability": applicability,
            "freshness": freshness,
            "importance": item.importance,
            "confidence": item.confidence,
            "utility": item.utility,
            "feedback": feedback,
            "semantic": semantic,
        }

    def _hybrid_rank(
        self,
        item: KnowledgeItem,
        components: dict[str, float],
    ) -> tuple[float, ...]:
        score = (
            components["lexical"] * 0.24
            + components["entity"] * 0.18
            + components["applicability"] * 0.13
            + components["freshness"] * 0.08
            + components["importance"] * 0.09
            + components["confidence"] * 0.09
            + components["utility"] * 0.08
            + ((components["feedback"] + 1) / 2) * 0.05
            + components["semantic"] * 0.06
        )
        return (
            float(self._SCOPE_WEIGHT[item.scope.scope_type]),
            score,
            item.updated_at.timestamp(),
            float(item.item_id.int),
        )

    @staticmethod
    def _feedback_scores(signals: list[KnowledgeSignal]) -> dict[UUID, float]:
        grouped: dict[UUID, list[KnowledgeSignal]] = {}
        for signal in signals:
            grouped.setdefault(signal.source_id, []).append(signal)
        return {
            source_id: sum(value.value * value.weight for value in values)
            / max(sum(value.weight for value in values), 1e-9)
            for source_id, values in grouped.items()
        }

    @staticmethod
    def _has_structured_context(query: RecallQuery) -> bool:
        return bool(query.entities or query.domain or query.process or query.task_type)

    @classmethod
    def _structured_relevant(cls, item: KnowledgeItem, query: RecallQuery) -> bool:
        if query.entities:
            wanted = {value.casefold() for value in query.entities}
            available = {
                str(value).casefold()
                for value in item.structured_data.get("entities", ())
            }
            if wanted & available:
                return True
        return cls._applicability_score(item, query) > 0

    @staticmethod
    def _applicability_score(item: KnowledgeItem, query: RecallQuery) -> float:
        raw = item.structured_data.get("applicability", {})
        applicability: dict[str, Any] = raw if isinstance(raw, dict) else {}
        wanted = {
            "domain": query.domain,
            "process": query.process,
            "task_type": query.task_type,
        }
        present = [(key, value) for key, value in wanted.items() if value]
        if not present:
            return 0.0
        matches = sum(
            str(applicability.get(key, "")).casefold() == value.casefold()
            for key, value in present
        )
        return matches / len(present)

    @staticmethod
    def _terms(value: str) -> set[str]:
        return {
            term.casefold()
            for term in re.findall(r"[\w\u3400-\u9fff]+", value, flags=re.UNICODE)
        }

    @staticmethod
    def _currently_valid(item: KnowledgeItem, now: datetime) -> bool:
        return item.valid_from <= now and (
            item.valid_until is None or item.valid_until > now
        )

    def _item_rank(self, item: KnowledgeItem) -> tuple[float, ...]:
        return (
            float(self._SCOPE_WEIGHT[item.scope.scope_type]),
            item.importance,
            item.confidence,
            item.utility,
            item.updated_at.timestamp(),
            float(item.item_id.int),
        )

    def _playbook_rank(self, playbook: Playbook) -> tuple[float, ...]:
        return (
            float(self._SCOPE_WEIGHT[playbook.scope.scope_type]),
            playbook.success_rate,
            float(playbook.evidence_count),
            playbook.updated_at.timestamp(),
        )

    @staticmethod
    def _item_tokens(item: KnowledgeItem) -> int:
        return max(1, math.ceil(len(item.title + "\n" + item.content) / 4))

    @staticmethod
    def _playbook_tokens(playbook: Playbook) -> int:
        payload = playbook.model_dump_json(
            include={
                "name",
                "steps",
                "decision_points",
                "pitfalls",
                "acceptance_criteria",
            },
        )
        return max(1, math.ceil(len(payload) / 4))
