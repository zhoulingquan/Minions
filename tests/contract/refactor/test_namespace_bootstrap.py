# -*- coding: utf-8 -*-
"""Contracts for the explicit, side-effect-free Minions bootstrap."""
from __future__ import annotations

from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def _run_isolated_python(code: str, *, env: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"isolated Python failed with {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_ROOT)
    env["MINIONS_WORKING_DIR"] = str(tmp_path / "working")
    env["MINIONS_SECRET_DIR"] = str(tmp_path / "secrets")
    return env


def _reload_bootstrap_module():
    module = importlib.import_module("minions.bootstrap")
    return importlib.reload(module)


def test_importing_namespace_does_not_configure_logging(tmp_path: Path) -> None:
    code = """
import logging

root = logging.getLogger()
project = logging.getLogger("minions")
before = (root.level, tuple(root.handlers), project.level,
          tuple(project.handlers), project.propagate)
import minions
after = (root.level, tuple(root.handlers), project.level,
         tuple(project.handlers), project.propagate)
assert after == before, (before, after)
"""
    _run_isolated_python(code, env=_isolated_env(tmp_path))


def test_importing_namespace_does_not_load_persisted_env(
    tmp_path: Path,
) -> None:
    env = _isolated_env(tmp_path)
    secret_dir = Path(env["MINIONS_SECRET_DIR"])
    secret_dir.mkdir(parents=True)
    (secret_dir / "envs.json").write_text(
        json.dumps({"MINIONS_NAMESPACE_IMPORT_PROBE": ""}),
        encoding="utf-8",
    )
    env.pop("MINIONS_NAMESPACE_IMPORT_PROBE", None)

    code = """
import os
import minions
assert "MINIONS_NAMESPACE_IMPORT_PROBE" not in os.environ
"""
    _run_isolated_python(code, env=env)


def test_bootstrap_loads_env_before_constant_import(tmp_path: Path) -> None:
    env = _isolated_env(tmp_path)
    secret_dir = Path(env["MINIONS_SECRET_DIR"])
    secret_dir.mkdir(parents=True)
    (secret_dir / "envs.json").write_text(
        json.dumps({"MINIONS_OPENAPI_DOCS": "true"}),
        encoding="utf-8",
    )
    env.pop("MINIONS_OPENAPI_DOCS", None)
    env["MINIONS_DISABLE_KEYRING"] = "1"

    code = """
import os
from minions.bootstrap import bootstrap_minions

bootstrap_minions()
from minions.constant import DOCS_ENABLED

assert os.environ["MINIONS_OPENAPI_DOCS"] == "true"
assert DOCS_ENABLED is True
"""
    _run_isolated_python(code, env=env)


def test_bootstrap_runs_env_then_logging_once(monkeypatch) -> None:
    bootstrap = _reload_bootstrap_module()
    bootstrap_env = importlib.import_module("minions.app.bootstrap_env")
    logging_utils = importlib.import_module("minions.utils.logging")
    calls: list[tuple[str, str | None]] = []

    monkeypatch.setenv("MINIONS_LOG_LEVEL", "debug")
    monkeypatch.setattr(
        bootstrap_env,
        "load_bootstrap_env",
        lambda: calls.append(("env", None)),
    )
    monkeypatch.setattr(
        logging_utils,
        "setup_logger",
        lambda level: calls.append(("logging", level)),
    )

    bootstrap.bootstrap_minions()
    bootstrap.bootstrap_minions()

    assert calls == [("env", None), ("logging", "debug")]


def test_bootstrap_failure_propagates_and_remains_retryable(monkeypatch) -> None:
    bootstrap = _reload_bootstrap_module()
    bootstrap_env = importlib.import_module("minions.app.bootstrap_env")
    logging_utils = importlib.import_module("minions.utils.logging")
    calls: list[str] = []

    def load_env() -> None:
        calls.append("env")
        if calls.count("env") == 1:
            raise RuntimeError("bootstrap failed")

    monkeypatch.setattr(bootstrap_env, "load_bootstrap_env", load_env)
    monkeypatch.setattr(
        logging_utils,
        "setup_logger",
        lambda _level: calls.append("logging"),
    )

    with pytest.raises(RuntimeError, match="bootstrap failed"):
        bootstrap.bootstrap_minions()

    bootstrap.bootstrap_minions()
    bootstrap.bootstrap_minions()
    assert calls == ["env", "env", "logging"]


def test_application_bootstrap_owns_restore_cleanup(monkeypatch) -> None:
    bootstrap_env = importlib.import_module("minions.app.bootstrap_env")
    safe_swap = importlib.import_module("minions.backup._utils.safe_swap")
    env_store = importlib.import_module("minions.envs.store")
    calls: list[str] = []

    @contextmanager
    def process_lock():
        calls.append("lock-enter")
        yield
        calls.append("lock-exit")

    monkeypatch.setattr(safe_swap, "restore_process_lock", process_lock)
    monkeypatch.setattr(
        safe_swap,
        "cleanup_stale_restore_artifacts",
        lambda _path: calls.append("cleanup"),
    )
    monkeypatch.setattr(
        env_store,
        "load_envs_into_environ",
        lambda: calls.append("load") or {"persisted": "value"},
    )

    assert bootstrap_env.load_bootstrap_env() == {"persisted": "value"}
    assert calls == ["lock-enter", "cleanup", "load", "lock-exit"]


def test_namespace_roots_and_env_store_have_no_legacy_bootstrap() -> None:
    assert not (SRC_ROOT / "minions" / "__init__.py").exists()
    assert not (SRC_ROOT / "minions" / "app" / "__init__.py").exists()
    store_source = (SRC_ROOT / "minions" / "envs" / "store.py").read_text(
        encoding="utf-8",
    )
    assert "minions.backup" not in store_source


def test_composition_roots_bootstrap_before_env_backed_imports() -> None:
    cli_source = (SRC_ROOT / "minions" / "cli" / "main.py").read_text(
        encoding="utf-8",
    )
    app_source = (SRC_ROOT / "minions" / "app" / "_app.py").read_text(
        encoding="utf-8",
    )

    assert cli_source.index("bootstrap_minions()") < cli_source.index(
        "from ..config.utils import",
    )
    assert app_source.index("bootstrap_minions()") < app_source.index(
        "from ..config import",
    )

    assert "load_envs_into_environ" not in app_source
    assert app_source.count("setup_logger") == 0
    assert "logger = logging.getLogger(__name__)" in app_source
