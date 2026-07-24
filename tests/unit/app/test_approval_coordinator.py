# -*- coding: utf-8 -*-
"""Tests for the app-owned runtime approval adapter."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from minions.app.app_services.approval_coordinator import ApprovalCoordinator
from minions.security.tool_guard.approval import ApprovalDecision, ApprovalScope


class _ApprovalService:
    def __init__(self) -> None:
        self.cancelled: list[tuple[str, str]] = []
        self.created: list[dict[str, Any]] = []
        self.waited: list[tuple[str, float]] = []

    async def cancel_stale_pending_for_tool_call(
        self,
        session_id: str,
        tool_call_id: str,
    ) -> None:
        self.cancelled.append((session_id, tool_call_id))

    async def create_pending(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        return SimpleNamespace(
            request_id="request-1",
            scope=ApprovalScope.SIMILAR,
        )

    async def wait_for_approval(
        self,
        request_id: str,
        timeout_seconds: float,
    ) -> ApprovalDecision:
        self.waited.append((request_id, timeout_seconds))
        return ApprovalDecision.APPROVED


@pytest.mark.asyncio
async def test_coordinator_adapts_tool_guard_request_to_service() -> None:
    service = _ApprovalService()
    coordinator = ApprovalCoordinator(service=service)
    guard_result = object()

    response = await coordinator.request_approval(
        agent_id="agent-1",
        tool_name="dangerous_tool",
        input_data={"path": "important.txt"},
        guard_result=guard_result,
        request_context={
            "session_id": "session-1",
            "root_session_id": "root-session",
            "root_agent_id": "root-agent",
            "user_id": "user-1",
            "channel": "console",
            "tool_call_id": "call-1",
        },
        timeout_seconds=12.5,
        extra={"display": {"similar_target": "important.*"}},
    )

    assert response.decision == ApprovalDecision.APPROVED
    assert response.scope == ApprovalScope.SIMILAR
    assert service.cancelled == [("session-1", "call-1")]
    assert service.created == [
        {
            "session_id": "session-1",
            "root_session_id": "root-session",
            "owner_agent_id": "root-agent",
            "user_id": "user-1",
            "channel": "console",
            "agent_id": "agent-1",
            "tool_name": "dangerous_tool",
            "result": guard_result,
            "timeout_seconds": 12.5,
            "extra": {
                "tool_call": {
                    "id": "call-1",
                    "name": "dangerous_tool",
                    "input": {"path": "important.txt"},
                },
                "channel_meta": None,
                "_channel_instance": None,
                "display": {"similar_target": "important.*"},
            },
        },
    ]
    assert service.waited == [("request-1", 12.5)]
