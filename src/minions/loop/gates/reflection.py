# -*- coding: utf-8 -*-
"""ReflectionGate — periodic self-reflection checkpoint.

Every ``interval`` iterations, injects a reflection prompt
asking the agent to evaluate its progress toward the goal.
Unlike RubricGate (completion check), this gate triggers
mid-loop reflection to catch going-off-track early.

Priority: 50 (between DoomLoopGate=5 and RubricGate=90).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from .base import StopAction, StopHandlerResult, StopGate

logger = logging.getLogger(__name__)


@dataclass
class _ReflectionState:
    """Per-turn reflection state."""
    iteration: int = 0
    interventions: int = 0


class ReflectionGate(StopGate):
    """Periodic self-reflection checkpoint.

    Every ``interval`` iterations, when the agent produces
    a text-only response (no tool calls), the gate injects
    a reflection prompt instead of allowing the loop to stop.

    The reflection prompt asks the agent to:
    1. Summarize what has been accomplished so far
    2. Assess whether the current approach is working
    3. Identify any blockers or wrong directions
    4. Decide whether to continue or change strategy

    This catches "silent drift" — agents that keep calling
    tools but make no real progress toward the goal.
    """

    DEFAULT_PROMPT = (
        "Before continuing, take a moment to reflect:\n"
        "1. What have you accomplished so far?\n"
        "2. Is your current approach working?\n"
        "3. Are there any blockers or wrong directions?\n"
        "4. Should you continue or change strategy?\n"
        "Provide a brief assessment, then continue working."
    )

    def __init__(
        self,
        *,
        interval: int = 5,
        max_interventions: int = 3,
        prompt: str = "",
    ) -> None:
        self._interval = max(1, interval)
        self._max_interventions = max(1, max_interventions)
        self._prompt = prompt or self.DEFAULT_PROMPT
        self._state: Optional[_ReflectionState] = None

    @property
    def name(self) -> str:
        return "reflection"

    @property
    def priority(self) -> int:
        return 50

    async def check(self, ctx: Any) -> Optional[StopHandlerResult]:
        """Trigger reflection every ``interval`` iterations."""
        _bypass = StopHandlerResult(action=StopAction.BYPASS)

        if self._state is None:
            self._state = _ReflectionState()

        self._state.iteration += 1

        # Only reflect at interval boundaries
        if self._state.iteration % self._interval != 0:
            return _bypass

        # Don't reflect more than max_interventions times
        if self._state.interventions >= self._max_interventions:
            return _bypass

        # Only reflect on text-only responses (when agent considers stopping)
        # or when we detect no tool calls in recent iterations
        if isinstance(ctx, dict):
            has_tool_calls = ctx.get("has_tool_calls", False)
            if has_tool_calls:
                # Agent is actively working — let it continue without reflection
                return _bypass

        self._state.interventions += 1
        logger.info(
            "ReflectionGate: triggering reflection at iteration %d (%d/%d interventions)",
            self._state.iteration,
            self._state.interventions,
            self._max_interventions,
        )

        return StopHandlerResult(
            action=StopAction.INTERRUPT_AND_CONTINUE,
            reason="periodic self-reflection checkpoint",
        )

    def build_continuation(self) -> str:
        """Return the reflection prompt."""
        return self._prompt

    def reset(self) -> None:
        """Reset state for a new user turn."""
        self._state = _ReflectionState()


__all__ = ["ReflectionGate"]
