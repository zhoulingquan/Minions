"""Tenant-wide knowledge consolidation and governed candidate lifecycle."""

from __future__ import annotations

import asyncio
import re
from collections import Counter, defaultdict
from datetime import date
from uuid import UUID, uuid5

from .catalog import SageCatalog
from .embeddings import EmbeddingService
from .control import PolicyCenter
from .errors import SageConflict, SageNotFound
from .models import (
    CandidateState,
    ConsolidationAction,
    ConsolidationCandidate,
    ConsolidationKind,
    ConsolidationRun,
    ConsolidationRunState,
    ItemKind,
    ItemState,
    KnowledgeItem,
    Playbook,
    PlaybookState,
    Principal,
    RiskLevel,
    SageCapability,
    ScopeType,
    Trace,
    TraceType,
    utc_now,
)
from .policy import ScopePolicy
from .store import SageStore
from .semantic import SemanticIndexer


class ConsolidationService:
    """Detect knowledge health issues and apply only governed changes."""

    def __init__(
        self,
        store: SageStore,
        control: PolicyCenter,
        catalog: SageCatalog,
        semantic: SemanticIndexer | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._store = store
        self._control = control
        self._catalog = catalog
        self._semantic = semantic
        self._embeddings = embeddings
        self._tenant_locks: dict[UUID, asyncio.Lock] = {}

    async def consolidate(
        self,
        principal: Principal,
        *,
        local_date: str | None = None,
        max_items: int = 1000,
    ) -> ConsolidationRun | None:
        decision = await self._control.decision(
            principal,
            SageCapability.NIGHTLY_CONSOLIDATION,
        )
        if not decision.execute:
            return None
        lock = self._tenant_locks.setdefault(principal.tenant_id, asyncio.Lock())
        async with lock:
            return await self._consolidate_locked(
                principal,
                local_date=local_date,
                max_items=max_items,
                settings=decision.policy.settings,
                auto_apply=decision.apply,
            )

    async def _consolidate_locked(
        self,
        principal: Principal,
        *,
        local_date: str | None,
        max_items: int,
        settings: dict[str, object],
        auto_apply: bool,
    ) -> ConsolidationRun:
        run = ConsolidationRun.create(
            principal.tenant_id,
            local_date or date.today().isoformat(),
        )
        existing = await self._store.get_consolidation_run(principal, run.run_id)
        if existing is not None and existing.state is ConsolidationRunState.COMPLETED:
            return existing
        now = utc_now()
        run = (existing or run).model_copy(
            update={
                "state": ConsolidationRunState.RUNNING,
                "started_at": (existing.started_at if existing else None) or now,
                "updated_at": now,
                "error": "",
            },
        )
        await self._store.save_consolidation_run(principal, run)
        try:
            configured_items = int(settings.get("max_items", max_items))
            time_budget = max(
                1.0,
                min(float(settings.get("time_budget_seconds", 30)), 300.0),
            )
            max_candidates = max(
                1,
                min(int(settings.get("max_candidates", 500)), 2000),
            )
            async with asyncio.timeout(time_budget):
                items = await self._store.list_items(
                    principal,
                    states=(ItemState.ACTIVE,),
                    limit=max(1, min(configured_items, 5000)),
                )
                candidates = await self._detect(
                    principal,
                    run,
                    items,
                    settings=settings,
                )
                candidates = sorted(
                    candidates, key=lambda value: str(value.candidate_id)
                )[:max_candidates]
            applied_count = 0
            for candidate in candidates:
                saved = await self._store.save_consolidation_candidate(
                    principal,
                    candidate,
                )
                if auto_apply:
                    try:
                        applied = await self.apply(principal, saved.candidate_id)
                    except SageConflict:
                        # Expected for shared, cross-scope, risky, stale, or
                        # approval-mode candidates. They remain reviewable.
                        continue
                    applied_count += int(applied.state is CandidateState.APPLIED)
            counts = Counter(candidate.kind.value for candidate in candidates)
            completed = run.model_copy(
                update={
                    "state": ConsolidationRunState.COMPLETED,
                    "stats": {
                        "scanned": len(items),
                        "auto_applied": applied_count,
                        **dict(counts),
                    },
                    "completed_at": utc_now(),
                    "updated_at": utc_now(),
                },
            )
            return await self._store.save_consolidation_run(principal, completed)
        except Exception as exc:
            failed = run.model_copy(
                update={
                    "state": ConsolidationRunState.FAILED,
                    "error": str(exc)[:2000],
                    "completed_at": utc_now(),
                    "updated_at": utc_now(),
                },
            )
            await self._store.save_consolidation_run(principal, failed)
            raise

    async def approve(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate:
        ScopePolicy.require_permission(principal, "sage.consolidation.approve")
        candidate = await self._required(principal, candidate_id)
        if candidate.state is not CandidateState.PROPOSED:
            raise SageConflict("only proposed candidates can be approved")
        return await self._save_candidate_state(
            principal,
            candidate,
            CandidateState.APPROVED,
            reviewed_by=principal.user_id,
        )

    async def reject(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate:
        ScopePolicy.require_permission(principal, "sage.consolidation.approve")
        candidate = await self._required(principal, candidate_id)
        if candidate.state is not CandidateState.PROPOSED:
            raise SageConflict("only proposed candidates can be rejected")
        return await self._save_candidate_state(
            principal,
            candidate,
            CandidateState.REJECTED,
            reviewed_by=principal.user_id,
        )

    async def apply(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate:
        candidate = await self._required(principal, candidate_id)
        if candidate.state not in {
            CandidateState.PROPOSED,
            CandidateState.APPROVED,
        }:
            raise SageConflict("candidate cannot be applied from its current state")
        capability = (
            SageCapability.PLAYBOOK_PROMOTION
            if candidate.action is ConsolidationAction.PROMOTE_PLAYBOOK
            else SageCapability.KNOWLEDGE_MERGE
        )
        source_scope_types = {
            ScopeType(snapshot["scope"]["scope_type"])
            for snapshot in candidate.before_snapshots.values()
            if isinstance(snapshot.get("scope"), dict)
            and snapshot["scope"].get("scope_type") is not None
        }
        shared = bool(
            source_scope_types
            & {
                ScopeType.TENANT,
                ScopeType.TEAM,
                ScopeType.PROJECT,
            },
        ) or candidate.scope.scope_type in {
            ScopeType.TENANT,
            ScopeType.TEAM,
            ScopeType.PROJECT,
        }
        cross_scope = (
            len(
                {
                    (
                        snapshot.get("scope", {}).get("scope_type"),
                        snapshot.get("scope", {}).get("scope_id"),
                    )
                    for snapshot in candidate.before_snapshots.values()
                },
            )
            > 1
        )
        decision = await self._control.decision(
            principal,
            capability,
            scope=candidate.scope,
            risk=candidate.risk_level,
            force_approval=(
                shared
                or cross_scope
                or candidate.action is ConsolidationAction.ARCHIVE
                or candidate.action is ConsolidationAction.PROMOTE_PLAYBOOK
                or candidate.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            ),
        )
        if not decision.execute:
            raise SageConflict("candidate capability is currently disabled")
        if candidate.state is CandidateState.PROPOSED and not decision.apply:
            raise SageConflict("candidate requires approval before application")
        if candidate.state is CandidateState.APPROVED:
            ScopePolicy.require_permission(principal, "sage.consolidation.apply")

        await self._require_sources_unchanged(principal, candidate)

        if candidate.action is ConsolidationAction.MERGE:
            await self._apply_merge(principal, candidate)
        elif candidate.action is ConsolidationAction.DISPUTE:
            for source_id in candidate.source_ids:
                await self._catalog.dispute_item(principal, source_id)
        elif candidate.action is ConsolidationAction.ARCHIVE:
            for source_id in candidate.source_ids:
                await self._catalog.archive_item(principal, source_id)
        elif candidate.action is ConsolidationAction.PROMOTE_PLAYBOOK:
            await self._apply_playbook(principal, candidate)

        applied = await self._save_candidate_state(
            principal,
            candidate,
            CandidateState.APPLIED,
            applied_by=principal.user_id,
        )
        await self._audit(principal, applied, "apply")
        return applied

    async def rollback(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate:
        ScopePolicy.require_permission(principal, "sage.consolidation.rollback")
        candidate = await self._required(principal, candidate_id)
        if candidate.state is not CandidateState.APPLIED:
            raise SageConflict("only applied candidates can be rolled back")
        for snapshot in candidate.before_snapshots.values():
            item = KnowledgeItem.model_validate(snapshot)
            await self._store.save_item(principal, item)
        if candidate.action is ConsolidationAction.PROMOTE_PLAYBOOK:
            playbook_id = uuid5(candidate.candidate_id, "sage-playbook")
            playbook = await self._store.get_playbook(principal, playbook_id)
            if playbook is not None:
                await self._store.save_playbook(
                    principal,
                    playbook.model_copy(
                        update={
                            "state": PlaybookState.ROLLED_BACK,
                            "updated_at": utc_now(),
                        },
                    ),
                )
        rolled_back = await self._save_candidate_state(
            principal,
            candidate,
            CandidateState.ROLLED_BACK,
            applied_by=principal.user_id,
        )
        await self._audit(principal, rolled_back, "rollback")
        return rolled_back

    async def _require_sources_unchanged(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
    ) -> None:
        for source_id in candidate.source_ids:
            expected = candidate.before_snapshots.get(str(source_id))
            current = await self._store.get_item(principal, source_id)
            if (
                expected is None
                or current is None
                or (current.model_dump(mode="json") != expected)
            ):
                await self._save_candidate_state(
                    principal,
                    candidate,
                    CandidateState.STALE,
                )
                raise SageConflict(
                    "candidate sources changed after detection; review again",
                )

    async def _detect(
        self,
        principal: Principal,
        run: ConsolidationRun,
        items: list[KnowledgeItem],
        *,
        settings: dict[str, object] | None = None,
    ) -> list[ConsolidationCandidate]:
        candidates: list[ConsolidationCandidate] = []
        exact: dict[str, list[KnowledgeItem]] = defaultdict(list)
        titles: dict[str, list[KnowledgeItem]] = defaultdict(list)
        for item in items:
            exact[self._normalize(item.title + "\n" + item.content)].append(item)
            titles[self._normalize(item.title)].append(item)
        for group in exact.values():
            if len(group) > 1:
                candidates.append(
                    self._candidate(
                        run,
                        ConsolidationKind.DUPLICATE,
                        ConsolidationAction.MERGE,
                        group,
                        RiskLevel.LOW,
                        "Multiple active knowledge items contain the same content.",
                    ),
                )
        for group in titles.values():
            contents = {self._normalize(item.content) for item in group}
            if len(group) > 1 and len(contents) > 1:
                candidates.append(
                    self._candidate(
                        run,
                        ConsolidationKind.CONFLICT,
                        ConsolidationAction.DISPUTE,
                        group,
                        RiskLevel.MEDIUM,
                        "Items with the same business subject contain different guidance.",
                    ),
                )
        now = utc_now()
        for item in items:
            if item.valid_until is not None and item.valid_until <= now:
                candidates.append(
                    self._candidate(
                        run,
                        ConsolidationKind.STALE,
                        ConsolidationAction.ARCHIVE,
                        [item],
                        RiskLevel.LOW,
                        "The knowledge validity window has ended.",
                    ),
                )
            signals = await self._store.list_knowledge_signals(
                principal,
                source_id=item.item_id,
                limit=10,
            )
            if len(signals) >= 3 and item.utility < 0.15:
                candidates.append(
                    self._candidate(
                        run,
                        ConsolidationKind.LOW_UTILITY,
                        ConsolidationAction.ARCHIVE,
                        [item],
                        RiskLevel.MEDIUM,
                        "Repeated use signals show persistently low utility.",
                    ),
                )
        insight_groups: dict[tuple[str, str, str], list[KnowledgeItem]] = defaultdict(
            list
        )
        for item in items:
            if item.kind is not ItemKind.INSIGHT:
                continue
            applicability = item.structured_data.get("applicability", {})
            if not isinstance(applicability, dict):
                continue
            key = tuple(
                str(applicability.get(name, ""))
                for name in ("domain", "process", "task_type")
            )
            if any(key):
                insight_groups[key].append(item)
        for key, group in insight_groups.items():
            if len(group) >= 3:
                candidates.append(
                    self._candidate(
                        run,
                        ConsolidationKind.PLAYBOOK_PROMOTION,
                        ConsolidationAction.PROMOTE_PLAYBOOK,
                        group,
                        RiskLevel.MEDIUM,
                        "Several validated insights support a reusable playbook.",
                        proposed_change={
                            "domain": key[0],
                            "process": key[1],
                            "task_type": key[2],
                        },
                    ),
                )
        candidates.extend(
            await self._semantic_candidates(
                principal,
                run,
                items,
                settings=settings or {},
            ),
        )
        unique = {candidate.candidate_id: candidate for candidate in candidates}
        return list(unique.values())

    async def _semantic_candidates(
        self,
        principal: Principal,
        run: ConsolidationRun,
        items: list[KnowledgeItem],
        *,
        settings: dict[str, object],
    ) -> list[ConsolidationCandidate]:
        if self._semantic is None or self._embeddings is None:
            return []
        threshold = max(
            0.45,
            min(float(settings.get("semantic_similarity_threshold", 0.50)), 0.99),
        )
        maximum = max(
            2,
            min(int(settings.get("semantic_scan_items", 100)), 500),
        )
        active = items[:maximum]
        for item in active:
            await self._semantic.index_item(principal, item)
        by_id = {item.item_id: item for item in active}
        seen: set[tuple[UUID, UUID]] = set()
        candidates: list[ConsolidationCandidate] = []
        for item in active:
            result = await self._embeddings.embed(f"{item.title}\n{item.content}")
            if result.vector is None:
                continue
            matches = await self._store.semantic_search_items(
                principal,
                result.vector,
                limit=6,
            )
            for other, score in matches:
                if other.item_id == item.item_id or other.item_id not in by_id:
                    continue
                pair = tuple(sorted((item.item_id, other.item_id), key=str))
                if pair in seen or score < threshold:
                    continue
                seen.add(pair)
                if self._normalize(item.title + item.content) == self._normalize(
                    other.title + other.content,
                ):
                    continue
                conflict = self._possible_negation_conflict(item.content, other.content)
                candidates.append(
                    self._candidate(
                        run,
                        (
                            ConsolidationKind.CONFLICT
                            if conflict
                            else ConsolidationKind.DUPLICATE
                        ),
                        (
                            ConsolidationAction.DISPUTE
                            if conflict
                            else ConsolidationAction.MERGE
                        ),
                        [item, other],
                        RiskLevel.MEDIUM,
                        (
                            "语义相似的经验可能包含相反做法，需要人工核对。"
                            if conflict
                            else "语义相似的经验可能重复，需要人工确认后合并。"
                        ),
                        proposed_change={
                            "semantic_score": f"{score:.4f}",
                            "embedding_model": self._semantic.model_key,
                        },
                    ),
                )
        return candidates

    @staticmethod
    def _possible_negation_conflict(left: str, right: str) -> bool:
        markers = ("不得", "禁止", "不要", "不能", "不可", "not ", "never ")
        left_negative = any(marker in left.casefold() for marker in markers)
        right_negative = any(marker in right.casefold() for marker in markers)
        return left_negative != right_negative

    @staticmethod
    def _candidate(
        run: ConsolidationRun,
        kind: ConsolidationKind,
        action: ConsolidationAction,
        items: list[KnowledgeItem],
        risk: RiskLevel,
        rationale: str,
        proposed_change: dict[str, str] | None = None,
    ) -> ConsolidationCandidate:
        return ConsolidationCandidate.create(
            tenant_id=run.tenant_id,
            run_id=run.run_id,
            kind=kind,
            action=action,
            source_ids=tuple(item.item_id for item in items),
            scope=items[0].scope,
            risk_level=risk,
            rationale=rationale,
            proposed_change=proposed_change,
            before_snapshots={
                str(item.item_id): item.model_dump(mode="json") for item in items
            },
        )

    async def _apply_merge(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
    ) -> None:
        for source_id in candidate.source_ids[1:]:
            item = await self._store.get_item(principal, source_id)
            if item is not None and item.state is ItemState.ACTIVE:
                await self._store.save_item(
                    principal,
                    item.model_copy(
                        update={
                            "state": ItemState.SUPERSEDED,
                            "structured_data": {
                                **item.structured_data,
                                "duplicate_of": str(candidate.source_ids[0]),
                            },
                            "updated_at": utc_now(),
                        },
                    ),
                )

    async def _apply_playbook(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
    ) -> None:
        source_items = [
            item
            for source_id in candidate.source_ids
            if (item := await self._store.get_item(principal, source_id)) is not None
        ]
        name = str(candidate.proposed_change.get("process") or "SAGE playbook")
        playbook = Playbook(
            playbook_id=uuid5(candidate.candidate_id, "sage-playbook"),
            tenant_id=principal.tenant_id,
            scope=candidate.scope,
            name=f"{name[:220]} playbook",
            scenario_schema=dict(candidate.proposed_change),
            steps=tuple(
                {"action": item.content, "source_id": str(item.item_id)}
                for item in source_items
            ),
            state=PlaybookState.ACTIVE,
            evidence_count=len(source_items),
            approved_by=principal.user_id,
        )
        await self._store.save_playbook(principal, playbook)

    async def _required(
        self,
        principal: Principal,
        candidate_id: UUID,
    ) -> ConsolidationCandidate:
        candidate = await self._store.get_consolidation_candidate(
            principal,
            candidate_id,
        )
        if candidate is None:
            raise SageNotFound(f"SAGE candidate not found: {candidate_id}")
        return candidate

    async def _save_candidate_state(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
        state: CandidateState,
        **updates: UUID,
    ) -> ConsolidationCandidate:
        changed = candidate.model_copy(
            update={
                "state": state,
                "version": candidate.version + 1,
                "updated_at": utc_now(),
                **updates,
            },
        )
        return await self._store.save_consolidation_candidate(principal, changed)

    async def _audit(
        self,
        principal: Principal,
        candidate: ConsolidationCandidate,
        action: str,
    ) -> None:
        await self._store.append_trace(
            principal,
            Trace.from_principal(
                principal,
                event_key=(
                    f"governance:{candidate.candidate_id}:{candidate.version}:{action}"
                ),
                trace_type=TraceType.GOVERNANCE,
                payload={
                    "candidate_id": str(candidate.candidate_id),
                    "action": action,
                    "kind": candidate.kind.value,
                    "source_ids": [str(value) for value in candidate.source_ids],
                },
            ),
        )

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().casefold())


__all__ = ["ConsolidationService"]
