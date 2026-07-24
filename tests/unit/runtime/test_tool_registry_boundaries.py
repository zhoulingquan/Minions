# -*- coding: utf-8 -*-
"""Ownership contracts for runtime's generic tool collection."""
from __future__ import annotations

from minions.agents import tools as agent_tools
from minions.runtime import tool_registry


def _builtin_tool() -> None:
    return None


def _external_tool() -> None:
    return None


_builtin_tool.__module__ = "minions.agents.tools.example"
_external_tool.__module__ = "example_plugin.tools"


def test_runtime_returns_all_registered_tool_functions(monkeypatch) -> None:
    monkeypatch.setattr(tool_registry, "_REGISTERED_TOOL_FUNCS", [])
    monkeypatch.setattr(tool_registry, "_REGISTERED_IDS", set())

    builtin = tool_registry.tool_descriptor()(_builtin_tool)
    external = tool_registry.tool_descriptor()(_external_tool)

    assert tool_registry.get_registered_tool_funcs() == [builtin, external]


def test_agents_own_builtin_tool_filtering(monkeypatch) -> None:
    monkeypatch.setattr(
        tool_registry,
        "get_registered_tool_funcs",
        lambda: [_builtin_tool, _external_tool],
    )
    monkeypatch.setattr(
        "minions.agents.tools.custom_loader.load_custom_tools",
        lambda: None,
    )

    assert agent_tools.discover_builtin_tool_funcs() == [_builtin_tool]
