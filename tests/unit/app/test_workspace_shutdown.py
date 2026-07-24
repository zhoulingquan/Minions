# -*- coding: utf-8 -*-
"""Regression tests for workspace shutdown ordering."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from minions.app.workspace.workspace import Workspace


@pytest.mark.asyncio
async def test_stop_cancels_active_runs_before_stopping_services() -> None:
    events: list[str] = []

    async def list_active_tasks() -> list[str]:
        return ["chat-run"]

    async def request_stop(run_key: str) -> bool:
        events.append(f"cancel:{run_key}")
        return True

    async def wait_all_done(timeout: float) -> bool:
        events.append(f"wait:{timeout}")
        return True

    async def stop_all(*, final: bool) -> None:
        events.append(f"services:{final}")

    workspace = Workspace.__new__(Workspace)
    workspace.agent_id = "shutdown-test"
    workspace._started = True
    workspace._task_tracker = SimpleNamespace(
        list_active_tasks=list_active_tasks,
        request_stop=request_stop,
        wait_all_done=wait_all_done,
    )
    workspace._service_manager = SimpleNamespace(stop_all=stop_all)

    await workspace.stop()

    assert events == ["cancel:chat-run", "wait:5.0", "services:True"]
    assert workspace._started is False
