# -*- coding: utf-8 -*-
"""IterationGate — universal iteration limiter.

Tracks per-session iteration count.  Returns TERMINATE when
``max_iterations`` is reached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from .base import StopAction, StopHandlerResult
from .loop_gate import LoopGate

logger = logging.getLogger(__name__)


@dataclass
class _IterState:
    """Per-session iteration state."""

    iteration: int = 0
    max_iterations: int = 20
    adaptive: bool = False
    min_iterations: int = 5
    max_allowed: int = 100
    adjusted: bool = False


class IterationGate(LoopGate):
    """Hard iteration cap.  Priority 10 (runs early)."""

    def __init__(
        self,
        max_iterations: int = 20,
        adaptive: bool = False,
        min_iterations: int = 5,
        max_allowed_iterations: int = 100,
    ) -> None:
        super().__init__()
        self._default_max = max_iterations
        self._default_adaptive = adaptive
        self._default_min_iterations = min_iterations
        self._default_max_allowed = max_allowed_iterations

    @property
    def name(self) -> str:
        return "iteration"

    @property
    def priority(self) -> int:
        return 10

    def activate(  # pylint: disable=arguments-renamed
        self,
        max_iterations: int | None = None,
        adaptive: bool | None = None,
        min_iterations: int | None = None,
        max_allowed_iterations: int | None = None,
    ) -> None:
        """Activate with optional custom limit."""
        limit = max_iterations or self._default_max
        use_adaptive = self._default_adaptive if adaptive is None else adaptive
        use_min = self._default_min_iterations if min_iterations is None else min_iterations
        use_max_allowed = (
            self._default_max_allowed
            if max_allowed_iterations is None
            else max_allowed_iterations
        )
        super().activate(
            _IterState(
                max_iterations=limit,
                adaptive=use_adaptive,
                min_iterations=use_min,
                max_allowed=use_max_allowed,
            ),
        )

    async def check(
        self,
        ctx: Any,  # pylint: disable=unused-argument
    ) -> StopHandlerResult:
        """Check iteration limit."""
        state: Optional[_IterState] = self._state()
        if state is None:
            return StopHandlerResult(
                action=StopAction.BYPASS,
            )

        state.iteration += 1

        # Adaptive budget adjustment: once, right after the first iteration,
        # re-estimate max_iterations based on observed task complexity.
        if (
            state.adaptive
            and not state.adjusted
            and state.iteration == 1
        ):
            complexity = self._estimate_complexity(ctx)
            base = state.max_iterations
            new_max = int(base * (0.5 + complexity / 10.0))
            # Clamp to [min_iterations, max_allowed].
            new_max = max(state.min_iterations, min(new_max, state.max_allowed))
            old_max = state.max_iterations
            state.max_iterations = new_max
            state.adjusted = True
            logger.info(
                "IterationGate: adaptive budget adjusted %d -> %d "
                "(complexity=%d)",
                old_max,
                new_max,
                complexity,
            )

        logger.debug(
            "IterationGate: %d/%d",
            state.iteration,
            state.max_iterations,
        )

        if state.iteration >= state.max_iterations:
            self.deactivate()
            return StopHandlerResult(
                action=StopAction.TERMINATE,
                reason=(f"Max iterations ({state.max_iterations}) reached"),
            )
        return StopHandlerResult(
            action=StopAction.BYPASS,
        )

    def _estimate_complexity(self, ctx: Any) -> int:
        """Estimate task complexity on a 1-10 scale.

        Inspects the last user message and tool-call signals to produce a
        heuristic complexity score.  Returns the highest score from any
        matching signal.  Defaults to 5 when nothing matches.

        This method must never raise — every failure path falls back to 5.
        """
        try:
            scores: list[int] = []

            # Extract the agent from the context dict, if available.
            agent = None
            if isinstance(ctx, dict):
                agent = ctx.get("agent")

            # Retrieve the last user message text from agent.state.context.
            text = ""
            if agent is not None:
                context = getattr(getattr(agent, "state", None), "context", None)
                if context:
                    # Walk the context backwards to find the last user message.
                    for msg in reversed(context):
                        role = None
                        content = None
                        if isinstance(msg, dict):
                            role = msg.get("role")
                            content = msg.get("content")
                        else:
                            role = getattr(msg, "role", None)
                            content = getattr(msg, "content", None)
                        if role == "user":
                            if isinstance(content, list):
                                # Multi-part content — join text parts together.
                                parts = []
                                for part in content:
                                    if isinstance(part, dict):
                                        parts.append(str(part.get("text", "")))
                                    else:
                                        parts.append(str(part))
                                text = "".join(parts)
                            else:
                                text = str(content or "")
                            break

            text_lower = text.lower()

            # Signal: long message → complexity 3
            if len(text) > 500:
                scores.append(3)

            # Signal: heavy-weight verbs → complexity 4
            heavy_words = (
                "refactor",
                "architecture",
                "design",
                "migrate",
                "implement from scratch",
            )
            if any(w in text_lower for w in heavy_words):
                scores.append(4)

            # Signal: light-weight verbs → complexity 1
            light_words = ("fix", "update", "rename", "move")
            if any(w in text_lower for w in light_words):
                scores.append(1)

            # Signal: mentions tests → complexity 1
            if "test" in text_lower:
                scores.append(1)

            # Signal: multiple tool calls in first iteration → complexity 2
            if isinstance(ctx, dict) and ctx.get("has_tool_calls"):
                scores.append(2)

            # Default to 5 when nothing matches.
            if not scores:
                return 5

            # Return the max matching score, clamped to 1-10.
            score = max(scores)
            return max(1, min(score, 10))
        except Exception:  # pylint: disable=broad-except
            return 5

    def reset(self) -> None:
        """Reset iteration counter for current session."""
        state = self._state()
        if state is not None:
            state.iteration = 0
            state.adjusted = False


__all__ = ["IterationGate"]
