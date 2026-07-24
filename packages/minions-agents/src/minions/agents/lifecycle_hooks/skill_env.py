# -*- coding: utf-8 -*-
"""Agent-owned skill environment override lifecycle hooks."""
from __future__ import annotations

import logging
from pathlib import Path

from ...constant import WORKING_DIR
from ...hooks.base import LifecycleHook
from ...runtime.hooks import HookContext, HookResult
from ...runtime.phases import Phase
from ..skill_system import apply_skill_config_env_overrides

logger = logging.getLogger(__name__)

_SKILL_ENV_CM_KEY = "_qp_skill_env_cm"


class SkillEnvHook(LifecycleHook):
    """Push skill-declared env vars before agent execution."""

    phase = Phase.PRE_EXECUTE
    name = "skill_env_override"
    priority = 40

    async def run(self, ctx: HookContext) -> HookResult:
        wd = Path(ctx.workspace_dir or WORKING_DIR)
        channel = getattr(ctx.request, "channel", None) or "console"
        try:
            cm = apply_skill_config_env_overrides(wd, channel)
            cm.__enter__()
            ctx.extras[_SKILL_ENV_CM_KEY] = cm
        except Exception:
            logger.debug("skill_env: override failed", exc_info=True)
        return HookResult()


class SkillEnvCleanupHook(LifecycleHook):
    """Pop skill env vars in FINALLY."""

    phase = Phase.FINALLY
    name = "skill_env_cleanup"
    priority = 40

    async def run(self, ctx: HookContext) -> HookResult:
        cm = ctx.extras.pop(_SKILL_ENV_CM_KEY, None)
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                logger.debug("skill_env_cleanup: exit failed", exc_info=True)
        return HookResult()


__all__ = ["SkillEnvHook", "SkillEnvCleanupHook"]
