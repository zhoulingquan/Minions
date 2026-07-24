# -*- coding: utf-8 -*-
"""Typed host boundary required by the ACP agent integration."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Sequence


class ACPHostServices(Protocol):
    """High-level services supplied by an app composition root."""

    async def start_workspace(
        self,
        agent_id: str,
        workspace_dir: Path,
    ) -> Any: ...

    async def stop_workspace(self, workspace: Any) -> None: ...

    async def get_pending_approvals(
        self,
        session_id: str,
    ) -> Sequence[Any]: ...

    async def resolve_approval(
        self,
        request_id: str,
        decision: Any,
        *,
        scope: Any = None,
    ) -> Any: ...

    def approval_display(self, pending: Any) -> dict[str, Any]: ...

    async def cancel_pending_approvals(self, session_id: str) -> None: ...


__all__ = ["ACPHostServices"]
