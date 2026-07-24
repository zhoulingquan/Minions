# -*- coding: utf-8 -*-
"""Bootstrap guidance lifecycle hook."""
from __future__ import annotations

import logging
from pathlib import Path

from ...hooks.base import LifecycleHook
from ...runtime.hooks import HookContext, HookResult
from ...runtime.phases import Phase

logger = logging.getLogger(__name__)


class BootstrapHook(LifecycleHook):
    """Inject BOOTSTRAP.md guidance into the first user message."""

    phase = Phase.PRE_EXECUTE
    name = "bootstrap"
    priority = 20

    async def run(self, ctx: HookContext) -> HookResult:
        if ctx.extras.get("is_cron"):
            return HookResult()

        wd = ctx.workspace_dir
        if not wd:
            return HookResult()

        bootstrap_path = Path(wd) / "BOOTSTRAP.md"
        bootstrap_completed_flag = Path(wd) / ".bootstrap_completed"
        if bootstrap_completed_flag.exists() or not bootstrap_path.exists():
            return HookResult()
        if not ctx.input_msgs:
            return HookResult()

        try:
            from ..prompt import build_bootstrap_guidance
            from ..utils import prepend_to_message_content

            language = "zh"
            if ctx.agent_config is not None:
                language = getattr(ctx.agent_config, "language", "zh") or "zh"
            bootstrap_guidance = build_bootstrap_guidance(language)
            for msg in ctx.input_msgs:
                if msg.role == "user":
                    prepend_to_message_content(msg, bootstrap_guidance)
                    break
            bootstrap_completed_flag.touch()
            logger.debug("Bootstrap guidance injected into input_msgs")
        except Exception:
            logger.debug("bootstrap: injection failed", exc_info=True)
        return HookResult()


__all__ = ["BootstrapHook"]
