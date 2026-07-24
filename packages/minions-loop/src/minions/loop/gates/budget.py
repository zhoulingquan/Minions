# -*- coding: utf-8 -*-
"""BudgetGate — universal token budget limiter.

Tracks per-session token usage pulled from the agent's
``TokenRecordingModelWrapper``. Provides graceful
degradation: warns (INTERRUPT_AND_CONTINUE) when usage
crosses ``max_tokens * warn_ratio`` before hard-stopping
(TERMINATE) at ``max_tokens``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from .base import StopAction, StopHandlerResult
from .loop_gate import LoopGate

logger = logging.getLogger(__name__)


@dataclass
class _BudgetState:
    """Per-session token budget state."""

    tokens_used: int = 0
    max_tokens: int = 300_000
    # Fraction of ``max_tokens`` at which to issue a warning.
    warn_ratio: float = 0.7
    # Whether the approaching-limit warning has already fired.
    warned: bool = False


class BudgetGate(LoopGate):
    """Token budget cap with graceful degradation.  Priority 20.

    Three-tier behaviour in ``check``:
      * ``tokens_used < max_tokens * warn_ratio``         -> BYPASS
      * ``warn_ratio`` reached and not yet warned          -> warn once
        (INTERRUPT_AND_CONTINUE), then BYPASS on later turns
      * ``tokens_used >= max_tokens``                      -> TERMINATE
    """

    def __init__(
        self,
        max_tokens: int = 300_000,
        warn_ratio: float = 0.7,
    ) -> None:
        super().__init__()
        self._default_max = max_tokens
        self._default_warn_ratio = warn_ratio

    @property
    def name(self) -> str:
        return "budget"

    @property
    def priority(self) -> int:
        return 20

    def activate(  # pylint: disable=arguments-renamed
        self,
        max_tokens: int | None = None,
        warn_ratio: float | None = None,
    ) -> None:
        """Activate with optional custom budget and warn ratio."""
        limit = (
            max_tokens if max_tokens is not None else self._default_max
        )
        ratio = (
            warn_ratio
            if warn_ratio is not None
            else self._default_warn_ratio
        )
        super().activate(
            _BudgetState(max_tokens=limit, warn_ratio=ratio),
        )

    def update_tokens(self, tokens: int) -> None:
        """Update token usage for current session."""
        state: Optional[_BudgetState] = self._state()
        if state is not None:
            state.tokens_used = tokens

    def refresh_tokens_from_agent(self, ctx: dict) -> None:
        """Refresh ``tokens_used`` from the agent context.

        Primary path: read the latest recorded usage from
        ``TokenRecordingModelWrapper`` for the current session.
        Fallback: estimate from the agent's conversation context
        length when the wrapper is unavailable.

        Never raises — a failure here must not crash the loop.
        """
        state: Optional[_BudgetState] = self._state()
        if state is None:
            return

        agent = ctx.get("agent") if isinstance(ctx, dict) else None

        # Primary path: real usage from the token recording wrapper.
        # Lazy import avoids a circular import with token_usage.
        try:
            if agent is not None:
                from ...token_usage.model_wrapper import (
                    TokenRecordingModelWrapper,
                )

                request_ctx = getattr(agent, "_request_context", {}) or {}
                session_id = request_ctx.get("session_id", "")
                if session_id:
                    usage = (
                        TokenRecordingModelWrapper.get_usage_for_session(
                            session_id,
                        )
                    )
                    if usage:
                        total = usage.get("total_tokens")
                        if isinstance(total, (int, float)) and total > 0:
                            self.update_tokens(int(total))
                            return
        except Exception:  # noqa: BLE001
            logger.debug(
                "BudgetGate: failed to read token usage from wrapper",
                exc_info=True,
            )

        # Fallback: estimate from the agent's context length.
        try:
            if agent is not None:
                estimated = self._estimate_context_tokens(agent)
                if estimated > 0:
                    self.update_tokens(estimated)
        except Exception:  # noqa: BLE001
            logger.debug(
                "BudgetGate: failed to estimate context tokens",
                exc_info=True,
            )

    @staticmethod
    def _estimate_context_tokens(agent: Any) -> int:
        """Estimate token usage from the agent's context length.

        Uses a rough heuristic (~4 characters per token) across
        all messages in the agent's conversation state.
        """
        agent_state = getattr(agent, "state", None)
        if agent_state is None:
            return 0
        context = getattr(agent_state, "context", None)
        if not context:
            return 0
        total_chars = 0
        for msg in context:
            content = getattr(msg, "content", None)
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        total_chars += len(text)
            elif content is not None:
                total_chars += len(str(content))
        # Rough heuristic: ~4 characters per token.
        return max(0, total_chars // 4)

    async def check(
        self,
        ctx: Any,
    ) -> StopHandlerResult:
        """Check token budget with graceful degradation.

        Tiers:
          * below ``warn_ratio``        -> BYPASS
          * at ``warn_ratio`` (unwarned) -> INTERRUPT_AND_CONTINUE once
          * at ``warn_ratio`` (warned)   -> BYPASS (already warned)
          * at/over ``max_tokens``       -> TERMINATE
        """
        # Refresh real token usage before evaluating.
        if isinstance(ctx, dict):
            self.refresh_tokens_from_agent(ctx)

        _bypass = StopHandlerResult(action=StopAction.BYPASS)
        state: Optional[_BudgetState] = self._state()
        if state is None:
            return _bypass

        max_tokens = state.max_tokens
        tokens_used = state.tokens_used

        # Hard stop: budget exhausted.
        if tokens_used >= max_tokens:
            self.deactivate()
            return StopHandlerResult(
                action=StopAction.TERMINATE,
                reason=f"Token budget exceeded ({tokens_used}/{max_tokens})",
            )

        warn_threshold = max_tokens * state.warn_ratio

        # Graceful degradation: warn once when approaching the limit.
        if tokens_used >= warn_threshold:
            if not state.warned:
                state.warned = True
                logger.warning(
                    "BudgetGate: approaching limit %d/%d",
                    tokens_used,
                    max_tokens,
                )
                return StopHandlerResult(
                    action=StopAction.INTERRUPT_AND_CONTINUE,
                    continuation_message=(
                        f"Token budget approaching limit "
                        f"({tokens_used}/{max_tokens}). "
                        f"Please wrap up the task efficiently."
                    ),
                    reason="token budget warning",
                )
            # Already warned — let the loop continue without nagging.
            return _bypass

        # Comfortably within budget.
        return _bypass

    def build_continuation(self) -> str:
        """Return the budget warning message to inject.

        Called by the StopHandler when ``check`` returns
        INTERRUPT_AND_CONTINUE. Reconstructed from the current
        state so the injected message always reflects live usage.
        """
        state: Optional[_BudgetState] = self._state()
        if state is None or not state.warned:
            return ""
        return (
            f"Token budget approaching limit "
            f"({state.tokens_used}/{state.max_tokens}). "
            f"Please wrap up the task efficiently."
        )


__all__ = ["BudgetGate"]
