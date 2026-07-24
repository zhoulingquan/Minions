# -*- coding: utf-8 -*-
"""UT for the injected tool_adapter approval-scope consumer.

``_ask_user_approval`` must pick the recorded rule target from the user's
chosen scope: SIMILAR -> the generalized pattern, EXACT/None -> the literal
target. This exercises that decision through ``ApprovalRequester`` without
an app singleton, real model, HTTP, or AgentScope runtime.
"""
from __future__ import annotations

# pylint: disable=protected-access

from minions.governance.policy import ToolCallSpec
from minions.security.tool_guard.approval import (
    ApprovalDecision,
    ApprovalScope,
)


class _FakeApprovalRequester:
    def __init__(self, scope: ApprovalScope | None) -> None:
        self._scope = scope
        self.requests: list[dict] = []

    async def request_approval(self, **kwargs):  # noqa: ANN
        self.requests.append(kwargs)
        return type(
            "ApprovalResponse",
            (),
            {
                "decision": ApprovalDecision.APPROVED,
                "scope": self._scope,
            },
        )()


class _FakeGovernor:
    def __init__(self) -> None:
        self.audits: list = []
        self.added: list[tuple[ToolCallSpec, str]] = []

    def audit(self, tc_spec, decision):  # noqa: ANN
        self.audits.append((tc_spec, decision))

    async def add_approved_rule(
        self,
        tc_spec,
        *,
        generalized_target,
    ):  # noqa: ANN
        self.added.append((tc_spec, generalized_target))
        return True

    def is_builtin_ask(self, _tc_spec):  # noqa: ANN
        return False


def _tc(target: str = "git status") -> ToolCallSpec:
    return ToolCallSpec(
        tool_name="Bash",
        target=target,
        agent_id="agent-1",
        session_id="session-1",
    )


async def _run_approval(scope: ApprovalScope | None, monkeypatch):
    """Drive ``_ask_user_approval`` through an injected requester."""
    from minions.governance import tool_adapter

    requester = _FakeApprovalRequester(scope)
    import minions.governance.generalize as generalize_mod

    async def _fake_generalize(
        _tool_name,
        _target,
        _source,
        agent_id=None,
        model_factory=None,
    ):  # noqa: ANN
        del agent_id, model_factory
        return "git *"

    monkeypatch.setattr(
        generalize_mod,
        "generalize_target_for_approval",
        _fake_generalize,
        raising=False,
    )

    governor = _FakeGovernor()
    tc = _tc()
    await tool_adapter._ask_user_approval(
        governor=governor,
        tc_spec=tc,
        approval_requester=requester,
        model_factory=None,
        request_context={
            "user_id": "u",
            "channel": "console",
            "root_session_id": "session-1",
            "root_agent_id": "agent-1",
            "tool_call_id": "tc-1",
        },
        source="No rule hit",
    )
    return governor, requester


class TestApprovalScopeConsumer:
    """The consumer picks the recorded target from the chosen scope."""

    async def test_similar_records_pattern(self, monkeypatch):
        governor, _requester = await _run_approval(
            ApprovalScope.SIMILAR,
            monkeypatch,
        )
        assert governor.added, "no rule was recorded"
        _tc_spec, target = governor.added[0]
        assert target == "git *"
        # Audit reason carries the scope label.
        _spec, decision = governor.audits[-1]
        assert "similar" in decision.reason

    async def test_exact_records_literal(self, monkeypatch):
        governor, _requester = await _run_approval(
            ApprovalScope.EXACT,
            monkeypatch,
        )
        _tc_spec, target = governor.added[0]
        assert target == "git status"
        _spec, decision = governor.audits[-1]
        assert "exact" in decision.reason

    async def test_none_scope_defaults_to_exact(self, monkeypatch):
        """No scope (IM channel / CLI) → records the literal target."""
        governor, _pending = await _run_approval(None, monkeypatch)
        _tc_spec, target = governor.added[0]
        assert target == "git status"
        _spec, decision = governor.audits[-1]
        assert "exact" in decision.reason

    async def test_display_payload_carries_both_targets(self, monkeypatch):
        _governor, requester = await _run_approval(
            ApprovalScope.SIMILAR,
            monkeypatch,
        )
        display = requester.requests[0]["extra"]["display"]
        assert display["is_generalized"] is True
        assert display["exact_target"] == "git status"
        assert display["similar_target"] == "git *"

    async def test_missing_requester_fails_closed(self):
        from agentscope.permission import PermissionBehavior
        from minions.governance import tool_adapter

        governor = _FakeGovernor()
        decision = await tool_adapter._ask_user_approval(
            governor=governor,
            tc_spec=_tc(),
            approval_requester=None,
            model_factory=None,
            request_context={},
        )

        assert decision.behavior == PermissionBehavior.DENY
        assert "not configured" in decision.message
        assert governor.added == []
