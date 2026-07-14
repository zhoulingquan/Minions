# -*- coding: utf-8 -*-
"""Focused concurrency tests for workspace task acquisition."""

from types import SimpleNamespace

from minions.app.multi_agent_manager import MultiAgentManager
from minions.app.task_tracker import TaskTracker


async def test_acquire_agent_task_registers_on_current_workspace(
    monkeypatch,
) -> None:
    manager = MultiAgentManager()
    old_workspace = SimpleNamespace(task_tracker=TaskTracker())
    new_workspace = SimpleNamespace(task_tracker=TaskTracker())
    manager.agents["default"] = old_workspace

    async def get_agent_during_reload(_agent_id: str):
        # Model a reload swap after a caller starts resolving the workspace
        # but before it enters the manager's atomic acquisition section.
        manager.agents["default"] = new_workspace
        return old_workspace

    monkeypatch.setattr(manager, "get_agent", get_agent_during_reload)

    acquired = await manager.acquire_agent_task("default", "run-1")

    assert acquired is new_workspace
    assert await new_workspace.task_tracker.has_active_tasks() is True
    assert await old_workspace.task_tracker.has_active_tasks() is False

    await acquired.task_tracker.unregister_external_task("run-1")
