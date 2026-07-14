# -*- coding: utf-8 -*-
"""DoomLoopGate: session-safe doom loop detection.

Inherits LoopGate for per-session state isolation.
Includes inline sliding-window similarity detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .base import (
    StopAction,
    StopHandlerResult,
)
from .loop_gate import LoopGate

logger = logging.getLogger(__name__)


@dataclass
class _ToolCallRecord:
    """One recorded tool call for pattern analysis.

    ``args_hash`` drives the fast exact-match path, while
    ``args_text`` (a truncated string view of the call args)
    feeds the semantic Jaccard fallback for detecting
    "same purpose, different parameters" patterns.
    """

    tool_name: str
    args_hash: str
    # Defaults to "" so the plain record() helper (which only
    # receives a hash) keeps working; empty text simply yields a
    # 0.0 Jaccard score and never triggers semantic false positives.
    args_text: str = ""


@dataclass
class _DoomState:
    """Per-session doom loop state."""

    history: deque = field(default_factory=deque)
    consecutive_hits: int = 0
    prompt: str = ""
    last_recorded_iter: int = -1


class DoomLoopGate(LoopGate):
    """Multi-stage doom loop gate (session-safe).

    Sliding-window repetition detection that escalates
    through configured stages.

    - action="modify_prompt": INTERRUPT_AND_CONTINUE,
      inject warning via build_continuation().
    - action="stop": return TERMINATE immediately.
    """

    @property
    def name(self) -> str:
        return "doom-loop"

    @property
    def priority(self) -> int:
        return 5

    def __init__(
        self,
        *,
        window_size: int = 3,
        similarity_threshold: float = 1.0,
        stages: list | None = None,
    ) -> None:
        super().__init__()
        self._window_size = max(2, window_size)
        self._threshold = similarity_threshold
        self._stages = sorted(
            stages or [],
            key=lambda s: s.after,
        )

    def _ensure_state(self) -> _DoomState:
        """Get or create per-session state."""
        state = self._state()
        if state is None:
            state = _DoomState(
                history=deque(
                    maxlen=self._window_size * 2,
                ),
            )
            self.activate(state)
        return state

    def record(
        self,
        tool_name: str,
        args_hash: str,
    ) -> None:
        """Record a completed tool call."""
        state = self._ensure_state()
        state.history.append(
            _ToolCallRecord(
                tool_name=tool_name,
                args_hash=args_hash,
            ),
        )

    def reset(self) -> None:
        """Clear history and counters for current session."""
        state = self._state()
        if state is not None:
            state.history.clear()
            state.consecutive_hits = 0
            state.prompt = ""
            state.last_recorded_iter = -1

    async def check(
        self,
        ctx: Any,
    ) -> StopHandlerResult:
        """Evaluate doom loop state.

        Auto-records tool calls from agent context when
        available (no explicit record() needed).
        """
        _bypass = StopHandlerResult(
            action=StopAction.BYPASS,
        )
        state = self._ensure_state()
        self._auto_record_from_ctx(ctx, state)

        is_looping = self._detect_repetition(state)

        if not is_looping:
            state.consecutive_hits = 0
            state.prompt = ""
            return _bypass

        if state.consecutive_hits == 0:
            state.consecutive_hits = self._window_size
        else:
            state.consecutive_hits += 1

        active_stage = None
        for stage in reversed(self._stages):
            if state.consecutive_hits >= stage.after:
                active_stage = stage
                break

        if active_stage is None:
            return _bypass

        if active_stage.action == "stop":
            logger.info(
                "DoomLoopGate: STOP after %d hits",
                state.consecutive_hits,
            )
            return StopHandlerResult(
                action=StopAction.TERMINATE,
                reason=active_stage.prompt,
            )

        state.prompt = active_stage.prompt
        logger.warning(
            "DoomLoopGate: warning at %d hits",
            state.consecutive_hits,
        )
        return StopHandlerResult(
            action=StopAction.INTERRUPT_AND_CONTINUE,
            reason="doom_loop repetition warning",
        )

    def build_continuation(self) -> str:
        """Return current doom loop warning."""
        state = self._state()
        if state is None:
            return ""
        return state.prompt

    def _auto_record_from_ctx(
        self,
        ctx: Any,
        state: _DoomState,
    ) -> None:
        """Extract latest tool call from agent context."""
        if not isinstance(ctx, dict):
            return
        agent = ctx.get("agent")
        if agent is None:
            return
        cur_iter = ctx.get("iteration", 0)
        if cur_iter <= state.last_recorded_iter:
            return
        state.last_recorded_iter = cur_iter

        context = getattr(
            getattr(agent, "state", None),
            "context",
            [],
        )
        if not context:
            return
        last_msg = context[-1]
        content = getattr(last_msg, "content", None)
        if not content or not isinstance(content, list):
            return
        for block in reversed(content):
            btype = getattr(block, "type", None)
            if isinstance(block, dict):
                btype = block.get("type")
            if btype in ("tool_call", "tool_use"):
                name = (
                    block.get("name", "")
                    if isinstance(block, dict)
                    else getattr(block, "name", "")
                )
                raw_input = (
                    block.get("input", "")
                    if isinstance(block, dict)
                    else getattr(block, "input", "")
                )
                args_hash, args_text = self._extract_args_info(raw_input)
                state.history.append(
                    _ToolCallRecord(
                        tool_name=name,
                        args_hash=args_hash,
                        args_text=args_text,
                    ),
                )
                return

    @staticmethod
    def _extract_args_info(raw_input: Any) -> tuple[str, str]:
        """Extract a hash and a truncated text view of tool call args.

        Returns ``(args_hash, args_text)``:
        - ``args_hash``: short md5 prefix used by the exact-match
          fast path. Only the first 2048 bytes are hashed — enough
          for repetition detection without serializing potentially
          large file contents.
        - ``args_text``: truncated string representation (max 512
          chars) of the same input, used as the token source for
          the semantic Jaccard fallback.
        """
        _MAX_HASH_INPUT = 2048
        _MAX_TEXT = 512
        if isinstance(raw_input, str):
            text = raw_input
        else:
            text = json.dumps(
                raw_input,
                sort_keys=True,
                default=str,
            )
        data = text[:_MAX_HASH_INPUT].encode()
        args_hash = hashlib.md5(data).hexdigest()[:8]
        args_text = text[:_MAX_TEXT]
        return args_hash, args_text

    def _detect_repetition(
        self,
        state: _DoomState,
    ) -> bool:
        """Check sliding window for repetition.

        Delegates to the dual-mode ``_compute_similarity`` (exact
        signature fast path, with a semantic Jaccard fallback when
        the threshold has been lowered). A single threshold applies
        to both modes.
        """
        if len(state.history) < self._window_size:
            return False

        window = list(state.history)[-self._window_size :]
        similarity = self._compute_similarity(window)

        if similarity >= self._threshold:
            logger.warning(
                "Doom loop: sim=%.2f thr=%.2f",
                similarity,
                self._threshold,
            )
            return True
        return False

    def _compute_similarity(
        self,
        window: list[_ToolCallRecord],
    ) -> float:
        """Compute action pattern similarity (dual-mode).

        Mode 1 — exact match (fast path): uses the formula
        ``1 - (unique - 1) / (total - 1)`` over the
        ``tool_name:args_hash`` signatures. When this already meets
        the configured threshold it is returned directly and the
        costlier semantic step is skipped.

        Mode 2 — semantic fuzzy match: activated only when the exact
        similarity falls below the threshold AND the threshold has
        been lowered below the strict-exact default (1.0). Computes a
        token-based Jaccard similarity between the ``args_text`` of
        consecutive records in the window and returns the average.
        This lets the gate flag "same purpose, different parameters"
        patterns that exact hashing misses.

        At the default threshold of 1.0 the gate stays in
        exact-match-only mode, preserving prior behaviour.

        Precondition: ``len(window) >= 2``.
        Callers must ensure this; ``_detect_repetition``
        guards via ``len(history) < window_size``
        where ``window_size >= 2``.
        """
        if not window or len(window) <= 1:
            return 0.0

        # --- Mode 1: exact signature similarity (fast path) ---
        sigs = [f"{r.tool_name}:{r.args_hash}" for r in window]
        unique = len(set(sigs))
        total = len(sigs)
        exact_similarity = 1.0 - (unique - 1) / (total - 1)

        # Fast path: exact match already meets the threshold, so the
        # more expensive semantic analysis is unnecessary.
        if exact_similarity >= self._threshold:
            return exact_similarity

        # Semantic matching only activates when the user has lowered
        # the threshold below the strict-exact default. At 1.0 the
        # gate remains exact-match-only.
        if self._threshold >= 1.0:
            return exact_similarity

        # --- Mode 2: semantic fuzzy similarity (Jaccard) ---
        jaccard_scores: list[float] = []
        for i in range(1, len(window)):
            prev_tokens = set(window[i - 1].args_text.split())
            cur_tokens = set(window[i].args_text.split())
            jaccard_scores.append(
                self._jaccard(prev_tokens, cur_tokens),
            )

        if not jaccard_scores:
            return exact_similarity

        return sum(jaccard_scores) / len(jaccard_scores)

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        """Token-set Jaccard similarity.

        Returns ``0.0`` when either token set is empty, so records
        without ``args_text`` (e.g. created via the plain
        ``record()`` helper) never produce semantic false positives.
        """
        if not a or not b:
            return 0.0
        union = len(a | b)
        if union == 0:
            return 0.0
        return len(a & b) / union


__all__ = ["DoomLoopGate"]
