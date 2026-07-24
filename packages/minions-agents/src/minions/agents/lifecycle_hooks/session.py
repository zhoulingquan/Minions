# -*- coding: utf-8 -*-
"""Agent-owned session load/save lifecycle hooks."""
from __future__ import annotations

import logging

from ...hooks.base import LifecycleHook
from ...runtime._state_utils import StateProxy
from ...runtime.hooks import HookContext, HookResult
from ...runtime.phases import Phase
from ..acp.meta import ACP_EPHEMERAL_META_KEY

logger = logging.getLogger(__name__)


def _is_ephemeral_request(ctx: HookContext) -> bool:
    request_context = getattr(ctx.request, "request_context", None)
    if not isinstance(request_context, dict):
        return False
    value = request_context.get(ACP_EPHEMERAL_META_KEY)
    if value is True:
        return True
    return isinstance(value, str) and value.lower() in {"1", "true", "yes"}


class SessionLoadHook(LifecycleHook):
    """Load persisted session state before agent construction."""

    phase = Phase.PRE_AGENT_BUILD
    name = "session_load"
    priority = 10

    async def run(self, ctx: HookContext) -> HookResult:
        if _is_ephemeral_request(ctx) or ctx.workspace is None:
            return HookResult()
        session = getattr(ctx.workspace, "session", None)
        if session is None:
            return HookResult()
        try:
            request = ctx.request
            user_id = getattr(request, "user_id", "") or ctx.session_id
            channel = getattr(request, "channel", "") or ""
            proxy = StateProxy()
            await session.load_session_state(
                session_id=ctx.session_id,
                user_id=user_id,
                channel=channel,
                agent=proxy,
            )
            if proxy.data:
                ctx.session_state = proxy.data
        except KeyError as exc:
            logger.debug("session_load: skipped (schema mismatch): %s", exc)
        except Exception:
            logger.debug("session_load: failed", exc_info=True)
        return HookResult()


class SessionSaveHook(LifecycleHook):
    """Persist agent state after response completion."""

    phase = Phase.POST_RESPONSE
    name = "session_save"
    priority = 90

    async def run(self, ctx: HookContext) -> HookResult:
        if (
            _is_ephemeral_request(ctx)
            or ctx.workspace is None
            or ctx.agent is None
        ):
            return HookResult()
        session = getattr(ctx.workspace, "session", None)
        if session is None:
            return HookResult()
        try:
            request = ctx.request
            user_id = getattr(request, "user_id", "") or ctx.session_id
            channel = getattr(request, "channel", "") or ""
            proxy = StateProxy()
            proxy.data = ctx.agent.state_dict()
            await session.save_session_state(
                session_id=ctx.session_id,
                user_id=user_id,
                channel=channel,
                agent=proxy,
            )
        except Exception:
            logger.debug("session_save: failed", exc_info=True)
        return HookResult()


__all__ = ["SessionLoadHook", "SessionSaveHook"]
