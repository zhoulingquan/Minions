# -*- coding: utf-8 -*-
"""Register default StopHandler + Gates for ReAct mode.

Ensures that even without an explicit loop mode (/goal, /mission),
the agent still has Gate-based iteration control, repetition
protection, and completion checks active.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .gates import StopHandler
from .gates.budget import BudgetGate
from .gates.doom_loop import DoomLoopGate
from .gates.iteration import IterationGate
from .gates.reflection import ReflectionGate
from .gates.rubric import StandaloneRubricGate
from .handler_registry import (
    get_or_create_stop_handler,
)

if TYPE_CHECKING:
    from ..config.config import (
        AgentsRunningConfig,
    )

logger = logging.getLogger(__name__)

_REACT_HANDLER_NAME = "react-default-stop-handler"


def resolve_max_iterations(
    running_config: "AgentsRunningConfig",
) -> int:
    """Resolve effective max iterations with legacy compat.

    Priority: loop.iteration.max_iterations > max_iters
    """
    loop_cfg = running_config.loop
    if loop_cfg.iteration.max_iterations is not None:
        return loop_cfg.iteration.max_iterations
    return running_config.max_iters


def _reset_gates_for_new_turn(
    handler: StopHandler,
) -> None:
    """Reset all gates for a new user turn."""
    for gate in handler.gates:
        gate.reset()


def register_react_gates(
    workspace: Any,
    running_config: "AgentsRunningConfig",
) -> StopHandler:
    """Register default ReAct StopHandler with configured gates.

    Idempotent: skips if already registered for this workspace.
    Resets all gates on re-entry so each user turn starts
    with fresh state.

    Args:
        workspace: The workspace/agent-workspace object
            (may be None).
        running_config: Agent runtime configuration.

    Returns:
        The StopHandler instance (for testing or extension).
    """
    if getattr(
        workspace,
        "_react_gates_registered",
        False,
    ):
        handler = get_or_create_stop_handler(
            workspace,
        )
        _reset_gates_for_new_turn(handler)
        return handler

    loop_cfg = running_config.loop
    handler = get_or_create_stop_handler(
        workspace,
        scope="default",
    )

    # 1. Iteration Gate (with adaptive budget support)
    if loop_cfg.iteration.enabled:
        effective_max = resolve_max_iterations(running_config)
        adaptive = getattr(loop_cfg.iteration, 'adaptive', False)
        min_iters = getattr(loop_cfg.iteration, 'min_iterations', 5)
        max_allowed = getattr(loop_cfg.iteration, 'max_allowed_iterations', 100)
        gate = IterationGate(
            max_iterations=effective_max,
            adaptive=adaptive,
            min_iterations=min_iters,
            max_allowed_iterations=max_allowed,
        )
        gate.activate()
        handler.register(gate)
        logger.debug(
            "ReactGates: IterationGate (max=%d, adaptive=%s)",
            effective_max,
            adaptive,
        )

    # 2. Budget Gate (token cost awareness)
    budget_enabled = getattr(loop_cfg, 'budget', None)
    if budget_enabled and getattr(budget_enabled, 'enabled', False):
        max_tokens = getattr(budget_enabled, 'max_tokens', 300_000)
        warn_ratio = getattr(budget_enabled, 'warn_ratio', 0.7)
        gate = BudgetGate(
            max_tokens=max_tokens,
            warn_ratio=warn_ratio,
        )
        gate.activate()
        handler.register(gate)
        logger.debug(
            "ReactGates: BudgetGate (max_tokens=%d, warn_ratio=%.1f)",
            max_tokens,
            warn_ratio,
        )

    # 3. DoomLoop Gate
    if loop_cfg.doom_loop.enabled:
        gate = DoomLoopGate(
            window_size=loop_cfg.doom_loop.window_size,
            similarity_threshold=(loop_cfg.doom_loop.similarity_threshold),
            stages=loop_cfg.doom_loop.stages,
        )
        gate.activate()
        handler.register(gate)
        logger.debug("ReactGates: DoomLoopGate registered")

    # 4. Reflection Gate (periodic self-reflection)
    reflection_cfg = getattr(loop_cfg, 'reflection', None)
    if reflection_cfg and getattr(reflection_cfg, 'enabled', False):
        gate = ReflectionGate(
            interval=getattr(reflection_cfg, 'interval', 5),
            max_interventions=getattr(reflection_cfg, 'max_interventions', 3),
            prompt=getattr(reflection_cfg, 'prompt', ''),
        )
        handler.register(gate)
        logger.debug(
            "ReactGates: ReflectionGate (interval=%d)",
            getattr(reflection_cfg, 'interval', 5),
        )

    # 5. Rubric Gate (completion check)
    if loop_cfg.rubric.enabled:
        gate = StandaloneRubricGate(
            prompt=loop_cfg.rubric.prompt,
            max_interventions=(loop_cfg.rubric.max_interventions),
        )
        handler.register(gate)
        logger.debug(
            "ReactGates: StandaloneRubricGate registered",
        )

    setattr(
        workspace,
        "_react_gates_registered",
        True,
    )
    return handler


__all__ = [
    "register_react_gates",
    "resolve_max_iterations",
]
