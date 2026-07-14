"""Tests for bounded, scoped SAGE retrieval."""

from datetime import timedelta
from uuid import uuid4

import pytest

from minions.sage.catalog import SageCatalog
from minions.sage.models import (
    ItemKind,
    ItemState,
    KnowledgeItem,
    Playbook,
    PlaybookState,
    Principal,
    RecallQuery,
    ScopeRef,
    ScopeType,
    RecallSection,
    utc_now,
)
from minions.sage.recall import RecallPlanner
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*permissions: str) -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="web",
        session_id="recall-session",
        permissions=frozenset(permissions),
    )


@pytest.mark.asyncio
async def test_recall_returns_only_active_unexpired_current_tenant_items(tmp_path) -> None:
    principal = _principal()
    foreign = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        active = await catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Monthly close deadline",
            content="Monthly close is due on business day three.",
            state=ItemState.ACTIVE,
        )
        await catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Draft monthly close guess",
            content="Unverified monthly close guidance.",
            state=ItemState.DRAFT,
        )
        expired = KnowledgeItem(
            tenant_id=principal.tenant_id,
            kind=ItemKind.RULE,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Expired monthly close rule",
            content="This monthly close rule is obsolete.",
            state=ItemState.ACTIVE,
            valid_until=utc_now() - timedelta(days=1),
        )
        await store.save_item(principal, expired)
        foreign_item = await SageCatalog(store).create_item(
            foreign,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(foreign.user_id),
            ),
            title="Foreign monthly close",
            content="Other tenant monthly close data.",
            state=ItemState.ACTIVE,
        )

        pack = await RecallPlanner(store).prepare(
            principal,
            "monthly close",
            token_budget=500,
        )
        assert [item.item_id for item in pack.known_facts] == [active.item_id]
        assert foreign_item.item_id not in pack.source_ids
        assert expired.item_id not in pack.source_ids
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recall_prefers_more_specific_scope(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        agent_item = await catalog.create_item(
            principal,
            kind=ItemKind.RULE,
            scope=ScopeRef(
                scope_type=ScopeType.AGENT,
                scope_id=str(principal.agent_uid),
            ),
            title="Invoice review agent rule",
            content="Invoice review uses the general checklist.",
            state=ItemState.ACTIVE,
            importance=1,
        )
        user_item = await catalog.create_item(
            principal,
            kind=ItemKind.PREFERENCE,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Invoice review user preference",
            content="Invoice review presents exceptions first.",
            state=ItemState.ACTIVE,
            importance=0.1,
        )
        pack = await RecallPlanner(store).prepare(principal, "invoice review")
        assert [item.item_id for item in pack.known_facts[:2]] == [
            user_item.item_id,
            agent_item.item_id,
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recall_includes_only_active_playbooks_and_source_links(tmp_path) -> None:
    principal = _principal()
    scope = ScopeRef(
        scope_type=ScopeType.AGENT,
        scope_id=str(principal.agent_uid),
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        active = Playbook(
            tenant_id=principal.tenant_id,
            scope=scope,
            name="Vendor onboarding",
            steps=({"action": "verify vendor registration"},),
            state=PlaybookState.ACTIVE,
        )
        draft = Playbook(
            tenant_id=principal.tenant_id,
            scope=scope,
            name="Vendor onboarding draft",
            steps=({"action": "unverified step"},),
            state=PlaybookState.DRAFT,
        )
        await store.save_playbook(principal, active)
        await store.save_playbook(principal, draft)

        pack = await RecallPlanner(store).prepare(principal, "Vendor onboarding")
        assert [playbook.playbook_id for playbook in pack.playbooks] == [
            active.playbook_id,
        ]
        assert pack.source_ids == (active.playbook_id,)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recall_respects_token_budget(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        for number in range(8):
            await catalog.create_item(
                principal,
                kind=ItemKind.INSIGHT,
                scope=ScopeRef(
                    scope_type=ScopeType.USER,
                    scope_id=str(principal.user_id),
                ),
                title=f"Budget insight {number}",
                content="budget " + ("useful detail " * 8),
                state=ItemState.ACTIVE,
            )

        pack = await RecallPlanner(store).prepare(
            principal,
            "budget",
            token_budget=80,
        )
        assert pack.estimated_tokens <= 80
        assert len(pack.insights) < 8
        assert pack.source_ids == tuple(item.item_id for item in pack.insights)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recall_always_loads_anchors_and_separates_warnings(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        scope = ScopeRef(
            scope_type=ScopeType.USER,
            scope_id=str(principal.user_id),
        )
        anchor = await catalog.create_item(
            principal,
            kind=ItemKind.ANCHOR,
            scope=scope,
            title="Stable company context",
            content="The company closes its books on a calendar-year basis.",
            state=ItemState.ACTIVE,
        )
        warning = await catalog.create_item(
            principal,
            kind=ItemKind.WARNING,
            scope=scope,
            title="Invoice export warning",
            content="Invoice export must remove bank account details.",
            state=ItemState.ACTIVE,
        )

        pack = await RecallPlanner(store).prepare(principal, "invoice export")

        assert [item.item_id for item in pack.anchors] == [anchor.item_id]
        assert [item.item_id for item in pack.warnings] == [warning.item_id]
        assert warning.item_id not in [item.item_id for item in pack.known_facts]
        assert pack.source_ids[0] == anchor.item_id
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_recall_uses_independent_section_budgets_and_emits_receipt(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        scope = ScopeRef(
            scope_type=ScopeType.USER,
            scope_id=str(principal.user_id),
        )
        fact = await catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=scope,
            title="Budget approval fact",
            content="Budget approval requires the finance owner.",
            state=ItemState.ACTIVE,
        )
        for number in range(5):
            await catalog.create_item(
                principal,
                kind=ItemKind.INSIGHT,
                scope=scope,
                title=f"Budget approval insight {number}",
                content="budget approval " + ("long experience " * 15),
                state=ItemState.ACTIVE,
            )

        pack = await RecallPlanner(store).prepare(
            principal,
            "budget approval",
            token_budget=200,
        )

        assert [item.item_id for item in pack.known_facts] == [fact.item_id]
        assert pack.receipt is not None
        assert pack.receipt.tenant_id == principal.tenant_id
        assert pack.receipt.section_tokens == pack.section_tokens
        assert sum(pack.section_tokens.values()) == pack.estimated_tokens
        for section, used in pack.section_tokens.items():
            assert used <= pack.receipt.budget.by_section()[section]
        fact_selection = next(
            selection
            for selection in pack.receipt.selections
            if selection.source_id == fact.item_id
        )
        assert fact_selection.section is RecallSection.FACT
        assert "active" in fact_selection.reasons
        assert fact_selection.score_components["scope"] > 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_hybrid_recall_finds_entity_match_without_lexical_match(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        item = await SageCatalog(store).create_item(
            principal,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Vendor operating profile",
            content="Use the established approval route.",
            structured_data={"entities": ["Acme Holdings"]},
            state=ItemState.ACTIVE,
        )

        pack = await RecallPlanner(store).prepare(
            principal,
            RecallQuery(text="renewal", entities=("Acme Holdings",)),
        )

        assert item.item_id in pack.source_ids
        assert pack.receipt is not None
        selection = next(
            value
            for value in pack.receipt.selections
            if value.source_id == item.item_id
        )
        assert selection.score_components["entity"] == 1
        assert pack.receipt.ranking_mode == "hybrid"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_shadow_recall_records_new_ranking_without_applying_it(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        scope = ScopeRef(
            scope_type=ScopeType.USER,
            scope_id=str(principal.user_id),
        )
        lexical = await catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=scope,
            title="Renewal checklist",
            content="General renewal steps.",
            importance=0.9,
            state=ItemState.ACTIVE,
        )
        entity = await catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=scope,
            title="Acme operating profile",
            content="Special approval route.",
            structured_data={"entities": ["Acme Holdings"]},
            importance=0.1,
            state=ItemState.ACTIVE,
        )

        pack = await RecallPlanner(store).prepare(
            principal,
            RecallQuery(text="renewal", entities=("Acme Holdings",)),
            shadow=True,
        )

        assert pack.known_facts[0].item_id == lexical.item_id
        assert pack.receipt is not None
        assert pack.receipt.ranking_mode == "shadow"
        assert entity.item_id in pack.receipt.shadow_source_ids
    finally:
        await store.close()
