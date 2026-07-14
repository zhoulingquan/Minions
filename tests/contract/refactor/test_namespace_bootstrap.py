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
import threading

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


def test_protected_bootstrap_paths_remain_frozen(tmp_path: Path) -> None:
    env = _isolated_env(tmp_path)
    code = """
from contextlib import nullcontext
import os
from pathlib import Path

from minions._bootstrap_paths import (
    get_bootstrap_secret_dir,
    get_bootstrap_working_dir,
)

working_dir = get_bootstrap_working_dir()
secret_dir = get_bootstrap_secret_dir()
os.environ["MINIONS_WORKING_DIR"] = str(working_dir.parent / "changed")
os.environ["MINIONS_SECRET_DIR"] = str(secret_dir.parent / "changed-secret")

assert get_bootstrap_working_dir() == working_dir
assert get_bootstrap_secret_dir() == secret_dir

from minions.app import bootstrap_env
from minions.backup._utils import safe_swap
from minions.envs import store as env_store
from minions.security import secret_store

assert env_store.get_envs_json_path() == secret_dir / "envs.json"
assert secret_store._get_secret_dir() == secret_dir

with safe_swap.restore_process_lock():
    pass
assert (working_dir / ".minions_restore.lock").exists()
assert not (
    Path(os.environ["MINIONS_WORKING_DIR"]) / ".minions_restore.lock"
).exists()

cleaned = []
safe_swap.restore_process_lock = lambda: nullcontext()
safe_swap.cleanup_stale_restore_artifacts = cleaned.append
env_store.load_envs_into_environ = lambda: {}
assert bootstrap_env.load_bootstrap_env() == {}
assert cleaned == [secret_dir]
"""
    _run_isolated_python(code, env=env)


def _composition_env(tmp_path: Path) -> dict[str, str]:
    env = _isolated_env(tmp_path)
    secret_dir = Path(env["MINIONS_SECRET_DIR"])
    secret_dir.mkdir(parents=True)
    (secret_dir / "envs.json").write_text(
        json.dumps(
            {
                "MINIONS_COMPOSITION_PROBE": "loaded",
                "MINIONS_OPENAPI_DOCS": "true",
            },
        ),
        encoding="utf-8",
    )
    env.pop("MINIONS_COMPOSITION_PROBE", None)
    env.pop("MINIONS_OPENAPI_DOCS", None)
    env["MINIONS_DISABLE_KEYRING"] = "1"
    env["MINIONS_LOG_LEVEL"] = "debug"
    return env


def test_cli_composition_root_executes_bootstrap(tmp_path: Path) -> None:
    code = """
import logging
import os

import minions.cli.main
from minions.constant import DOCS_ENABLED

project_logger = logging.getLogger("minions")
assert os.environ["MINIONS_COMPOSITION_PROBE"] == "loaded"
assert DOCS_ENABLED is True
assert project_logger.level == logging.DEBUG
assert project_logger.handlers
assert project_logger.propagate is False
"""
    _run_isolated_python(code, env=_composition_env(tmp_path))


def test_app_composition_root_preserves_project_logger(tmp_path: Path) -> None:
    code = """
import logging
import os

from minions.app import _app

project_logger = logging.getLogger("minions")
assert os.environ["MINIONS_COMPOSITION_PROBE"] == "loaded"
assert _app.DOCS_ENABLED is True
assert _app.app.docs_url == "/docs"
assert _app.logger is project_logger
assert _app.logger.level == logging.DEBUG
assert _app.logger.handlers
assert _app.logger.propagate is False
"""
    _run_isolated_python(code, env=_composition_env(tmp_path))


def test_bootstrap_runs_env_then_logging_once(monkeypatch) -> None:
    bootstrap = _reload_bootstrap_module()
    bootstrap_env = importlib.import_module("minions.app.bootstrap_env")
    logging_utils = importlib.import_module("minions.utils.logging")
    calls: list[str] = []

    monkeypatch.setenv("MINIONS_LOG_LEVEL", "debug")
    monkeypatch.setattr(
        bootstrap.time,
        "perf_counter",
        lambda: calls.append("clock") or 1.0,
    )
    monkeypatch.setattr(
        bootstrap_env,
        "load_bootstrap_env",
        lambda: calls.append("env"),
    )
    monkeypatch.setattr(
        logging_utils,
        "setup_logger",
        lambda level: calls.append(f"logging:{level}"),
    )

    bootstrap.bootstrap_minions()
    bootstrap.bootstrap_minions()

    assert calls == ["env", "clock", "logging:debug", "clock"]


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


def test_waiting_bootstrap_caller_retries_after_failure(monkeypatch) -> None:
    bootstrap = _reload_bootstrap_module()
    bootstrap_env = importlib.import_module("minions.app.bootstrap_env")
    logging_utils = importlib.import_module("minions.utils.logging")
    first_entered = threading.Event()
    release_first = threading.Event()
    waiter_started = threading.Event()
    calls: list[str] = []
    errors: list[Exception] = []

    def load_env() -> None:
        calls.append("env")
        if calls.count("env") == 1:
            first_entered.set()
            assert release_first.wait(timeout=5)
            raise RuntimeError("first caller failed")

    monkeypatch.setattr(bootstrap_env, "load_bootstrap_env", load_env)
    monkeypatch.setattr(
        logging_utils,
        "setup_logger",
        lambda _level: calls.append("logging"),
    )

    def call_bootstrap(*, waiter: bool = False) -> None:
        if waiter:
            waiter_started.set()
        try:
            bootstrap.bootstrap_minions()
        except Exception as exc:  # expected from the first caller only
            errors.append(exc)

    first = threading.Thread(target=call_bootstrap)
    waiter = threading.Thread(
        target=call_bootstrap,
        kwargs={"waiter": True},
    )
    first.start()
    assert first_entered.wait(timeout=5)
    waiter.start()
    assert waiter_started.wait(timeout=5)
    release_first.set()
    first.join(timeout=5)
    waiter.join(timeout=5)

    assert not first.is_alive()
    assert not waiter.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert calls == ["env", "env", "logging"]

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


def test_lazy_backup_exports_remain_discoverable() -> None:
    backup = importlib.import_module("minions.backup")
    assert set(backup.__all__).issubset(dir(backup))
