"""Semantic indexing coordinator shared by development and production stores."""

from __future__ import annotations

import os
from uuid import UUID

from .embeddings import EmbeddingService
from .models import ItemState, KnowledgeItem, Principal
from .store import SageStore


class SemanticIndexer:
    """Index active knowledge with bounded, retryable provider calls."""

    def __init__(self, store: SageStore, embeddings: EmbeddingService) -> None:
        self._store = store
        self._embeddings = embeddings
        provider = embeddings.provider
        self.model_key = str(
            getattr(provider, "model", provider.__class__.__name__),
        )[:200]
        self._indexed: set[tuple[UUID, UUID, int, str]] = set()
        self._backfill_limit = max(
            1,
            min(
                int(os.environ.get("MINIONS_SAGE_EMBEDDING_BACKFILL_LIMIT", "50")),
                500,
            ),
        )

    async def index_item(
        self,
        principal: Principal,
        item: KnowledgeItem,
    ) -> bool:
        if item.state is not ItemState.ACTIVE:
            return False
        key = (item.tenant_id, item.item_id, item.version, self.model_key)
        if key in self._indexed:
            return True
        result = await self._embeddings.embed(f"{item.title}\n{item.content}")
        if result.vector is None:
            return False
        await self._store.save_item_embedding(
            principal,
            item.item_id,
            result.vector,
            model=self.model_key,
            item_version=item.version,
        )
        self._indexed.add(key)
        return True

    async def ensure_active(self, principal: Principal) -> int:
        items = await self._store.list_items(
            principal,
            states=(ItemState.ACTIVE,),
            limit=self._backfill_limit,
        )
        indexed = 0
        for item in items:
            indexed += int(await self.index_item(principal, item))
        return indexed


__all__ = ["SemanticIndexer"]
