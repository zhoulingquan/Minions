# -*- coding: utf-8 -*-
"""Rubric evaluation strategies for loop completion.

Architecture:
    RubricStrategy (ABC)
    ├── DefaultRubric     — always SATISFIED (no rubric)
    ├── GoalStatusRubric  — checks session.active
    └── SubAgentRubric    — placeholder for subagent eval
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from .base import (
    StopAction,
    StopGate,
    StopHandlerResult,
)

logger = logging.getLogger(__name__)


class RubricVerdict(str, Enum):
    """Grader verdicts."""

    SATISFIED = "satisfied"
    NEEDS_REVISION = "needs_revision"
    FAILED = "failed"
    GRADER_ERROR = "grader_error"
    MAX_ITERATIONS = "max_iterations_reached"


@dataclass
class RubricEvaluation:
    """Result of one rubric evaluation pass."""

    iteration: int
    verdict: RubricVerdict
    explanation: str = ""
    feedback: str = ""


# ---- Abstract Strategy ----


class RubricStrategy(ABC):
    """Base class for rubric evaluation strategies."""

    @abstractmethod
    async def evaluate(
        self,
        goal: str,
        agent_output: str,
        iteration: int,
    ) -> RubricEvaluation:
        """Evaluate whether the goal is met."""


# ---- Concrete Strategies ----


class DefaultRubric(RubricStrategy):
    """No rubric — always SATISFIED.

    Used for loops that have no rubric requirement.
    The loop terminates normally after each turn.
    """

    async def evaluate(
        self,
        goal: str,
        agent_output: str,
        iteration: int,
    ) -> RubricEvaluation:
        return RubricEvaluation(
            iteration=iteration,
            verdict=RubricVerdict.SATISFIED,
            explanation="No rubric registered",
        )


class GoalStatusRubric(RubricStrategy):
    """Hardcoded status check for GoalMode.

    Accepts a ``get_session_fn`` callback that retrieves
    the current GoalSession via ContextVar (no scan).
    Returns SATISFIED when session.active is False
    (set by update_goal tool), NEEDS_REVISION otherwise.
    """

    def __init__(
        self,
        get_session_fn: Callable[[], Optional[Any]],
    ) -> None:
        self._get_session = get_session_fn

    async def evaluate(
        self,
        goal: str,
        agent_output: str,
        iteration: int,
    ) -> RubricEvaluation:
        session = self._get_session()
        if session is None or not session.active:
            return RubricEvaluation(
                iteration=iteration,
                verdict=RubricVerdict.SATISFIED,
                explanation=("Goal completed via update_goal"),
            )
        return RubricEvaluation(
            iteration=iteration,
            verdict=RubricVerdict.NEEDS_REVISION,
            explanation="Goal still active",
        )


class SubAgentRubric(RubricStrategy):
    """Subagent-based rubric verification (the "ralph" pattern).

    Instead of parsing the agent's free-text output to decide whether a
    goal is complete, this rubric relies on concrete state checks.
    Evaluation proceeds through three modes, tried in priority order:

    1. **check_fn** (programmatic state check): a synchronous predicate
       ``check_fn(agent_output) -> bool`` supplied by the caller.  This is
       the preferred "file-based state verification" mode -- the agent or
       its tools write structured state (e.g. key/values to a state file)
       and ``check_fn`` inspects that state directly.  Yields
       ``SATISFIED`` when truthy, ``NEEDS_REVISION`` otherwise.

    2. **spawn_fn** (LLM-based verification): an async callable
       ``spawn_fn(prompt, context_snapshot) -> str`` that spawns a
       subagent to judge completion.  The subagent must return one of the
       literal strings ``"satisfied"``, ``"needs_revision"`` or
       ``"failed"``, which are mapped to the matching
       :class:`RubricVerdict`.  Exceptions are retried up to
       ``max_retries`` times before yielding ``GRADER_ERROR`` with the
       underlying error message.

    3. **heuristic** (keyword fallback): when neither callable is
       supplied, a naive substring scan of ``agent_output`` is used.
       This is intentionally not robust and exists only so the rubric
       degrades gracefully instead of always erroring.

    The ``fork`` flag is reserved for future use (forking the agent
    context for the spawned verifier) and is currently a no-op kept for
    API compatibility.
    """

    def __init__(
        self,
        spawn_fn: Optional[Callable[[str, str], Awaitable[str]]] = None,
        fork: bool = False,
        check_fn: Optional[Callable[[Any], bool]] = None,
        max_retries: int = 1,
    ) -> None:
        self._spawn_fn = spawn_fn
        self._fork = fork
        self._check_fn = check_fn
        self._max_retries = max_retries

    async def evaluate(
        self,
        goal: str,
        agent_output: str,
        iteration: int,
    ) -> RubricEvaluation:
        """Evaluate ``goal`` against ``agent_output``.

        Dispatches to one of the three modes documented on the class
        (``check_fn`` -> ``spawn_fn`` -> heuristic) and always embeds
        ``iteration`` in the returned :class:`RubricEvaluation`.
        """
        # ---- Mode 1: programmatic state check -------------------------
        if self._check_fn is not None:
            try:
                ok = bool(self._check_fn(agent_output))
            except Exception as exc:  # noqa: BLE001 - surface grader faults
                return RubricEvaluation(
                    iteration=iteration,
                    verdict=RubricVerdict.GRADER_ERROR,
                    explanation=f"check_fn raised: {exc}",
                )
            if ok:
                return RubricEvaluation(
                    iteration=iteration,
                    verdict=RubricVerdict.SATISFIED,
                    explanation="check_fn returned True",
                )
            return RubricEvaluation(
                iteration=iteration,
                verdict=RubricVerdict.NEEDS_REVISION,
                explanation="check_fn returned False",
            )

        # ---- Mode 2: subagent (LLM) verification ----------------------
        if self._spawn_fn is not None:
            verdict_map = {
                "satisfied": RubricVerdict.SATISFIED,
                "needs_revision": RubricVerdict.NEEDS_REVISION,
                "failed": RubricVerdict.FAILED,
            }
            attempts = self._max_retries + 1
            last_exc: Optional[Exception] = None
            for attempt in range(attempts):
                try:
                    raw = await self._spawn_fn(goal, agent_output)
                except Exception as exc:  # noqa: BLE001 - transient grader faults
                    last_exc = exc
                    logger.warning(
                        "SubAgentRubric spawn_fn attempt %d/%d raised: %s",
                        attempt + 1,
                        attempts,
                        exc,
                    )
                    continue
                verdict_str = (raw or "").strip().lower()
                verdict = verdict_map.get(verdict_str)
                if verdict is None:
                    return RubricEvaluation(
                        iteration=iteration,
                        verdict=RubricVerdict.GRADER_ERROR,
                        explanation=(
                            f"spawn_fn returned unrecognized verdict: {raw!r}"
                        ),
                    )
                return RubricEvaluation(
                    iteration=iteration,
                    verdict=verdict,
                    explanation=f"spawn_fn verdict: {verdict_str}",
                )
            return RubricEvaluation(
                iteration=iteration,
                verdict=RubricVerdict.GRADER_ERROR,
                explanation=(
                    f"spawn_fn failed after {attempts} attempts: {last_exc}"
                ),
            )

        # ---- Mode 3: heuristic keyword fallback -----------------------
        completion_phrases = (
            "task complete",
            "task completed",
            "task is complete",
            "task is done",
            "all steps completed",
            "all steps done",
            "successfully completed",
            "successfully finished",
            "finished",
            "done",
            "complete",
        )
        lowered = (agent_output or "").lower()
        matched = next(
            (phrase for phrase in completion_phrases if phrase in lowered),
            None,
        )
        if matched is not None:
            return RubricEvaluation(
                iteration=iteration,
                verdict=RubricVerdict.SATISFIED,
                explanation=f"heuristic match: {matched!r}",
            )
        return RubricEvaluation(
            iteration=iteration,
            verdict=RubricVerdict.NEEDS_REVISION,
            explanation="heuristic: no completion phrase found",
        )


class StandaloneRubricGate(StopGate):
    """Re-prompt on text-only responses.

    Prevents premature stop when the LLM outputs text
    without any tool calls.  Counts interventions per
    request cycle; stops re-prompting after
    ``max_interventions``.
    """

    def __init__(
        self,
        prompt: str = "",
        max_interventions: int = 1,
    ) -> None:
        self._prompt = prompt
        self._max = max_interventions
        self._count = 0

    @property
    def name(self) -> str:
        return "standalone_rubric"

    @property
    def priority(self) -> int:
        return 90

    async def check(
        self,
        ctx: Any,
    ) -> StopHandlerResult:
        """Intervene up to max_interventions.

        Only triggers on text-only responses
        (no tool calls).
        """
        _bypass = StopHandlerResult(
            action=StopAction.BYPASS,
        )
        if isinstance(ctx, dict) and ctx.get(
            "has_tool_calls",
        ):
            return _bypass

        if self._count >= self._max:
            self._count = 0
            return _bypass

        self._count += 1
        logger.debug(
            "StandaloneRubricGate: intervene %d/%d",
            self._count,
            self._max,
        )
        return StopHandlerResult(
            action=StopAction.INTERRUPT_AND_CONTINUE,
            reason="text-only response re-prompt",
            reset_peers=True,
        )

    def build_continuation(self) -> str:
        """Return the re-prompt text."""
        return self._prompt

    def reset(self) -> None:
        """Reset intervention counter for new turn."""
        self._count = 0


__all__ = [
    "StandaloneRubricGate",
    "DefaultRubric",
    "GoalStatusRubric",
    "RubricEvaluation",
    "RubricStrategy",
    "RubricVerdict",
    "SubAgentRubric",
]
