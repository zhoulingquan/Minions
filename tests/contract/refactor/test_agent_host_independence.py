# -*- coding: utf-8 -*-
"""Contracts for agent-owned typed hosts and isolated imports."""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_ROOT = (
    REPO_ROOT / "packages" / "minions-agents" / "src" / "minions"
)


def test_acp_host_protocol_and_app_adapter_exist() -> None:
    host_module = importlib.import_module("minions.agents.acp.host")
    app_host_module = importlib.import_module("minions.app.acp_host")

    assert hasattr(host_module, "ACPHostServices")
    assert hasattr(app_host_module, "AppACPHostServices")


def test_agents_acp_tree_has_no_app_dependency() -> None:
    offenders: list[str] = []
    for path in (AGENTS_ROOT / "agents" / "acp").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if (
            "from ...app" in source
            or "from minions.app" in source
            or "import minions.app" in source
        ):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_agents_tree_has_no_app_dependency() -> None:
    offenders: list[str] = []
    for path in (AGENTS_ROOT / "agents").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if (
            "from ..app" in source
            or "from ...app" in source
            or "from minions.app" in source
            or "import minions.app" in source
        ):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_app_owns_daemon_command_specs() -> None:
    daemon = importlib.import_module("minions.app.commands.daemon")

    names = {spec.name for spec in daemon.collect_daemon_command_specs()}
    assert names == {
        "daemon",
        "logs",
        "reload-config",
        "restart",
        "status",
        "version",
    }


def test_acp_host_required_paths_fail_explicitly() -> None:
    server = importlib.import_module("minions.agents.acp.server")
    agent = server.MinionsACPAgent(agent_id="default")

    with pytest.raises(RuntimeError, match="host services.*not configured"):
        agent._require_host()


@pytest.mark.asyncio
async def test_acp_workspace_lifecycle_uses_injected_host(tmp_path) -> None:
    server = importlib.import_module("minions.agents.acp.server")
    workspace = object()

    class _Host:
        def __init__(self) -> None:
            self.started: list[tuple[str, Path]] = []
            self.stopped: list[Any] = []

        async def start_workspace(
            self,
            agent_id: str,
            workspace_dir: Path,
        ) -> Any:
            self.started.append((agent_id, workspace_dir))
            return workspace

        async def stop_workspace(self, value: Any) -> None:
            self.stopped.append(value)

    host = _Host()
    agent = server.MinionsACPAgent(
        agent_id="writer",
        workspace_dir=tmp_path,
        host=host,
    )

    assert await agent._ensure_workspace() is workspace
    assert host.started == [("writer", tmp_path)]

    await agent._shutdown_workspace()
    assert host.stopped == [workspace]
