# -*- coding: utf-8 -*-
"""Tests for channel-owned dynamic registration."""
from __future__ import annotations

import pytest

from minions.channels.base import BaseChannel
from minions.channels.registry import (
    clear_registered_channels,
    get_channel_registry,
    register_channel,
    unregister_channel,
)


class _DemoChannel(BaseChannel):
    channel = "demo"


@pytest.fixture(autouse=True)
def reset_dynamic_channels():
    clear_registered_channels()
    yield
    clear_registered_channels()


def test_register_and_unregister_dynamic_channel() -> None:
    register_channel("demo", _DemoChannel)
    assert get_channel_registry()["demo"] is _DemoChannel

    unregister_channel("demo")
    assert "demo" not in get_channel_registry()


def test_dynamic_channel_cannot_replace_builtin() -> None:
    with pytest.raises(ValueError, match="built-in"):
        register_channel("console", _DemoChannel)


def test_plugin_registry_updates_channel_owner_registry() -> None:
    from minions.app.plugin_host import AppPluginHost
    from minions.plugins.host import configure_plugin_host
    from minions.plugins.registry import PluginRegistry

    old_instance = PluginRegistry._instance
    PluginRegistry._instance = None
    configure_plugin_host(AppPluginHost())
    try:
        registry = PluginRegistry()
        registry.register_channel(
            plugin_id="demo-plugin",
            channel_key="demo",
            channel_class=_DemoChannel,
        )
        assert get_channel_registry()["demo"] is _DemoChannel

        registry.unregister_plugin("demo-plugin")
        assert "demo" not in get_channel_registry()
    finally:
        configure_plugin_host(None)
        PluginRegistry._instance = old_instance
