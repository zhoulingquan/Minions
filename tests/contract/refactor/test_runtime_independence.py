# -*- coding: utf-8 -*-
"""Contracts for runtime orchestration without upward dependencies."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = (
    REPO_ROOT / "packages" / "minions-runtime" / "src" / "minions"
)
AGENTS_ROOT = (
    REPO_ROOT / "packages" / "minions-agents" / "src" / "minions"
)
APP_ROOT = REPO_ROOT / "packages" / "minions-app" / "src" / "minions"


def test_runtime_consumes_an_injected_agent_builder() -> None:
    runtime_module = importlib.import_module("minions.runtime.runtime")
    parameters = inspect.signature(runtime_module.Runtime).parameters
    source = (RUNTIME_ROOT / "runtime" / "runtime.py").read_text(
        encoding="utf-8",
    )

    assert "agent_builder" in parameters
    assert "from .builder import AgentBuilder" not in source

    builder = object()
    runtime = runtime_module.Runtime(
        workspace=object(),
        app_services=object(),
        agent_builder=builder,
    )
    assert runtime.agent_builder is builder


def test_agent_composition_modules_have_moved_out_of_runtime() -> None:
    moves = {
        "builder.py": "runtime_builder.py",
        "builtin_commands.py": "builtin_commands.py",
        "prompt_contributors.py": "prompt_contributors.py",
    }
    for old_name, new_name in moves.items():
        assert not (RUNTIME_ROOT / "runtime" / old_name).exists()
        assert (AGENTS_ROOT / "agents" / new_name).is_file()

    importlib.import_module("minions.agents.runtime_builder")
    importlib.import_module("minions.agents.builtin_commands")
    importlib.import_module("minions.agents.prompt_contributors")


def test_environment_and_state_helpers_have_downward_owners() -> None:
    environment_context = importlib.import_module(
        "minions.core.environment_context",
    )
    state_compat = importlib.import_module("minions.agents.state_compat")
    chats_utils = importlib.import_module("minions.app.chats.utils")

    assert chats_utils.build_env_context is environment_context.build_env_context
    assert chats_utils.parse_legacy_memory_state is (
        state_compat.parse_legacy_memory_state
    )

    source = (APP_ROOT / "app" / "chats" / "utils.py").read_text(
        encoding="utf-8",
    )
    assert "def build_env_context" not in source
    assert "def parse_legacy_memory_state" not in source


def test_runtime_tree_has_no_agent_or_app_imports() -> None:
    offenders: list[str] = []
    for path in (RUNTIME_ROOT / "runtime").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "minions.agents" in source or "minions.app" in source:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
        if "..agents" in source or "..app" in source:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert sorted(set(offenders)) == []


def test_token_estimation_implementation_is_owned_by_runtime() -> None:
    runtime_counter = importlib.import_module(
        "minions.token_usage.estimate_token_counter",
    )
    runtime_stats = importlib.import_module("minions.token_usage.context_stats")
    agent_counter = importlib.import_module(
        "minions.agents.utils.estimate_token_counter",
    )
    agent_stats = importlib.import_module("minions.agents.utils.context_stats")

    assert agent_counter.EstimatedTokenCounter is (
        runtime_counter.EstimatedTokenCounter
    )
    assert agent_stats.estimate_context_tokens is (
        runtime_stats.estimate_context_tokens
    )
