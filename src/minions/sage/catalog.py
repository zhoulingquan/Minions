"""Versioned knowledge catalog for SAGE."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from .errors import SageConflict, SageNotFound
from .models import (
    Classification,
    ItemKind,
    ItemState,
    KnowledgeItem,
    Principal,
    ScopeRef,
    utc_now,
)
from .policy import ScopePolicy
from .store import SageStore


class SageCatalog:
    """Creates and revises evidence-linked, scope-bound knowledge items."""

    def __init__(self, store: SageStore, semantic=None) -> None:
        self._store = store
        self._semantic = semantic

    async def create_item(
        self,
        principal: Principal,
        *,
        kind: ItemKind,
        scope: ScopeRef,
        title: str,
        content: str,
        state: ItemState = ItemState.DRAFT,
        structured_data: dict[str, Any] | None = None,
        evidence_trace_ids: tuple[UUID, ...] = (),
        confidence: float = 0.5,
        importance: float = 0.5,
        classification: Classification = Classification.INTERNAL,
    ) -> KnowledgeItem:
        ScopePolicy.require_scope(principal, scope)
        item = KnowledgeItem(
            tenant_id=principal.tenant_id,
            kind=kind,
            scope=scope,
            classification=classification,
            title=title,
            content=content,
            state=state,
            structured_data=structured_data or {},
            evidence_trace_ids=tuple(dict.fromkeys(evidence_trace_ids)),
            confidence=confidence,
            importance=importance,
        )
        saved = await self._store.save_item(principal, item)
        if self._semantic is not None and saved.state is ItemState.ACTIVE:
            await self._semantic.index_item(principal, saved)
        return saved

    async def revise_item(
        self,
        principal: Principal,
        item_id: UUID,
        *,
        content: str,
        title: str | None = None,
        evidence_trace_ids: tuple[UUID, ...] | None = None,
    ) -> KnowledgeItem:
        current = await self._required_item(principal, item_id)
        if current.state in {ItemState.ERASED, ItemState.ARCHIVED}:
            raise SageConflict(f"item cannot be revised from state {current.state}")

        now = utc_now()
        superseded = current.model_copy(
            update={"state": ItemState.SUPERSEDED, "updated_at": now},
        )
        await self._store.save_item(principal, superseded)

        revised = KnowledgeItem(
            tenant_id=current.tenant_id,
            kind=current.kind,
            scope=current.scope,
            classification=current.classification,
            title=title if title is not None else current.title,
            content=content,
            structured_data=current.structured_data,
            evidence_trace_ids=(
                tuple(dict.fromkeys(evidence_trace_ids))
                if evidence_trace_ids is not None
                else current.evidence_trace_ids
            ),
            confidence=current.confidence,
            importance=current.importance,
            utility=current.utility,
            state=ItemState.DRAFT,
            version=current.version + 1,
            supersedes_id=current.item_id,
            valid_from=now,
            valid_until=current.valid_until,
            created_at=now,
            updated_at=now,
        )
        return await self._store.save_item(principal, revised)

    async def dispute_item(
        self,
        principal: Principal,
        item_id: UUID,
    ) -> KnowledgeItem:
        item = await self._required_item(principal, item_id)
        if item.state in {
            ItemState.ERASED,
            ItemState.ARCHIVED,
            ItemState.SUPERSEDED,
        }:
            raise SageConflict(f"item cannot be disputed from state {item.state}")
        disputed = item.model_copy(
            update={"state": ItemState.DISPUTED, "updated_at": utc_now()},
        )
        return await self._store.save_item(principal, disputed)

    async def archive_item(
        self,
        principal: Principal,
        item_id: UUID,
    ) -> KnowledgeItem:
        item = await self._required_item(principal, item_id)
        if item.state in {ItemState.ARCHIVED, ItemState.ERASED}:
            return item
        archived = item.model_copy(
            update={"state": ItemState.ARCHIVED, "updated_at": utc_now()},
        )
        return await self._store.save_item(principal, archived)

    async def adjust_utility(
        self,
        principal: Principal,
        item_id: UUID,
        *,
        utility: float,
    ) -> KnowledgeItem:
        """Publish a new active version with a bounded learned utility."""

        current = await self._required_item(principal, item_id)
        if current.state is not ItemState.ACTIVE:
            raise SageConflict("utility can only be adjusted on active knowledge")
        bounded = max(0.0, min(float(utility), 1.0))
        if bounded == current.utility:
            return current
        now = utc_now()
        retired = current.model_copy(
            update={"state": ItemState.SUPERSEDED, "updated_at": now},
        )
        await self._store.save_item(principal, retired)
        learned = current.model_copy(
            update={
                "item_id": uuid4(),
                "utility": bounded,
                "state": ItemState.ACTIVE,
                "version": current.version + 1,
                "supersedes_id": current.item_id,
                "valid_from": now,
                "created_at": now,
                "updated_at": now,
            },
        )
        return await self._store.save_item(principal, learned)

    async def _required_item(
        self,
        principal: Principal,
        item_id: UUID,
    ) -> KnowledgeItem:
        item = await self._store.get_item(principal, item_id)
        if item is None:
            raise SageNotFound(f"SAGE catalog item not found: {item_id}")
        return item
