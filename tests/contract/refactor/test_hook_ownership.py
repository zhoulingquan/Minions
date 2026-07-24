# -*- coding: utf-8 -*-
"""Contracts for lifecycle hook ownership across distribution layers."""
from __future__ import annotations

import importlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = (
    REPO_ROOT / "packages" / "minions-runtime" / "src" / "minions"
)
AGENTS_ROOT = (
    REPO_ROOT / "packages" / "minions-agents" / "src" / "minions"
)
APP_ROOT = REPO_ROOT / "packages" / "minions-app" / "src" / "minions"


def test_high_level_hooks_have_layer_owned_modules() -> None:
    moves = {
        "hooks/bootstrap/bootstrap_hook.py": (
            AGENTS_ROOT / "agents" / "lifecycle_hooks" / "bootstrap.py"
        ),
        "hooks/request_setup/media_hook.py": (
            AGENTS_ROOT / "agents" / "lifecycle_hooks" / "media.py"
        ),
        "hooks/session/session_hook.py": (
            AGENTS_ROOT / "agents" / "lifecycle_hooks" / "session.py"
        ),
        "hooks/skill_env/skill_env_hook.py": (
            AGENTS_ROOT / "agents" / "lifecycle_hooks" / "skill_env.py"
        ),
        "hooks/error/error_hook.py": (
            APP_ROOT / "app" / "lifecycle_hooks" / "error.py"
        ),
    }
    for old_name, new_path in moves.items():
        assert not (RUNTIME_ROOT / old_name).exists()
        assert new_path.is_file()

    agents_hooks = importlib.import_module("minions.agents.lifecycle_hooks")
    app_hooks = importlib.import_module("minions.app.lifecycle_hooks")
    assert hasattr(agents_hooks, "BootstrapHook")
    assert hasattr(agents_hooks, "MediaProcessHook")
    assert hasattr(agents_hooks, "SessionLoadHook")
    assert hasattr(agents_hooks, "SkillEnvHook")
    assert hasattr(app_hooks, "ErrorNormalizeHook")
    assert hasattr(app_hooks, "CancelCleanupHook")


def test_runtime_owned_hooks_have_no_agents_or_app_imports() -> None:
    offenders: list[str] = []
    for path in (RUNTIME_ROOT / "hooks").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if (
            "from ..agents" in source
            or "from ...agents" in source
            or "from minions.agents" in source
            or "from ..app" in source
            or "from ...app" in source
            or "from minions.app" in source
        ):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []


def test_low_level_request_setup_package_exports_only_contextvars() -> None:
    request_setup = importlib.import_module("minions.hooks.request_setup")

    assert request_setup.__all__ == ["ContextVarsSetupHook"]
    assert not hasattr(request_setup, "MediaProcessHook")
