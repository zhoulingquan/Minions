# -*- coding: utf-8 -*-
"""Contracts for the core-owned request ContextVars."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOTS = {
    "agents": REPO_ROOT / "packages" / "minions-agents" / "src",
    "hooks": REPO_ROOT / "packages" / "minions-runtime" / "src",
    "loop": REPO_ROOT / "packages" / "minions-loop" / "src",
    "modes": REPO_ROOT / "packages" / "minions-modes" / "src",
    "plugins": REPO_ROOT / "packages" / "minions-plugins" / "src",
    "token_usage": REPO_ROOT / "packages" / "minions-runtime" / "src",
}
CORE_SOURCE_ROOT = REPO_ROOT / "packages" / "minions-core" / "src"


def test_agent_token_restores_exact_previous_context(monkeypatch) -> None:
    context = importlib.import_module("minions.core.context")
    monkeypatch.setattr(context, "get_active_agent_id", lambda: "fallback")

    assert context.get_current_agent_id() == "fallback"
    outer = context.set_current_agent_id("outer")
    inner = context.set_current_agent_id("inner")
    assert context.get_current_agent_id() == "inner"

    context.reset_current_agent_id(inner)
    assert context.get_current_agent_id() == "outer"
    context.reset_current_agent_id(outer)
    assert context.get_current_agent_id() == "fallback"


def test_other_context_setters_keep_void_return_contract() -> None:
    context = importlib.import_module("minions.core.context")

    assert context.set_current_session_id("session") is None
    assert context.get_current_session_id() == "session"
    assert context.set_current_root_session_id("root") is None
    assert context.get_current_root_session_id() == "root"
    assert context.set_current_user_id("user") is None
    assert context.get_current_user_id() == "user"
    assert context.set_current_channel("channel") is None
    assert context.get_current_channel() == "channel"


def test_app_agent_context_reexports_core_identity() -> None:
    app_context = importlib.import_module("minions.app.agent_context")
    core_context = importlib.import_module("minions.core.context")

    names = (
        "get_active_agent_id",
        "set_current_agent_id",
        "reset_current_agent_id",
        "get_current_agent_id",
        "set_current_session_id",
        "get_current_session_id",
        "set_current_root_session_id",
        "get_current_root_session_id",
        "set_current_user_id",
        "get_current_user_id",
        "set_current_channel",
        "get_current_channel",
    )
    for name in names:
        assert getattr(app_context, name) is getattr(core_context, name)


def test_importing_core_context_does_not_import_app() -> None:
    code = """
import sys
import minions.core.context
assert not any(name == "minions.app" or name.startswith("minions.app.")
               for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env={**dict(os.environ), "PYTHONPATH": str(CORE_SOURCE_ROOT)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_lower_layers_do_not_import_app_agent_context() -> None:
    lower_roots = (
        "agents",
        "hooks",
        "loop",
        "modes",
        "plugins",
        "token_usage",
    )
    offenders: list[str] = []
    for root_name in lower_roots:
        for path in (
            SOURCE_ROOTS[root_name] / "minions" / root_name
        ).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "app.agent_context" in source:
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []
