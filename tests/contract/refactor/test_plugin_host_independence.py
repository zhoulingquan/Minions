# -*- coding: utf-8 -*-
"""Contracts for plugin isolation and typed host integration."""
from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGINS_ROOT = (
    REPO_ROOT
    / "packages"
    / "minions-plugins"
    / "src"
    / "minions"
    / "plugins"
)


@pytest.fixture(autouse=True)
def reset_plugin_host():
    try:
        host_module = importlib.import_module("minions.plugins.host")
    except ModuleNotFoundError:
        yield
        return
    host_module.configure_plugin_host(None)
    yield
    host_module.configure_plugin_host(None)


class _Host:
    def __init__(self) -> None:
        self.tools: list[dict[str, Any]] = []
        self.removed_tools: list[tuple[str, tuple[str, ...]]] = []
        self.prompt_anchors: list[str] = []
        self.channels: list[tuple[str, type]] = []

    def register_tool(self, **kwargs: Any) -> None:
        self.tools.append(kwargs)

    def unregister_tools(self, plugin_id: str, tool_names: list[str]) -> None:
        self.removed_tools.append((plugin_id, tuple(tool_names)))

    def create_stop_handler_registration(self, **kwargs: Any) -> Any:
        return SimpleNamespace(**kwargs)

    def validate_prompt_anchor(self, anchor: str) -> None:
        self.prompt_anchors.append(anchor)

    def validate_channel(self, channel_key: str, channel_class: type) -> None:
        self.channels.append((channel_key, channel_class))

    def install_plugin_skills(self, **_kwargs: Any) -> None:
        return None

    def install_plugin_skills_into_workspace(self, **_kwargs: Any) -> None:
        return None

    def uninstall_plugin_skills(self, **_kwargs: Any) -> None:
        return None


def test_plugin_host_is_required_explicitly() -> None:
    host_module = importlib.import_module("minions.plugins.host")

    assert hasattr(host_module, "PluginHost")
    with pytest.raises(RuntimeError, match="plugin host.*not configured"):
        host_module.require_plugin_host()


def test_plugin_tree_has_no_high_level_dependencies_or_module_locators() -> None:
    offenders: list[str] = []
    forbidden = (
        "from ..agents",
        "from minions.agents",
        "import minions.agents",
        "from ..app",
        "from minions.app",
        "import minions.app",
        "from ..loop",
        'sys.modules.get("minions.agents.tools")',
    )
    for path in PLUGINS_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in forbidden):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_plugin_api_delegates_tool_registration_to_host() -> None:
    host_module = importlib.import_module("minions.plugins.host")
    api_module = importlib.import_module("minions.plugins.api")
    registry_module = importlib.import_module("minions.plugins.registry")
    host = _Host()
    host_module.configure_plugin_host(host)
    registry = registry_module.PluginRegistry()
    api = api_module.PluginApi("demo", {}, {"id": "demo"})
    api.set_registry(registry)

    def tool_func() -> None:
        return None

    api.register_tool("demo_tool", tool_func, description="demo")
    hook = next(
        item
        for item in registry.get_startup_hooks()
        if item.hook_name == "register_tool_demo_demo_tool"
    )
    hook.callback()

    assert host.tools == [
        {
            "plugin_id": "demo",
            "tool_name": "demo_tool",
            "tool_func": tool_func,
            "description": "demo",
            "icon": "🔧",
            "enabled": False,
        },
    ]


def test_loader_delegates_tool_cleanup_to_host() -> None:
    host_module = importlib.import_module("minions.plugins.host")
    loader_module = importlib.import_module("minions.plugins.loader")
    host = _Host()
    host_module.configure_plugin_host(host)
    loader = loader_module.PluginLoader([])
    record = SimpleNamespace(
        manifest=SimpleNamespace(
            meta={
                "tool_name": "legacy_tool",
                "tools": [{"name": "modern_tool"}],
            },
        ),
    )

    loader._cleanup_plugin_tools("demo", record)

    assert host.removed_tools == [
        ("demo", ("legacy_tool", "modern_tool")),
    ]
