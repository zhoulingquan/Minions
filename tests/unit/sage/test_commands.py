"""Tests for SAGE-native command registration."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from minions.runtime.builtin_commands import collect_builtin_command_specs
from minions.sage.commands import build_sage_command_specs
from minions.sage.identity import TrustedSageIdentity
from minions.sage.models import ItemKind, ItemState, ScopeRef, ScopeType, TraceType
from minions.sage.runtime import SageRuntime
from minions.sage.sqlite_store import SQLiteSageStore


def test_runtime_registers_sage_names_and_retires_old_memory_commands() -> None:
    names = {spec.name for spec in collect_builtin_command_specs()}
    assert {
        "sage-status",
        "sage-find",
        "sage-feedback",
        "sage-policy",
    }.issubset(names)
    assert {"dream", "memorize", "summarize_status"}.isdisjoint(names)


@pytest.mark.asyncio
async def test_sage_find_returns_only_authorized_sources(tmp_path) -> None:
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        tenant_id = uuid4()
        user_id = uuid4()
        identity = TrustedSageIdentity(tenant_id, user_id, "test")
        ctx = SimpleNamespace(
            agent_id="finance-agent",
            session_id="command-session",
            extras={"sage.identity": identity},
            workspace=SimpleNamespace(sage_runtime=runtime),
        )
        from minions.sage.lifecycle import resolve_sage_principal

        principal = resolve_sage_principal(ctx)
        assert principal is not None
        item = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(user_id),
            ),
            title="Invoice review lesson",
            content="Review invoice exceptions before totals.",
            state=ItemState.ACTIVE,
        )
        find = next(
            spec for spec in build_sage_command_specs() if spec.name == "sage-find"
        )
        result = await find.handler(ctx, "invoice review")
        text = result.get_text_content()
        assert "Invoice review lesson" in text
        assert str(item.item_id) in text
        assert "Receipt:" in text
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_sage_feedback_records_recall_correction(tmp_path) -> None:
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        tenant_id = uuid4()
        user_id = uuid4()
        ctx = SimpleNamespace(
            agent_id="finance-agent",
            session_id="command-session",
            extras={
                "sage.identity": TrustedSageIdentity(tenant_id, user_id, "test"),
            },
            workspace=SimpleNamespace(sage_runtime=runtime),
        )
        from minions.sage.lifecycle import resolve_sage_principal

        principal = resolve_sage_principal(ctx)
        assert principal is not None
        source = await runtime.catalog.create_item(
            principal,
            kind=ItemKind.INSIGHT,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            title="Current policy",
            content="The current policy was recalled for review.",
            state=ItemState.ACTIVE,
        )
        turn = await runtime.begin(
            principal,
            scope=ScopeRef(
                scope_type=ScopeType.USER,
                scope_id=str(principal.user_id),
            ),
            user_input="current policy",
        )
        pack = await runtime.prepare_for_turn(principal, turn, "current policy")
        assert pack.receipt is not None
        receipt_id = pack.receipt.receipt_id
        source_id = source.item_id
        feedback = next(
            spec for spec in build_sage_command_specs() if spec.name == "sage-feedback"
        )
        result = await feedback.handler(
            ctx,
            f"{receipt_id} outdated {source_id} policy changed",
        )
        assert "Feedback recorded" in result.get_text_content()

        traces = await runtime.store.list_traces(principal)
        recorded = next(
            trace for trace in traces if trace.trace_type is TraceType.FEEDBACK
        )
        assert recorded.payload["receipt_id"] == str(receipt_id)
        assert recorded.payload["source_id"] == str(source_id)
        assert recorded.payload["verdict"] == "outdated"
    finally:
        await runtime.close()


@pytest.mark.asyncio
async def test_sage_policy_shows_conservative_defaults(tmp_path) -> None:
    runtime = SageRuntime(SQLiteSageStore(tmp_path / "sage.db"))
    await runtime.start()
    try:
        tenant_id = uuid4()
        ctx = SimpleNamespace(
            agent_id="finance-agent",
            session_id="command-session",
            extras={
                "sage.identity": TrustedSageIdentity(
                    tenant_id,
                    uuid4(),
                    "test",
                ),
            },
            workspace=SimpleNamespace(sage_runtime=runtime),
        )
        policy = next(
            spec for spec in build_sage_command_specs() if spec.name == "sage-policy"
        )
        result = await policy.handler(ctx, "")
        text = result.get_text_content()
        assert "hybrid_recall: auto" in text
        assert "nightly_consolidation: shadow" in text
        assert "cross_scope_transfer: off" in text
    finally:
        await runtime.close()
