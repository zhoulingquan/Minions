from __future__ import annotations

from uuid import uuid4

import pytest

from minions.sage.models import ItemKind, ItemState, Principal, ScopeRef, ScopeType
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*, tenant_id=None) -> Principal:
    return Principal(
        tenant_id=tenant_id or uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="semantic-test",
        session_id="semantic-session",
    )


@pytest.mark.asyncio
async def test_runtime_indexes_and_recalls_chinese_similarity_in_sqlite(
    tmp_path,
) -> None:
    principal = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        item = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="客户月度对账流程",
            content="先核验源台账，再汇总差异并出具交付包。",
            state=ItemState.ACTIVE,
        )

        pack = await runtime.prepare(principal, "月度客户对账复核")

        assert item.item_id in pack.source_ids
        selected = next(
            value
            for value in pack.receipt.selections
            if value.source_id == item.item_id
        )
        assert selected.score_components["semantic"] > 0
        assert "semantic" in selected.reasons
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_sqlite_semantic_search_is_tenant_isolated(tmp_path) -> None:
    first = _principal()
    second = _principal()
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        foreign = await runtime.catalog.create_item(
            second,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(second.user_id),
            ),
            title="客户月度对账流程",
            content="另一个企业的内部流程。",
            state=ItemState.ACTIVE,
        )

        pack = await runtime.prepare(first, "月度客户对账复核")

        assert foreign.item_id not in pack.source_ids
    finally:
        await runtime.close()
