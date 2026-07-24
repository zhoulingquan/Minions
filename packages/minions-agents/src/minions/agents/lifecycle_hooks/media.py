# -*- coding: utf-8 -*-
"""Agent-owned file and media processing lifecycle hook."""
from __future__ import annotations

import logging

from ...hooks.base import LifecycleHook
from ...runtime.hooks import HookContext, HookResult
from ...runtime.phases import Phase

logger = logging.getLogger(__name__)


class MediaProcessHook(LifecycleHook):
    """Process file/media blocks in input messages before execution."""

    phase = Phase.PRE_EXECUTE
    name = "media_process"
    priority = 5

    async def run(self, ctx: HookContext) -> HookResult:
        if not ctx.input_msgs:
            return HookResult()
        try:
            from ..utils import process_file_and_media_blocks_in_message

            await process_file_and_media_blocks_in_message(ctx.input_msgs)
        except Exception:
            logger.warning(
                "media_process: failed; user uploads may not be visible",
                exc_info=True,
            )
        return HookResult()


__all__ = ["MediaProcessHook"]
