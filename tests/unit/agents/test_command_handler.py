# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from minions.agents.command_handler import CommandHandler


def _make_agent():
    """Build a minimal fake agent satisfying CommandHandler's expectations."""
    agent = MagicMock()
    agent.state = SimpleNamespace(context=[], session_id="session-1")
    return agent


@pytest.mark.asyncio
async def test_process_clear_returns_clear_history_metadata() -> None:
    agent = _make_agent()
    handler = CommandHandler(agent_name="Minions", agent=agent)

    msg = await handler.handle_command("/clear")

    assert msg.metadata == {"clear_history": True, "clear_plan": True}


@pytest.mark.asyncio
async def test_system_prompt_command_returns_current_prompt() -> None:
    agent = _make_agent()

    async def _get_system_prompt() -> str:
        return "current prompt"

    # pylint: disable=protected-access
    agent._get_system_prompt = _get_system_prompt
    handler = CommandHandler(agent_name="Minions", agent=agent)

    msg = await handler.handle_command("/system_prompt")

    assert handler.is_command("/system_prompt")
    assert "current prompt" in msg.get_text_content()


def _make_config(
    *,
    compact_enabled: bool = True,
    reserve_ratio: float = 0.1,
    strategy: str = "scroll",
):
    return SimpleNamespace(
        running=SimpleNamespace(
            light_context_config=SimpleNamespace(
                strategy=strategy,
                context_compact_config=SimpleNamespace(
                    enabled=compact_enabled,
                    reserve_threshold_ratio=reserve_ratio,
                ),
            ),
        ),
    )


@pytest.mark.asyncio
async def test_compact_respects_disabled_config() -> None:
    agent = _make_agent()
    agent.state = SimpleNamespace(
        context=[object()],
        summary="",
    )
    agent.compress_context = MagicMock()
    handler = CommandHandler(agent_name="Minions", agent=agent)
    # pylint: disable=protected-access
    handler._get_agent_config = lambda: _make_config(compact_enabled=False)

    msg = await handler.handle_command("/compact")

    agent.compress_context.assert_not_called()
    assert "Compact skipped" in msg.get_text_content()


class _FakeCtxConfig(SimpleNamespace):
    """Minimal stand-in for AgentScope's ContextConfig with model_copy()."""

    def model_copy(self, *, update):
        merged = {
            "trigger_ratio": self.trigger_ratio,
            "reserve_ratio": self.reserve_ratio,
            **update,
        }
        return _FakeCtxConfig(**merged)


@pytest.mark.asyncio
async def test_compact_uses_manual_force_context_config() -> None:
    """Under scroll, manual /compact clones the live agent's context_config,
    dropping the auto trigger but leaving the reserve tail untouched so it
    matches the same recent-tail budget as auto compaction."""
    from minions.agents.command_handler import _FORCE_TRIGGER_RATIO

    captured = {}

    async def _compress_context(context_config=None):
        captured["context_config"] = context_config
        agent.state.summary = "summary"

    agent = _make_agent()
    agent.state = SimpleNamespace(
        context=[object()],
        summary="",
    )
    agent.context_config = _FakeCtxConfig(trigger_ratio=0.8, reserve_ratio=0.2)
    agent.compress_context = _compress_context
    handler = CommandHandler(agent_name="Minions", agent=agent)
    # pylint: disable=protected-access
    handler._get_agent_config = lambda: _make_config(
        reserve_ratio=0.2,
        strategy="scroll",
    )

    msg = await handler.handle_command("/compact")

    context_config = captured["context_config"]
    assert context_config.trigger_ratio == _FORCE_TRIGGER_RATIO
    # The reserve tail is kept at the agent's configured value, not shrunk.
    assert context_config.reserve_ratio == 0.2
    # The live agent's own config is left untouched (model_copy, not mutated).
    assert agent.context_config.reserve_ratio == 0.2
    assert "Compact Complete" in msg.get_text_content()


@pytest.mark.asyncio
async def test_compact_under_native_keeps_configured_reserve() -> None:
    """Under native, manual /compact forces the trigger but must NOT shrink the
    reserve: native compaction is lossy (the non-reserved middle is summarized
    away), so it keeps the agent's configured reserve_ratio for the same
    recent-tail continuity as auto compaction."""
    from minions.agents.command_handler import _FORCE_TRIGGER_RATIO

    captured = {}

    async def _compress_context(context_config=None):
        captured["context_config"] = context_config
        agent.state.summary = "summary"

    agent = _make_agent()
    agent.state = SimpleNamespace(
        context=[object()],
        summary="",
    )
    agent.context_config = _FakeCtxConfig(trigger_ratio=0.8, reserve_ratio=0.2)
    agent.compress_context = _compress_context
    handler = CommandHandler(agent_name="Minions", agent=agent)
    # pylint: disable=protected-access
    handler._get_agent_config = lambda: _make_config(
        reserve_ratio=0.2,
        strategy="native",
    )

    await handler.handle_command("/compact")

    context_config = captured["context_config"]
    # Trigger is still forced so the manual command always runs...
    assert context_config.trigger_ratio == _FORCE_TRIGGER_RATIO
    # ...but the reserve is left at the agent's configured value (the base),
    # NOT shrunk to the scroll-only _FORCE_RESERVE_RATIO.
    assert context_config.reserve_ratio == 0.2
