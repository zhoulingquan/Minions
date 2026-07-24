# -*- coding: utf-8 -*-
"""Façade over the existing ``ApprovalService`` singleton.

A thin pass-through that lets callers use
``ctx.app_services.approval_coordinator`` *without* changing behavior.
The wrapper is the future seam where cross-workspace approval
orchestration will land.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..approvals.service import ApprovalService


class ApprovalCoordinator:
    """Wrap one ``ApprovalService`` instance and forward all attribute access.

    The default constructor binds to the process-wide singleton so the
    transitional period keeps behaving like today. Tests (and the future
    lifespan-managed instance) inject their own service explicitly.
    """

    def __init__(self, service: "ApprovalService | None" = None) -> None:
        if service is None:
            from ..approvals.service import get_approval_service

            service = get_approval_service()
        self._svc = service

    @property
    def service(self) -> "ApprovalService":
        """Expose the underlying service.

        Escape hatch for code that needs the concrete type.
        """
        return self._svc

    def __getattr__(self, name: str) -> Any:
        """Forward every undefined attribute to the wrapped service."""
        return getattr(self._svc, name)

    async def request_approval(
        self,
        *,
        agent_id: str,
        tool_name: str,
        input_data: dict[str, Any],
        guard_result: Any,
        request_context: dict[str, Any] | None = None,
        timeout_seconds: float,
        extra: dict[str, Any] | None = None,
    ) -> Any:
        """Adapt a generic runtime approval request to ``ApprovalService``."""
        ctx = request_context or {}
        session_id = str(ctx.get("session_id") or "")
        tool_call_id = str(ctx.get("tool_call_id") or "")
        if session_id and tool_call_id:
            await self._svc.cancel_stale_pending_for_tool_call(
                session_id,
                tool_call_id,
            )

        pending_extra = dict(extra or {})
        pending_extra.update(
            {
                "tool_call": {
                    "id": tool_call_id,
                    "name": tool_name,
                    "input": dict(input_data or {}),
                },
                "channel_meta": ctx.get("channel_meta"),
                "_channel_instance": ctx.get("_channel_instance"),
            },
        )
        pending = await self._svc.create_pending(
            session_id=session_id,
            root_session_id=str(ctx.get("root_session_id") or session_id),
            owner_agent_id=str(ctx.get("root_agent_id") or agent_id or "unknown"),
            user_id=str(ctx.get("user_id") or ""),
            channel=str(ctx.get("channel") or ""),
            agent_id=agent_id or "unknown",
            tool_name=tool_name,
            result=guard_result,
            timeout_seconds=timeout_seconds,
            extra=pending_extra,
        )
        decision = await self._svc.wait_for_approval(
            pending.request_id,
            timeout_seconds,
        )
        from ...security.tool_guard.approval import ApprovalResponse

        return ApprovalResponse(
            decision=decision,
            scope=getattr(pending, "scope", None),
        )


__all__ = ["ApprovalCoordinator"]
