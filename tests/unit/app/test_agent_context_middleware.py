# -*- coding: utf-8 -*-
"""Path parsing regressions for Agent context middleware."""

from minions.app.routers.agent_scoped import _agent_id_from_path


def test_agent_id_from_scoped_path() -> None:
    assert _agent_id_from_path("/api/agents/demo/tools") == "demo"
    assert _agent_id_from_path("/api/agents/demo") == "demo"


def test_agent_order_control_path_is_not_an_agent() -> None:
    assert _agent_id_from_path("/api/agents/order") is None
