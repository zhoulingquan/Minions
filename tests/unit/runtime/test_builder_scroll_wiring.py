# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from minions.agents.runtime_builder import AgentBuilder


def _config(strategy: str):
    return SimpleNamespace(
        running=SimpleNamespace(
            light_context_config=SimpleNamespace(
                strategy=strategy,
                scroll_config=SimpleNamespace(allow_unsandboxed=False),
            ),
        ),
    )


def test_scroll_runtime_wires_manager_middleware_and_recall_tools(
    monkeypatch,
) -> None:
    builder = AgentBuilder()
    components = SimpleNamespace(
        context_manager=object(),
        cap_middleware=object(),
        recall_tool=object(),
        repl_tool=object(),
    )
    monkeypatch.setattr(builder, "_scroll_recall_runnable", lambda *_: True)
    monkeypatch.setattr(
        builder,
        "_build_scroll_components",
        lambda *_: components,
    )
    calls = []
    monkeypatch.setattr(
        builder,
        "_append_scroll_recall_tools",
        lambda tools, scroll, *_: calls.append((tools, scroll)),
    )
    tools = []

    result = builder._prepare_scroll_runtime(
        ctx=SimpleNamespace(),
        agent_config=_config("scroll"),
        model=object(),
        offloader=None,
        governor=object(),
        extra_tools=tools,
        agent_id="agent-1",
        request_context={"channel": "console"},
    )

    assert result is components
    assert calls == [(tools, components)]


def test_scroll_runtime_degrades_to_native_when_recall_is_unavailable(
    monkeypatch,
) -> None:
    builder = AgentBuilder()
    monkeypatch.setattr(builder, "_scroll_recall_runnable", lambda *_: False)
    monkeypatch.setattr(
        builder,
        "_build_scroll_components",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not build")),
    )

    result = builder._prepare_scroll_runtime(
        ctx=SimpleNamespace(),
        agent_config=_config("scroll"),
        model=object(),
        offloader=None,
        governor=None,
        extra_tools=[],
        agent_id="agent-1",
        request_context={},
    )

    assert result is None


def test_native_strategy_never_constructs_scroll(monkeypatch) -> None:
    builder = AgentBuilder()
    monkeypatch.setattr(
        builder,
        "_scroll_recall_runnable",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not check")),
    )

    assert (
        builder._prepare_scroll_runtime(
            ctx=SimpleNamespace(),
            agent_config=_config("native"),
            model=object(),
            offloader=None,
            governor=None,
            extra_tools=[],
            agent_id="agent-1",
            request_context={},
        )
        is None
    )
