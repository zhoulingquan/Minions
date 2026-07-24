# -*- coding: utf-8 -*-
"""App-owned host implementation for the independently importable ACP agent."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AppACPHostServices:
    """Compose app services, workspaces, hooks, and approvals for ACP."""

    def __init__(self, app_services: Any | None = None) -> None:
        self._app_services = app_services
        self._app_services_started = False

    async def start_workspace(
        self,
        agent_id: str,
        workspace_dir: Path,
    ) -> Any:
        """Create and start a fully composed app workspace."""
        from .app_services import AppServiceManager
        from .plugin_host import AppPluginHost
        from .workspace.workspace import Workspace
        from ..plugins.host import configure_plugin_host

        configure_plugin_host(AppPluginHost())

        if self._app_services is None:
            self._app_services = AppServiceManager()
        if not self._app_services_started:
            await self._app_services.start()
            self._app_services_started = True

        workspace = Workspace(
            agent_id=agent_id,
            workspace_dir=str(workspace_dir),
        )
        workspace.bootstrap_plugins(
            **self._build_bootstrap_kwargs(self._app_services),
        )
        workspace.set_app_services(self._app_services)
        await workspace.start()
        return workspace

    async def stop_workspace(self, workspace: Any) -> None:
        """Stop the workspace and its ACP-local app services."""
        try:
            await workspace.stop(final=True)
        finally:
            if self._app_services is not None and self._app_services_started:
                await self._app_services.stop()
                self._app_services_started = False

    async def get_pending_approvals(self, session_id: str) -> list[Any]:
        """Return deduplicated approvals routed to an ACP session."""
        service = self._approval_service()
        pending_by_root = await service.get_pending_by_root_session(session_id)
        pending_direct = await service.get_all_pending_by_session(session_id)
        return list(
            {
                pending.request_id: pending
                for pending in [*pending_by_root, *pending_direct]
            }.values(),
        )

    async def resolve_approval(
        self,
        request_id: str,
        decision: Any,
        *,
        scope: Any = None,
    ) -> Any:
        """Resolve one app-owned approval record."""
        return await self._approval_service().resolve_request(
            request_id,
            decision,
            scope=scope,
        )

    @staticmethod
    def approval_display(pending: Any) -> dict[str, Any]:
        """Return app-specific display metadata for an approval."""
        from .approvals.display import approval_display_fields

        return approval_display_fields(pending)

    async def cancel_pending_approvals(self, session_id: str) -> None:
        """Cancel approvals associated with a closed ACP session."""
        await self._approval_service().cancel_all_pending_by_root_session(
            session_id,
        )

    def _approval_service(self) -> Any:
        if self._app_services is not None:
            coordinator = getattr(
                self._app_services,
                "approval_coordinator",
                None,
            )
            if coordinator is not None:
                return coordinator
        from .approvals import get_approval_service

        return get_approval_service()

    @staticmethod
    def _build_bootstrap_kwargs(app_services: Any) -> dict[str, Any]:
        """Build the runtime plugin set shared with the web app lifespan."""
        kwargs: dict[str, Any] = {}
        command_specs: list[Any] = []

        try:
            from ..agents.tools import discover_builtin_tool_funcs

            kwargs["builtin_tool_funcs"] = discover_builtin_tool_funcs()
        except Exception:
            logger.debug(
                "ACP bootstrap: built-in tools skipped",
                exc_info=True,
            )

        try:
            from ..agents.builtin_commands import (
                collect_builtin_command_specs,
                get_skill_fallback_handler,
            )
            from ..agents.control_handlers import (
                register_agent_control_handlers,
            )
            from .control_handlers import register_app_control_handlers
            from .commands.daemon import collect_daemon_command_specs

            register_agent_control_handlers()
            register_app_control_handlers()
            command_specs.extend(collect_builtin_command_specs())
            command_specs.extend(collect_daemon_command_specs())
            kwargs["builtin_fallback_handler"] = get_skill_fallback_handler()
        except Exception:
            logger.debug(
                "ACP bootstrap: built-in slash commands skipped",
                exc_info=True,
            )

        try:
            from .app_services._builtin_tool_commands import (
                build_tool_command_specs,
            )

            command_specs.extend(
                build_tool_command_specs(app_services.tool_coordinator),
            )
        except Exception:
            logger.debug(
                "ACP bootstrap: HITL tool commands skipped",
                exc_info=True,
            )

        if command_specs:
            kwargs["builtin_command_specs"] = command_specs

        try:
            from ..agents.lifecycle_hooks import (
                BootstrapHook,
                MediaProcessHook,
                SessionLoadHook,
                SessionSaveHook,
                SkillEnvCleanupHook,
                SkillEnvHook,
            )
            from ..hooks.cron.cron_hook import CronContextHook
            from .lifecycle_hooks import (
                CancelCleanupHook,
                ErrorNormalizeHook,
            )
            from ..hooks.request_setup.contextvars_hook import (
                ContextVarsSetupHook,
            )
            from ..sage.lifecycle import (
                SageBeginHook,
                SageCompleteHook,
                SageErrorHook,
                SageIdentityHook,
            )

            kwargs["builtin_hook_clses"] = [
                CronContextHook,
                SessionLoadHook,
                SessionSaveHook,
                BootstrapHook,
                SkillEnvHook,
                SkillEnvCleanupHook,
                ContextVarsSetupHook,
                MediaProcessHook,
                SageIdentityHook,
                SageBeginHook,
                SageCompleteHook,
                SageErrorHook,
                ErrorNormalizeHook,
                CancelCleanupHook,
            ]
        except Exception:
            logger.debug(
                "ACP bootstrap: lifecycle hooks skipped",
                exc_info=True,
            )

        try:
            from ..agents.prompt_contributors import _ALL_CONTRIBUTORS

            kwargs["builtin_contributor_clses"] = _ALL_CONTRIBUTORS
        except Exception:
            logger.debug(
                "ACP bootstrap: prompt contributors skipped",
                exc_info=True,
            )

        try:
            from ..modes.goal import GoalMode
            from ..modes.mission import MissionMode

            kwargs["builtin_mode_clses"] = [MissionMode, GoalMode]
        except Exception:
            logger.debug(
                "ACP bootstrap: modes skipped",
                exc_info=True,
            )

        return kwargs


__all__ = ["AppACPHostServices"]
