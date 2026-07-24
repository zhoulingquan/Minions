# -*- coding: utf-8 -*-
"""Tests for tenant capability policy resolution and decisions."""

from uuid import uuid4

import pytest

from minions.sage.errors import SageAccessDenied
from minions.sage.models import (
    ActivationMode,
    RiskLevel,
    SageCapability,
    Principal,
    ScopeRef,
    ScopeType,
)
from minions.sage.control import PolicyCenter
from minions.sage.sqlite_store import SQLiteSageStore


def _principal(*permissions: str) -> Principal:
    return Principal(
        tenant_id=uuid4(),
        user_id=uuid4(),
        agent_uid=uuid4(),
        source="test",
        session_id="control-session",
        permissions=frozenset(permissions),
    )


@pytest.mark.asyncio
async def test_policy_center_uses_defaults_and_exact_scope_override(
    tmp_path,
) -> None:
    principal = _principal("sage.policy.manage")
    scope = ScopeRef(
        scope_type=ScopeType.USER,
        scope_id=str(principal.user_id),
    )
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        center = PolicyCenter(store)
        default = await center.resolve(
            principal,
            SageCapability.FEEDBACK_LEARNING,
        )
        assert default.mode is ActivationMode.SHADOW

        await center.set_policy(
            principal,
            capability=SageCapability.FEEDBACK_LEARNING,
            mode=ActivationMode.APPROVAL,
        )
        scoped = await center.set_policy(
            principal,
            capability=SageCapability.FEEDBACK_LEARNING,
            mode=ActivationMode.AUTO,
            scope=scope,
        )

        assert (
            await center.resolve(
                principal,
                SageCapability.FEEDBACK_LEARNING,
            )
        ).mode is ActivationMode.APPROVAL
        assert (
            await center.resolve(
                principal,
                SageCapability.FEEDBACK_LEARNING,
                scope=scope,
            )
        ) == scoped
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_policy_updates_require_manage_permission(tmp_path) -> None:
    principal = _principal()
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        with pytest.raises(SageAccessDenied, match="sage.policy.manage"):
            await PolicyCenter(store).set_policy(
                principal,
                capability=SageCapability.NIGHTLY_CONSOLIDATION,
                mode=ActivationMode.AUTO,
            )
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_policy_decision_is_fail_closed_above_auto_risk(
    tmp_path,
) -> None:
    principal = _principal("sage.policy.manage")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        center = PolicyCenter(store)
        await center.set_policy(
            principal,
            capability=SageCapability.KNOWLEDGE_MERGE,
            mode=ActivationMode.AUTO,
            max_auto_risk=RiskLevel.LOW,
        )

        low = await center.decision(
            principal,
            SageCapability.KNOWLEDGE_MERGE,
            risk=RiskLevel.LOW,
        )
        high = await center.decision(
            principal,
            SageCapability.KNOWLEDGE_MERGE,
            risk=RiskLevel.HIGH,
        )
        forced = await center.decision(
            principal,
            SageCapability.KNOWLEDGE_MERGE,
            risk=RiskLevel.LOW,
            force_approval=True,
        )

        assert low.execute and low.apply
        assert high.execute and not high.apply and high.requires_approval
        assert forced.execute and not forced.apply and forced.requires_approval
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_off_policy_prevents_execution(tmp_path) -> None:
    principal = _principal("sage.policy.manage")
    store = SQLiteSageStore(tmp_path / "sage.db")
    await store.start()
    try:
        center = PolicyCenter(store)
        await center.set_policy(
            principal,
            capability=SageCapability.CROSS_SCOPE_TRANSFER,
            mode=ActivationMode.OFF,
        )
        decision = await center.decision(
            principal,
            SageCapability.CROSS_SCOPE_TRANSFER,
        )
        assert not decision.execute
        assert not decision.apply
        assert not decision.requires_approval
    finally:
        await store.close()
