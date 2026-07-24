# -*- coding: utf-8 -*-
"""Minimal structural interfaces shared across Minions distributions."""
from __future__ import annotations

from typing import Any, Protocol


class AgentBuilderProtocol(Protocol):
    """Build an agent-compatible object for a runtime context."""

    async def build(self, ctx: Any) -> Any: ...


class ApprovalRequester(Protocol):
    """Request approval without coupling core to an app implementation."""

    async def request_approval(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...


class WorkspaceProtocol(Protocol):
    """Small workspace surface consumed by cross-distribution code."""

    agent_id: str
    workspace_dir: Any


class ChannelProtocol(Protocol):
    """Small channel surface used by composition and delivery code."""

    async def send_message(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> Any: ...
