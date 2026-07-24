# -*- coding: utf-8 -*-
"""App implementation of the typed plugin integration boundary."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AppPluginHost:
    """Bridge plugin registrations to agent, loop, channel, and skill owners."""

    def register_tool(
        self,
        *,
        plugin_id: str,
        tool_name: str,
        tool_func: Callable[..., Any],
        description: str,
        icon: str,
        enabled: bool,
    ) -> None:
        """Expose a plugin tool and persist its per-agent config entry."""
        from ..agents import tools as tools_module
        from ..config.config import (
            BuiltinToolConfig,
            ToolsConfig,
            load_agent_config,
            save_agent_config,
        )
        from ..core.context import get_current_agent_id

        setattr(tools_module, tool_name, tool_func)
        if tool_name not in tools_module.__all__:
            tools_module.__all__.append(tool_name)

        agent_id = get_current_agent_id()
        if not agent_id:
            logger.warning(
                "No current agent ID; tool '%s' will be available after restart",
                tool_name,
            )
            return
        agent_config = load_agent_config(agent_id)
        if not agent_config.tools:
            agent_config.tools = ToolsConfig()
        if tool_name not in agent_config.tools.builtin_tools:
            agent_config.tools.builtin_tools[tool_name] = BuiltinToolConfig(
                name=tool_name,
                enabled=enabled,
                description=description,
                display_to_user=True,
                async_execution=False,
                icon=icon,
            )
        save_agent_config(agent_id, agent_config)
        logger.info(
            "Plugin '%s' registered tool '%s' for agent '%s'",
            plugin_id,
            tool_name,
            agent_id,
        )

    def unregister_tools(
        self,
        plugin_id: str,
        tool_names: list[str],
    ) -> None:
        """Remove plugin-owned attributes from the agent tools package."""
        from ..agents import tools as tools_module

        for tool_name in tool_names:
            if hasattr(tools_module, tool_name):
                delattr(tools_module, tool_name)
            if tool_name in tools_module.__all__:
                tools_module.__all__.remove(tool_name)
        if tool_names:
            logger.info(
                "Removed tools %s for plugin '%s'",
                tool_names,
                plugin_id,
            )

    @staticmethod
    def create_stop_handler_registration(
        *,
        plugin_id: str,
        handler: Callable[..., Any],
        priority: int,
        name: str,
    ) -> Any:
        """Create the loop-owned stop-handler registration value."""
        from ..loop.gates import StopHandlerRegistration

        return StopHandlerRegistration(
            plugin_id=plugin_id,
            handler=handler,
            priority=priority,
            name=name,
        )

    @staticmethod
    def validate_prompt_anchor(anchor: str) -> None:
        """Validate against the agent prompt builder's host anchors."""
        from ..agents.prompt_builder import PromptBuilder

        if anchor not in PromptBuilder.HOST_ANCHORS:
            raise ValueError(
                f"Prompt section after='{anchor}' must reference a host anchor",
            )

    @staticmethod
    def validate_channel(channel_key: str, channel_class: type) -> None:
        """Validate channel ownership rules without coupling plugins to app."""
        from ..channels.base import BaseChannel
        from ..channels.registry import BUILTIN_CHANNEL_KEYS

        if channel_key in BUILTIN_CHANNEL_KEYS:
            raise ValueError(
                f"Channel '{channel_key}' conflicts with a built-in channel "
                "and cannot be registered by a plugin",
            )
        if not (
            isinstance(channel_class, type)
            and issubclass(channel_class, BaseChannel)
            and channel_class is not BaseChannel
        ):
            raise TypeError(
                "channel_class must be a concrete BaseChannel subclass, "
                f"got {channel_class!r}",
            )

    def install_plugin_skills(
        self,
        *,
        plugin_id: str,
        skills_dir: Path,
        source_tag: str,
        enabled_by_default: bool,
        channels: list[str],
    ) -> None:
        """Install plugin skills into every registered workspace."""
        from ..agents.skill_system.registry import list_workspaces

        for workspace_info in list_workspaces():
            self.install_plugin_skills_into_workspace(
                plugin_id=plugin_id,
                workspace_info=workspace_info,
                skills_dir=skills_dir,
                source_tag=source_tag,
                enabled_by_default=enabled_by_default,
                channels=channels,
            )

    @staticmethod
    def install_plugin_skills_into_workspace(
        *,
        plugin_id: str,
        workspace_info: dict[str, Any],
        skills_dir: Path,
        source_tag: str,
        enabled_by_default: bool,
        channels: list[str],
    ) -> None:
        """Install plugin skills and update one workspace manifest."""
        from ..agents.skill_system.registry import reconcile_workspace_manifest
        from ..agents.skill_system.store import (
            copy_skill_dir,
            default_workspace_manifest,
            get_workspace_skill_manifest_path,
            get_workspace_skills_dir,
            mutate_json,
        )

        skill_names = AppPluginHost._skill_names(skills_dir)
        if not skill_names:
            return
        workspace_dir = Path(workspace_info["workspace_dir"])
        workspace_skills_dir = get_workspace_skills_dir(workspace_dir)
        workspace_skills_dir.mkdir(parents=True, exist_ok=True)
        for skill_name in skill_names:
            copy_skill_dir(
                skills_dir / skill_name,
                workspace_skills_dir / skill_name,
            )
        reconcile_workspace_manifest(workspace_dir)
        manifest_path = get_workspace_skill_manifest_path(workspace_dir)

        def _apply_defaults(payload: dict[str, Any]) -> dict[str, Any]:
            skills = payload.setdefault("skills", {})
            for name in skill_names:
                entry = skills.get(name)
                if entry is None:
                    continue
                if entry.get("source") != source_tag:
                    entry["enabled"] = enabled_by_default
                    entry["channels"] = list(channels)
                entry["source"] = source_tag
            return payload

        mutate_json(
            manifest_path,
            default_workspace_manifest(),
            _apply_defaults,
        )
        logger.debug(
            "Plugin '%s' installed %d skill(s) into workspace '%s'",
            plugin_id,
            len(skill_names),
            workspace_info.get("agent_id", "?"),
        )

    @staticmethod
    def uninstall_plugin_skills(
        *,
        plugin_id: str,
        source_tag: str,
    ) -> None:
        """Remove plugin-sourced skills from every workspace."""
        from ..agents.skill_system.registry import list_workspaces
        from ..agents.skill_system.store import (
            default_workspace_manifest,
            get_workspace_skill_manifest_path,
            get_workspace_skills_dir,
            mutate_json,
        )

        workspaces = list_workspaces()
        for workspace_info in workspaces:
            workspace_dir = Path(workspace_info["workspace_dir"])
            workspace_skills_dir = get_workspace_skills_dir(workspace_dir)
            manifest_path = get_workspace_skill_manifest_path(workspace_dir)

            def _remove_plugin_skills(payload: dict[str, Any]) -> dict[str, Any]:
                skills = payload.setdefault("skills", {})
                names = [
                    name
                    for name, entry in skills.items()
                    if entry.get("source") == source_tag
                ]
                for name in names:
                    skills.pop(name, None)
                    skill_dir = workspace_skills_dir / name
                    if skill_dir.exists():
                        shutil.rmtree(skill_dir)
                return payload

            mutate_json(
                manifest_path,
                default_workspace_manifest(),
                _remove_plugin_skills,
            )
        logger.info(
            "Plugin '%s' skills cleaned up from %d workspace(s)",
            plugin_id,
            len(workspaces),
        )

    @staticmethod
    def _skill_names(skills_dir: Path) -> list[str]:
        if not skills_dir.exists() or not skills_dir.is_dir():
            return []
        return [
            path.name
            for path in skills_dir.iterdir()
            if path.is_dir() and (path / "SKILL.md").exists()
        ]


__all__ = ["AppPluginHost"]
