# -*- coding: utf-8 -*-
"""Approval injection contracts for the generic runtime tool guard."""
from __future__ import annotations

from typing import Any

import pytest
from agentscope.permission import PermissionBehavior

from minions.agents.runtime_builder import AgentBuilder
from minions.runtime import tool_guard
from minions.security.tool_guard.approval import ApprovalDecision


class _ApprovalRequester:
    def __init__(self, decision: ApprovalDecision) -> None:
        self.decision = decision
        self.calls: list[dict[str, Any]] = []

    async def request_approval(self, **kwargs: Any) -> ApprovalDecision:
        self.calls.append(kwargs)
        return self.decision


@pytest.mark.asyncio
async def test_approval_required_without_requester_fails_closed() -> None:
    result = await tool_guard._ask_user_approval(
        approval_requester=None,
        agent_id="agent-1",
        tool_name="dangerous_tool",
        input_data={"path": "important.txt"},
        guard_result=tool_guard._strict_info_guard_result(
            "dangerous_tool",
            {"path": "important.txt"},
        ),
        request_context={"session_id": "session-1"},
    )

    assert result.behavior == PermissionBehavior.DENY
    assert "approval requester is not configured" in result.message.lower()


@pytest.mark.asyncio
async def test_injected_requester_handles_approval() -> None:
    requester = _ApprovalRequester(ApprovalDecision.APPROVED)
    result = await tool_guard._ask_user_approval(
        approval_requester=requester,
        agent_id="agent-1",
        tool_name="dangerous_tool",
        input_data={"path": "important.txt"},
        guard_result=tool_guard._strict_info_guard_result(
            "dangerous_tool",
            {"path": "important.txt"},
        ),
        request_context={"session_id": "session-1"},
    )

    assert result.behavior == PermissionBehavior.ALLOW
    assert requester.calls[0]["tool_name"] == "dangerous_tool"
    assert requester.calls[0]["request_context"] == {
        "session_id": "session-1",
    }


def test_agent_builder_passes_requester_to_runtime_guard(monkeypatch) -> None:
    requester = _ApprovalRequester(ApprovalDecision.APPROVED)
    captured: dict[str, Any] = {}

    def _guarded_tool(func: Any, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
        captured.update(kwargs)
        return func, kwargs

    monkeypatch.setattr(tool_guard, "GuardedFunctionTool", _guarded_tool)
    builder = AgentBuilder(approval_requester=requester)
    wrapped = builder._wrap_tool(
        "tool-func",
        "agent-1",
        {"session_id": "session-1"},
        governor=None,
    )

    assert wrapped[0] == "tool-func"
    assert captured["approval_requester"] is requester
