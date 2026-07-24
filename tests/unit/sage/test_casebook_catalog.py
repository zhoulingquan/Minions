# -*- coding: utf-8 -*-
"""Tests for SAGE CaseBook and SageCatalog services."""

from uuid import uuid4

import pytest

from minions.sage.casebook import CaseBook
from minions.sage.catalog import SageCatalog
from minions.sage.errors import SageConflict
from minions.sage.models import (
    CaseOutcome,
    CaseState,
    ItemKind,
    ItemState,
    Principal,
    ScopeRef,
    ScopeType,
)
from minions.sage.sqlite_store import SQLiteSageStore


def _principal() -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="web",
        session_id="case-session",
    )


@pytest.mark.asyncio
async def test_casebook_opens_and_finishes_a_business_case(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        cases = CaseBook(store)
        case = await cases.open_case(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            domain="finance",
            process="monthly-close",
            task_type="management-report",
            goal="Deliver the approved monthly report",
        )
        assert case.state is CaseState.OPEN

        finished = await cases.finish_case(
            principal,
            case.case_id,
            outcome=CaseOutcome.SUCCESS,
            decision_summary="Reconciled source systems before aggregation.",
            outcome_metrics={"accepted": True, "duration_minutes": 42},
        )
        assert finished.state is CaseState.COMPLETED
        assert finished.completed_at is not None
        assert finished.outcome is CaseOutcome.SUCCESS
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_casebook_does_not_learn_from_unknown_outcome(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        cases = CaseBook(store)
        case = await cases.open_case(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            goal="Unverified task",
        )
        with pytest.raises(SageConflict, match="outcome"):
            await cases.finish_case(
                principal,
                case.case_id,
                outcome=CaseOutcome.UNKNOWN,
            )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_catalog_revision_preserves_version_chain(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        original = await catalog.create_item(
            principal,
            kind=ItemKind.RULE,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Report review order",
            content="Review totals before exceptions.",
            state=ItemState.ACTIVE,
        )
        revised = await catalog.revise_item(
            principal,
            original.item_id,
            content=(
                "Review source reconciliation, then totals, then "
                "exceptions."
            ),
        )

        old = await store.get_item(principal, original.item_id)
        assert old is not None
        assert old.state is ItemState.SUPERSEDED
        assert revised.version == 2
        assert revised.supersedes_id == original.item_id
        assert revised.state is ItemState.DRAFT
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_catalog_can_mark_active_fact_as_disputed(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        catalog = SageCatalog(store)
        item = await catalog.create_item(
            principal,
            kind=ItemKind.FACT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Approval deadline",
            content="Approval is due Friday.",
            state=ItemState.ACTIVE,
        )
        disputed = await catalog.dispute_item(principal, item.item_id)
        assert disputed.state is ItemState.DISPUTED
    finally:
        await store.close()
