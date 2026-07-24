# -*- coding: utf-8 -*-
"""Typed host boundary for optional high-level plugin integrations."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol


class PluginHost(Protocol):
    """Capabilities supplied by an app composition root."""

    def register_tool(
        self,
        *,
        plugin_id: str,
        tool_name: str,
        tool_func: Callable[..., Any],
        description: str,
        icon: str,
        enabled: bool,
    ) -> None: ...

    def unregister_tools(
        self,
        plugin_id: str,
        tool_names: list[str],
    ) -> None: ...

    def create_stop_handler_registration(
        self,
        *,
        plugin_id: str,
        handler: Callable[..., Any],
        priority: int,
        name: str,
    ) -> Any: ...

    def validate_prompt_anchor(self, anchor: str) -> None: ...

    def validate_channel(self, channel_key: str, channel_class: type) -> None: ...

    def install_plugin_skills(
        self,
        *,
        plugin_id: str,
        skills_dir: Path,
        source_tag: str,
        enabled_by_default: bool,
        channels: list[str],
    ) -> None: ...

    def install_plugin_skills_into_workspace(
        self,
        *,
        plugin_id: str,
        workspace_info: dict[str, Any],
        skills_dir: Path,
        source_tag: str,
        enabled_by_default: bool,
        channels: list[str],
    ) -> None: ...

    def uninstall_plugin_skills(
        self,
        *,
        plugin_id: str,
        source_tag: str,
    ) -> None: ...


_plugin_host: PluginHost | None = None


def configure_plugin_host(host: PluginHost | None) -> None:
    """Install or clear the process-wide typed plugin host."""
    global _plugin_host
    _plugin_host = host


def get_plugin_host() -> PluginHost | None:
    """Return the configured host without requiring high-level packages."""
    return _plugin_host


def require_plugin_host() -> PluginHost:
    """Return the configured host or fail explicitly for host-only APIs."""
    if _plugin_host is None:
        raise RuntimeError("plugin host is not configured")
    return _plugin_host


__all__ = [
    "PluginHost",
    "configure_plugin_host",
    "get_plugin_host",
    "require_plugin_host",
]
