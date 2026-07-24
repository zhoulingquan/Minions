# -*- coding: utf-8 -*-
"""Contracts for the explicit, side-effect-free Minions bootstrap."""
from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading


REPO_ROOT = Path(__file__).resolve().parents[3]
COMPONENT_SOURCE_ROOTS = tuple(
    REPO_ROOT / "packages" / distribution / "src"
    for distribution in (
        "minions-core",
        "minions-runtime",
        "minions-providers",
        "minions-tool-calls",
        "minions-drivers",
        "minions-channels",
        "minions-plugins",
        "minions-loop",
        "minions-governance",
        "minions-modes",
        "minions-agents",
        "minions-app",
        "minions-cli",
    )
)
CORE_ROOT = COMPONENT_SOURCE_ROOTS[0] / "minions"
AGENTS_ROOT = COMPONENT_SOURCE_ROOTS[10] / "minions"
APP_ROOT = COMPONENT_SOURCE_ROOTS[11] / "minions"
CLI_ROOT = COMPONENT_SOURCE_ROOTS[12] / "minions"


def _run_isolated_python(
    code: str,
    *,
    env: dict[str, str],
    cwd: Path | None = None,
) -> None:
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd or REPO_ROOT,
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
    env["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in COMPONENT_SOURCE_ROOTS
    )
    env["MINIONS_WORKING_DIR"] = str(tmp_path / "working")
    env["MINIONS_SECRET_DIR"] = str(tmp_path / "secrets")
    env["MINIONS_DISABLE_KEYRING"] = "1"
    for name in (
        "MINIONS_CWD_BOOTSTRAP_PROBE",
        "MINIONS_EXPLICIT_BOOTSTRAP_PROBE",
        "MINIONS_NAMESPACE_IMPORT_PROBE",
        "MINIONS_OPENAPI_DOCS",
    ):
        env.pop(name, None)
    return env


def _reload_bootstrap_module():
    module = importlib.import_module("minions.core.bootstrap")
    return importlib.reload(module)


def test_importing_namespace_has_no_logging_or_env_side_effects(
    tmp_path: Path,
) -> None:
    env = _isolated_env(tmp_path)
    secret_dir = Path(env["MINIONS_SECRET_DIR"])
    secret_dir.mkdir(parents=True)
    env_file = secret_dir / "envs.json"
    env_file.write_text(
        json.dumps({"MINIONS_NAMESPACE_IMPORT_PROBE": "loaded"}),
        encoding="utf-8",
    )

    code = """
import logging
import os
from pathlib import Path

root = logging.getLogger()
project = logging.getLogger("minions")
before_logging = (
    root.level,
    tuple(root.handlers),
    project.level,
    tuple(project.handlers),
    project.propagate,
)
secret_dir = Path(os.environ["MINIONS_SECRET_DIR"])
before_files = tuple(sorted(path.name for path in secret_dir.iterdir()))

import minions

after_logging = (
    root.level,
    tuple(root.handlers),
    project.level,
    tuple(project.handlers),
    project.propagate,
)
after_files = tuple(sorted(path.name for path in secret_dir.iterdir()))
assert after_logging == before_logging
assert after_files == before_files
assert "MINIONS_NAMESPACE_IMPORT_PROBE" not in os.environ
"""
    _run_isolated_python(code, env=env)


def test_importing_bootstrap_does_not_import_env_backed_modules(
    tmp_path: Path,
) -> None:
    code = """
import sys
from minions.core import bootstrap

assert "minions.constant" not in sys.modules
assert "minions.envs.store" not in sys.modules
assert "minions.core.paths" not in sys.modules
assert bootstrap is not None
"""
    _run_isolated_python(code, env=_isolated_env(tmp_path))


def test_initialize_environment_loads_cwd_dotenv_before_constants(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "MINIONS_CWD_BOOTSTRAP_PROBE=from-cwd\n" "MINIONS_OPENAPI_DOCS=true\n",
        encoding="utf-8",
    )
    code = """
import os
from pathlib import Path
from minions.core.bootstrap import initialize_environment

status = initialize_environment()
from minions.constant import DOCS_ENABLED

assert status.initialized is True
assert status.persisted_env_loaded is True
assert status.env_file == (Path.cwd() / ".env").resolve()
assert status.error is None
assert os.environ["MINIONS_CWD_BOOTSTRAP_PROBE"] == "from-cwd"
assert DOCS_ENABLED is True
"""
    _run_isolated_python(
        code,
        env=_isolated_env(tmp_path),
        cwd=tmp_path,
    )


def test_initialize_environment_loads_explicit_dotenv(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / "settings" / "minions.env"
    env_file.parent.mkdir()
    env_file.write_text(
        "MINIONS_EXPLICIT_BOOTSTRAP_PROBE=explicit\n",
        encoding="utf-8",
    )
    other_cwd = tmp_path / "cwd"
    other_cwd.mkdir()
    code = f"""
import os
from pathlib import Path
from minions.core.bootstrap import initialize_environment

expected = Path({str(env_file)!r}).resolve()
status = initialize_environment(expected)
assert status.env_file == expected
assert os.environ["MINIONS_EXPLICIT_BOOTSTRAP_PROBE"] == "explicit"
"""
    _run_isolated_python(
        code,
        env=_isolated_env(tmp_path),
        cwd=other_cwd,
    )


def test_constant_has_no_repository_relative_dotenv_loading() -> None:
    source = (CORE_ROOT / "constant.py").read_text(
        encoding="utf-8",
    )
    assert "load_dotenv" not in source
    assert "_env_path" not in source


def test_persisted_env_is_loaded_before_constant_import(
    tmp_path: Path,
) -> None:
    env = _isolated_env(tmp_path)
    secret_dir = Path(env["MINIONS_SECRET_DIR"])
    secret_dir.mkdir(parents=True)
    (secret_dir / "envs.json").write_text(
        json.dumps({"MINIONS_OPENAPI_DOCS": "true"}),
        encoding="utf-8",
    )
    code = """
import os
from minions.core.bootstrap import initialize_environment

status = initialize_environment()
from minions.constant import DOCS_ENABLED

assert status.persisted_env_loaded is True
assert os.environ["MINIONS_OPENAPI_DOCS"] == "true"
assert DOCS_ENABLED is True
"""
    _run_isolated_python(code, env=env)


def test_persisted_env_failure_warns_and_returns_status(
    monkeypatch,
    caplog,
) -> None:
    bootstrap = _reload_bootstrap_module()
    calls: list[str] = []

    def load_environment_file(_path) -> None:
        calls.append("dotenv")

    monkeypatch.setattr(
        bootstrap,
        "_load_environment_file",
        load_environment_file,
    )

    def fail_persisted_env() -> None:
        calls.append("persisted")
        raise RuntimeError("persisted env unavailable")

    monkeypatch.setattr(
        bootstrap,
        "_load_persisted_environment",
        fail_persisted_env,
    )
    monkeypatch.setattr(
        bootstrap,
        "_initialize_logging",
        lambda: calls.append("logging"),
    )

    with caplog.at_level(logging.WARNING):
        status = bootstrap.initialize_environment()

    assert status.initialized is True
    assert status.persisted_env_loaded is False
    assert status.error == "persisted env unavailable"
    assert "persisted env unavailable" in caplog.text
    assert calls == ["dotenv", "persisted", "logging"]
    assert bootstrap.initialize_environment() == status
    assert calls == ["dotenv", "persisted", "logging"]


def test_initialize_environment_is_thread_safe_and_idempotent(
    monkeypatch,
) -> None:
    bootstrap = _reload_bootstrap_module()
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []
    statuses = []

    def load_environment_file(_path) -> None:
        calls.append("dotenv")

    monkeypatch.setattr(
        bootstrap,
        "_load_environment_file",
        load_environment_file,
    )

    def load_persisted() -> None:
        calls.append("persisted")
        entered.set()
        assert release.wait(timeout=5)

    monkeypatch.setattr(
        bootstrap,
        "_load_persisted_environment",
        load_persisted,
    )
    monkeypatch.setattr(
        bootstrap,
        "_initialize_logging",
        lambda: calls.append("logging"),
    )

    first = threading.Thread(
        target=lambda: statuses.append(
            bootstrap.initialize_environment(),
        ),
    )
    second = threading.Thread(
        target=lambda: statuses.append(
            bootstrap.initialize_environment(),
        ),
    )
    first.start()
    assert entered.wait(timeout=5)
    second.start()
    release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(statuses) == 2
    assert statuses[0] == statuses[1]
    assert calls == ["dotenv", "persisted", "logging"]


def test_bootstrap_uses_only_core_owned_restore_orchestration(
    tmp_path: Path,
) -> None:
    code = """
import sys
from minions.core.bootstrap import initialize_environment

initialize_environment()
assert not any(name == "minions.app" or name.startswith("minions.app.")
               for name in sys.modules)
assert not any(name == "minions.backup" or name.startswith("minions.backup.")
               for name in sys.modules)
"""
    _run_isolated_python(code, env=_isolated_env(tmp_path))


def test_cli_and_app_initialize_before_env_backed_imports() -> None:
    cli_source = (CLI_ROOT / "cli" / "main.py").read_text(
        encoding="utf-8",
    )
    app_source = (APP_ROOT / "app" / "_app.py").read_text(
        encoding="utf-8",
    )

    assert "from ..core.bootstrap import initialize_environment" in cli_source
    assert cli_source.index("initialize_environment()") < cli_source.index(
        "from ..config.utils import",
    )
    assert "from ..core.bootstrap import initialize_environment" in app_source
    assert app_source.index("initialize_environment()") < app_source.index(
        "from fastapi import FastAPI",
    )
    assert app_source.index("initialize_environment()") < app_source.index(
        "FastAPI(",
    )


def test_cli_composition_root_observes_persisted_env(tmp_path: Path) -> None:
    env = _isolated_env(tmp_path)
    secret_dir = Path(env["MINIONS_SECRET_DIR"])
    secret_dir.mkdir(parents=True)
    (secret_dir / "envs.json").write_text(
        json.dumps({"MINIONS_OPENAPI_DOCS": "true"}),
        encoding="utf-8",
    )
    code = """
import minions.cli.main
from minions.constant import DOCS_ENABLED
assert DOCS_ENABLED is True
"""
    _run_isolated_python(code, env=env)


def test_app_is_a_real_package_without_eager_app_construction(
    tmp_path: Path,
) -> None:
    code = """
import sys
import minions.app

assert minions.app.__file__ is not None
assert "minions.app._app" not in sys.modules
"""
    _run_isolated_python(code, env=_isolated_env(tmp_path))
    assert (APP_ROOT / "app" / "__init__.py").is_file()


def test_agents_owns_compatibility_shim() -> None:
    assert not any(
        (root / "minions" / "_compat").exists()
        for root in COMPONENT_SOURCE_ROOTS
    )
    assert (AGENTS_ROOT / "agents" / "_compat" / "__init__.py").is_file()
    agents_source = (AGENTS_ROOT / "agents" / "__init__.py").read_text(
        encoding="utf-8",
    )
    assert "from . import _compat" in agents_source


def test_transitional_bootstrap_modules_are_removed() -> None:
    assert not any(
        (root / "minions" / "bootstrap.py").exists()
        for root in COMPONENT_SOURCE_ROOTS
    )
    assert not any(
        (root / "minions" / "_bootstrap_paths.py").exists()
        for root in COMPONENT_SOURCE_ROOTS
    )
    assert not (APP_ROOT / "app" / "bootstrap_env.py").exists()
