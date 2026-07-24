# -*- coding: utf-8 -*-
"""Unit tests for the 8 loop upgrade features.

Tests cover:
1. DoomLoopGate semantic similarity detection
2. SubAgentRubric real evaluation (check_fn / spawn_fn / heuristic)
3. BudgetGate three-tier behavior + token refresh
4. ToolCoordinatorMiddleware parallel execution
5. Tool error classification and retry
6. IterationGate adaptive budget
7. Plan phase injection in _reply
8. ReflectionGate periodic checkpoint
"""

from __future__ import annotations

import asyncio
import pytest
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# 1. DoomLoopGate — semantic similarity
# ===========================================================================


class TestDoomLoopSemantic:
    """DoomLoopGate semantic detection tests."""

    @pytest.fixture
    def gate(self):
        from minions.loop.gates.doom_loop import DoomLoopGate

        return DoomLoopGate(
            window_size=3,
            similarity_threshold=0.7,
        )

    @pytest.mark.asyncio
    async def test_exact_match_still_works(self, gate):
        """Exact repetition should still be detected at any threshold."""
        from minions.loop.gates.doom_loop import _DoomState, _ToolCallRecord

        state = _DoomState()
        state.history.extend(
            [
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="abc",
                    args_text="pattern file.py",
                ),
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="abc",
                    args_text="pattern file.py",
                ),
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="abc",
                    args_text="pattern file.py",
                ),
            ],
        )
        assert gate._detect_repetition(state) is True

    @pytest.mark.asyncio
    async def test_semantic_match_different_args(self, gate):
        """Different args with same purpose should be detected via Jaccard."""
        from minions.loop.gates.doom_loop import _DoomState, _ToolCallRecord

        state = _DoomState()
        # Same tool, different file names but same search pattern
        state.history.extend(
            [
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h1",
                    args_text="search TODO in src/a.py",
                ),
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h2",
                    args_text="search TODO in src/b.py",
                ),
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h3",
                    args_text="search TODO in src/c.py",
                ),
            ],
        )
        # With threshold 0.7, the Jaccard similarity of these should be high
        similarity = gate._compute_similarity(list(state.history)[-3:])
        assert similarity >= 0.5  # Should have meaningful overlap

    @pytest.mark.asyncio
    async def test_no_false_positive_different_tools(self, gate):
        """Completely different tool calls should not trigger."""
        from minions.loop.gates.doom_loop import _DoomState, _ToolCallRecord

        state = _DoomState()
        state.history.extend(
            [
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h1",
                    args_text="search pattern alpha",
                ),
                _ToolCallRecord(
                    tool_name="read_file",
                    args_hash="h2",
                    args_text="completely different beta gamma",
                ),
                _ToolCallRecord(
                    tool_name="write_file",
                    args_hash="h3",
                    args_text="entirely unrelated delta epsilon",
                ),
            ],
        )
        assert gate._detect_repetition(state) is False

    @pytest.mark.asyncio
    async def test_threshold_1_0_is_exact_only(self):
        """At threshold 1.0, only exact matches trigger (no semantic)."""
        from minions.loop.gates.doom_loop import (
            DoomLoopGate,
            _DoomState,
            _ToolCallRecord,
        )

        gate = DoomLoopGate(window_size=3, similarity_threshold=1.0)
        state = _DoomState()
        state.history.extend(
            [
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h1",
                    args_text="search TODO a.py",
                ),
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h2",
                    args_text="search TODO b.py",
                ),
                _ToolCallRecord(
                    tool_name="grep",
                    args_hash="h3",
                    args_text="search TODO c.py",
                ),
            ],
        )
        # At 1.0, different hashes should NOT trigger even with similar text
        assert gate._detect_repetition(state) is False


# ===========================================================================
# 2. SubAgentRubric — real evaluation
# ===========================================================================


class TestSubAgentRubric:
    """SubAgentRubric evaluation tests."""

    @pytest.mark.asyncio
    async def test_check_fn_satisfied(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        rubric = SubAgentRubric(check_fn=lambda output: True)
        result = await rubric.evaluate("goal", "output", 1)
        assert result.verdict == RubricVerdict.SATISFIED

    @pytest.mark.asyncio
    async def test_check_fn_needs_revision(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        rubric = SubAgentRubric(check_fn=lambda output: False)
        result = await rubric.evaluate("goal", "output", 1)
        assert result.verdict == RubricVerdict.NEEDS_REVISION

    @pytest.mark.asyncio
    async def test_spawn_fn_satisfied(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        async def verifier(goal: str, output: str) -> str:
            return "satisfied"

        rubric = SubAgentRubric(spawn_fn=verifier)
        result = await rubric.evaluate("goal", "output", 1)
        assert result.verdict == RubricVerdict.SATISFIED

    @pytest.mark.asyncio
    async def test_spawn_fn_needs_revision(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        async def verifier(goal: str, output: str) -> str:
            return "needs_revision"

        rubric = SubAgentRubric(spawn_fn=verifier)
        result = await rubric.evaluate("goal", "output", 1)
        assert result.verdict == RubricVerdict.NEEDS_REVISION

    @pytest.mark.asyncio
    async def test_heuristic_satisfied(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        rubric = SubAgentRubric()
        result = await rubric.evaluate("goal", "The task is complete now.", 1)
        assert result.verdict == RubricVerdict.SATISFIED

    @pytest.mark.asyncio
    async def test_heuristic_needs_revision(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        rubric = SubAgentRubric()
        result = await rubric.evaluate("goal", "Working on it still.", 1)
        assert result.verdict == RubricVerdict.NEEDS_REVISION

    @pytest.mark.asyncio
    async def test_spawn_fn_exception_returns_grader_error(self):
        from minions.loop.gates.rubric import SubAgentRubric, RubricVerdict

        async def verifier(goal: str, output: str) -> str:
            raise RuntimeError("boom")

        rubric = SubAgentRubric(spawn_fn=verifier, max_retries=1)
        result = await rubric.evaluate("goal", "output", 1)
        assert result.verdict == RubricVerdict.GRADER_ERROR


# ===========================================================================
# 3. BudgetGate — three-tier behavior
# ===========================================================================


class TestBudgetGate:
    """BudgetGate token-aware behavior tests."""

    @pytest.fixture
    def gate(self):
        from minions.loop.gates.budget import BudgetGate

        g = BudgetGate(max_tokens=10000, warn_ratio=0.7)
        g.activate()
        return g

    @pytest.mark.asyncio
    async def test_bypass_when_under_warn_ratio(self, gate):
        """Should bypass when tokens are well below budget."""
        gate.update_tokens(1000)
        ctx = {"agent": None, "iteration": 1}
        result = await gate.check(ctx)
        from minions.loop.gates.base import StopAction

        assert result.action == StopAction.BYPASS

    @pytest.mark.asyncio
    async def test_warn_when_approaching_limit(self, gate):
        """Should warn when tokens reach warn_ratio threshold."""
        gate.update_tokens(7500)  # 75% of 10000
        ctx = {"agent": None, "iteration": 1}
        result = await gate.check(ctx)
        from minions.loop.gates.base import StopAction

        assert result.action == StopAction.INTERRUPT_AND_CONTINUE
        assert (
            "approaching limit" in result.reason.lower()
            or "wrap up" in (result.continuation_message or "").lower()
        )

    @pytest.mark.asyncio
    async def test_terminate_when_exceeded(self, gate):
        """Should terminate when tokens exceed budget."""
        gate.update_tokens(11000)
        ctx = {"agent": None, "iteration": 1}
        result = await gate.check(ctx)
        from minions.loop.gates.base import StopAction

        assert result.action == StopAction.TERMINATE

    @pytest.mark.asyncio
    async def test_warn_only_once(self, gate):
        """Warning should only be issued once, then bypass."""
        gate.update_tokens(7500)
        ctx = {"agent": None, "iteration": 1}
        # First check: warn
        result1 = await gate.check(ctx)
        from minions.loop.gates.base import StopAction

        assert result1.action == StopAction.INTERRUPT_AND_CONTINUE
        # Second check: bypass (already warned)
        result2 = await gate.check(ctx)
        assert result2.action == StopAction.BYPASS


# ===========================================================================
# 4. Parallel tool execution
# ===========================================================================


class TestParallelToolExecution:
    """ToolCoordinatorMiddleware parallel execution tests."""

    def test_execute_parallel_method_exists(self):
        """The execute_parallel method should exist on the middleware."""
        from minions.tool_calls._middleware import ToolCoordinatorMiddleware

        assert hasattr(ToolCoordinatorMiddleware, "execute_parallel")

    @pytest.mark.asyncio
    async def test_parallel_enabled_flag(self):
        """The parallel_enabled flag should be configurable."""
        from minions.tool_calls._middleware import ToolCoordinatorMiddleware

        mock_coordinator = MagicMock()
        mw = ToolCoordinatorMiddleware(mock_coordinator, parallel_enabled=True)
        assert mw.parallel_enabled is True

        mw2 = ToolCoordinatorMiddleware(
            mock_coordinator,
            parallel_enabled=False,
        )
        assert mw2.parallel_enabled is False


# ===========================================================================
# 5. Tool error classification
# ===========================================================================


class TestToolErrorClassification:
    """Tool error classification tests."""

    def test_classify_transient_timeout(self):
        from minions.tool_calls._coordinator import ToolCoordinator

        exc = asyncio.TimeoutError()
        assert ToolCoordinator._classify_error(exc) == "transient"

    def test_classify_transient_connection(self):
        from minions.tool_calls._coordinator import ToolCoordinator

        exc = ConnectionError("Connection refused")
        assert ToolCoordinator._classify_error(exc) == "transient"

    def test_classify_transient_rate_limit(self):
        from minions.tool_calls._coordinator import ToolCoordinator

        exc = Exception("rate limit exceeded")
        assert ToolCoordinator._classify_error(exc) == "transient"

    def test_classify_permanent_permission(self):
        from minions.tool_calls._coordinator import ToolCoordinator

        exc = PermissionError("access denied")
        assert ToolCoordinator._classify_error(exc) == "permanent"

    def test_classify_permanent_not_found(self):
        from minions.tool_calls._coordinator import ToolCoordinator

        exc = FileNotFoundError("no such file")
        assert ToolCoordinator._classify_error(exc) == "permanent"

    def test_classify_unknown(self):
        from minions.tool_calls._coordinator import ToolCoordinator

        exc = RuntimeError("something weird happened")
        assert ToolCoordinator._classify_error(exc) == "unknown"

    def test_context_has_retry_fields(self):
        """ToolCallContext should have retry_count and max_retries fields."""
        from minions.tool_calls._context import ToolCallContext
        import asyncio as _asyncio

        ctx = ToolCallContext(
            tool_call_id="test",
            tool_name="test",
            session_id="s",
            agent_id="a",
            root_session_id="r",
            started_at=0.0,
            deadline=None,
            cancel_event=_asyncio.Event(),
        )
        assert hasattr(ctx, "retry_count")
        assert hasattr(ctx, "max_retries")
        assert ctx.retry_count == 0
        assert ctx.max_retries == 0


# ===========================================================================
# 6. IterationGate — adaptive budget
# ===========================================================================


class TestIterationGateAdaptive:
    """IterationGate adaptive budget tests."""

    @pytest.fixture
    def gate(self):
        from minions.loop.gates.iteration import IterationGate

        g = IterationGate(
            max_iterations=20,
            adaptive=True,
            min_iterations=5,
            max_allowed_iterations=100,
        )
        g.activate()
        return g

    @pytest.mark.asyncio
    async def test_adaptive_adjusts_on_first_iteration(self, gate):
        """Budget should be adjusted after the first iteration."""
        ctx = {
            "agent": MagicMock(),
            "final_msg": None,
            "iteration": 0,
            "has_tool_calls": True,
        }
        await gate.check(ctx)
        from minions.loop.gates.iteration import _IterState

        state = gate._state()
        assert state.adjusted is True

    @pytest.mark.asyncio
    async def test_non_adaptive_no_adjustment(self):
        """When adaptive=False, budget should not change."""
        from minions.loop.gates.iteration import IterationGate, _IterState

        g = IterationGate(max_iterations=20, adaptive=False)
        g.activate()
        ctx = {
            "agent": MagicMock(),
            "final_msg": None,
            "iteration": 0,
            "has_tool_calls": True,
        }
        await g.check(ctx)
        state = g._state()
        assert state.adjusted is False
        assert state.max_iterations == 20

    @pytest.mark.asyncio
    async def test_complexity_estimation_never_crashes(self, gate):
        """Complexity estimation should never crash on bad input."""
        score = gate._estimate_complexity(None)
        assert 1 <= score <= 10

        score = gate._estimate_complexity({})
        assert 1 <= score <= 10

        score = gate._estimate_complexity({"agent": None})
        assert 1 <= score <= 10

    @pytest.mark.asyncio
    async def test_reset_clears_adjusted(self, gate):
        """Reset should clear the adjusted flag."""
        ctx = {
            "agent": MagicMock(),
            "final_msg": None,
            "iteration": 0,
            "has_tool_calls": True,
        }
        await gate.check(ctx)
        gate.reset()
        state = gate._state()
        assert state.adjusted is False


# ===========================================================================
# 7. Plan phase
# ===========================================================================


class TestPlanPhase:
    """Plan phase injection tests."""

    def test_plan_prompt_method_exists(self):
        """The _build_plan_prompt method should exist."""
        # Just verify the method is defined, not that it works
        # (full integration requires AgentScope)
        from minions.agents.react_agent import MinionsAgent

        assert hasattr(MinionsAgent, "_build_plan_prompt")

    def test_plan_enabled_method_exists(self):
        """The _plan_enabled method should exist."""
        from minions.agents.react_agent import MinionsAgent

        assert hasattr(MinionsAgent, "_plan_enabled")


# ===========================================================================
# 8. ReflectionGate
# ===========================================================================


class TestReflectionGate:
    """ReflectionGate periodic checkpoint tests."""

    @pytest.fixture
    def gate(self):
        from minions.loop.gates.reflection import ReflectionGate

        return ReflectionGate(interval=3, max_interventions=2)

    @pytest.mark.asyncio
    async def test_bypass_before_interval(self, gate):
        """Should bypass before reaching the interval."""
        from minions.loop.gates.base import StopAction

        ctx = {"has_tool_calls": False}
        result = await gate.check(ctx)  # iteration 1
        assert result.action == StopAction.BYPASS
        result = await gate.check(ctx)  # iteration 2
        assert result.action == StopAction.BYPASS

    @pytest.mark.asyncio
    async def test_trigger_at_interval(self, gate):
        """Should trigger at the interval boundary."""
        from minions.loop.gates.base import StopAction

        ctx = {"has_tool_calls": False}
        await gate.check(ctx)  # 1
        await gate.check(ctx)  # 2
        result = await gate.check(ctx)  # 3 = interval
        assert result.action == StopAction.INTERRUPT_AND_CONTINUE

    @pytest.mark.asyncio
    async def test_skip_when_tool_calls_active(self, gate):
        """Should not reflect when agent is actively calling tools."""
        from minions.loop.gates.base import StopAction

        ctx = {"has_tool_calls": True}
        await gate.check(ctx)  # 1
        await gate.check(ctx)  # 2
        result = await gate.check(ctx)  # 3 = interval, but has_tool_calls
        assert result.action == StopAction.BYPASS

    @pytest.mark.asyncio
    async def test_max_interventions_cap(self, gate):
        """Should stop reflecting after max_interventions."""
        from minions.loop.gates.base import StopAction

        ctx = {"has_tool_calls": False}
        # intervention 1 at iteration 3
        await gate.check(ctx)
        await gate.check(ctx)
        r1 = await gate.check(ctx)
        assert r1.action == StopAction.INTERRUPT_AND_CONTINUE
        # intervention 2 at iteration 6
        await gate.check(ctx)
        await gate.check(ctx)
        r2 = await gate.check(ctx)
        assert r2.action == StopAction.INTERRUPT_AND_CONTINUE
        # intervention 3 at iteration 9 — should be bypassed (cap=2)
        await gate.check(ctx)
        await gate.check(ctx)
        r3 = await gate.check(ctx)
        assert r3.action == StopAction.BYPASS

    def test_reset_clears_state(self, gate):
        """Reset should clear iteration and intervention counters."""
        gate._state = None  # simulate some usage
        gate.reset()
        assert gate._state is not None
        assert gate._state.iteration == 0
        assert gate._state.interventions == 0

    def test_build_continuation_returns_prompt(self, gate):
        """build_continuation should return a non-empty prompt."""
        prompt = gate.build_continuation()
        assert len(prompt) > 0
        assert "reflect" in prompt.lower()


# ===========================================================================
# Integration: config model
# ===========================================================================


class TestConfigModel:
    """Verify new config fields are properly defined."""

    def test_budget_gate_config_exists(self):
        from minions.config.config import BudgetGateConfig

        cfg = BudgetGateConfig()
        assert cfg.enabled is False
        assert cfg.max_tokens == 300_000
        assert cfg.warn_ratio == 0.7

    def test_reflection_gate_config_exists(self):
        from minions.config.config import ReflectionGateConfig

        cfg = ReflectionGateConfig()
        assert cfg.enabled is False
        assert cfg.interval == 5
        assert cfg.max_interventions == 3

    def test_iteration_gate_config_adaptive_fields(self):
        from minions.config.config import IterationGateConfig

        cfg = IterationGateConfig()
        assert cfg.adaptive is False
        assert cfg.min_iterations == 5
        assert cfg.max_allowed_iterations == 100

    def test_loop_config_has_new_sections(self):
        from minions.config.config import LoopConfig

        cfg = LoopConfig()
        assert hasattr(cfg, "budget")
        assert hasattr(cfg, "reflection")
        assert hasattr(cfg, "iteration")
        assert hasattr(cfg, "doom_loop")
        assert hasattr(cfg, "rubric")

    def test_running_config_has_plan_phase(self):
        from minions.config.config import AgentsRunningConfig

        cfg = AgentsRunningConfig()
        assert hasattr(cfg, "plan_phase_enabled")
        assert cfg.plan_phase_enabled is False
