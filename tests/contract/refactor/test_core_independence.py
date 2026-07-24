# -*- coding: utf-8 -*-
"""Contracts keeping the minions-core ownership boundary downward-only."""
from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys
from typing import Protocol

from importlib import metadata


REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = REPO_ROOT / "packages" / "minions-core" / "src" / "minions"
APP_ROOT = REPO_ROOT / "packages" / "minions-app" / "src" / "minions"


def test_core_protocols_are_dependency_free() -> None:
    protocols = importlib.import_module("minions.core.protocols")

    for name in (
        "AgentBuilderProtocol",
        "ApprovalRequester",
        "WorkspaceProtocol",
        "ChannelProtocol",
    ):
        protocol = getattr(protocols, name)
        assert issubclass(protocol, Protocol)
        assert protocol._is_protocol is True


def test_config_construction_does_not_import_plugins_or_app() -> None:
    code = """
import sys
from minions.config import Config

Config()
for prefix in ("minions.plugins", "minions.providers", "minions.app"):
    assert not any(name == prefix or name.startswith(prefix + ".")
                   for name in sys.modules), prefix
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_config_context_has_no_agentscope_dependency() -> None:
    source = (CORE_ROOT / "config" / "context.py").read_text(
        encoding="utf-8",
    )
    assert "agentscope" not in source


def test_access_control_is_core_owned() -> None:
    security_acl = importlib.import_module("minions.security.access_control")
    assert security_acl.AccessControlStore is not None
    assert (CORE_ROOT / "security" / "access_control.py").is_file()
    assert not (APP_ROOT / "app" / "channels" / "access_control.py").exists()

    config_source = (CORE_ROOT / "config" / "config.py").read_text(
        encoding="utf-8",
    )
    assert "app.channels.access_control" not in config_source
    assert "from ..security.access_control import" in config_source


def test_agent_access_control_migration_uses_core_store(tmp_path: Path) -> None:
    config = importlib.import_module("minions.config.config")
    access_control = importlib.import_module("minions.security.access_control")
    access_control._stores.clear()
    channels = {
        "console": {
            "dm_policy": "allowlist",
            "group_policy": "disabled",
            "allow_from": ["alice"],
        },
    }

    assert config._migrate_access_control_fields(channels, tmp_path) is True
    assert channels == {
        "console": {
            "access_control_dm": True,
            "group_disabled": True,
        },
    }
    store = access_control.get_access_control_store(tmp_path)
    assert store.is_whitelisted("console", "alice") is True


def test_restore_implementation_is_core_owned() -> None:
    core_safe_swap = importlib.import_module("minions.core.restore.safe_swap")
    backup_safe_swap = importlib.import_module(
        "minions.backup._utils.safe_swap",
    )
    assert backup_safe_swap.commit_tmp is core_safe_swap.commit_tmp
    assert backup_safe_swap.restore_process_lock is (
        core_safe_swap.restore_process_lock
    )

    facade_source = (
        APP_ROOT / "backup" / "_utils" / "safe_swap.py"
    ).read_text(encoding="utf-8")
    assert "minions.core.restore.safe_swap" in facade_source
    assert "def commit_tmp" not in facade_source


def test_runtime_dependent_config_helpers_have_new_owners() -> None:
    config = importlib.import_module("minions.config.config")
    migration = importlib.import_module("minions.app.migration")
    context_windows = importlib.import_module(
        "minions.providers.context_windows",
    )

    assert not hasattr(config, "migrate_legacy_config_to_multi_agent")
    assert not hasattr(config, "get_model_max_input_length")
    assert callable(migration.migrate_legacy_config_to_multi_agent)
    assert callable(context_windows.get_model_max_input_length)


def test_config_utilities_do_not_discover_channels() -> None:
    config = importlib.import_module("minions.config")
    source = (CORE_ROOT / "config" / "utils.py").read_text(encoding="utf-8")

    assert not hasattr(config, "get_available_channels")
    assert "app.channels" not in source
    assert "def get_available_channels" not in source


def test_core_constants_do_not_discover_agent_or_app_resources() -> None:
    constant = importlib.import_module("minions.constant")
    source = (CORE_ROOT / "constant.py").read_text(encoding="utf-8")

    assert constant.SUPPORTED_AGENT_LANGUAGES == frozenset(
        {"en", "id", "ru", "zh"},
    )
    assert not hasattr(constant, "DOCS_DIR")
    assert "_discover_agent_languages" not in source
    assert "_resolve_docs_dir" not in source


def test_console_static_prefers_minions_app_distribution(
    tmp_path: Path,
    monkeypatch,
) -> None:
    console = importlib.import_module("minions.utils.console_static")
    package_root = tmp_path / "installed"
    static_dir = package_root / "minions" / "console"
    static_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("ok", encoding="utf-8")

    class _Distribution:
        @staticmethod
        def locate_file(path: str) -> Path:
            return package_root / path

    monkeypatch.delenv("MINIONS_CONSOLE_STATIC_DIR", raising=False)
    monkeypatch.setattr(
        console.metadata,
        "distribution",
        lambda name: _Distribution() if name == "minions-app" else None,
    )

    assert console.resolve_console_static_dir() == str(static_dir)


def test_console_static_is_unavailable_without_app_or_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    console = importlib.import_module("minions.utils.console_static")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MINIONS_CONSOLE_STATIC_DIR", raising=False)
    monkeypatch.setattr(
        console.metadata,
        "distribution",
        lambda _name: (_ for _ in ()).throw(
            metadata.PackageNotFoundError("minions-app"),
        ),
    )
    monkeypatch.setattr(console, "find_minions_source_repo_root", lambda: None)

    assert console.resolve_console_static_dir() == ""


def test_console_repo_detection_does_not_use_namespace_file() -> None:
    console = importlib.import_module("minions.utils.console_static")
    source = (CORE_ROOT / "utils" / "console_static.py").read_text(
        encoding="utf-8",
    )

    assert "minions.__file__" not in source
    assert console.find_minions_source_repo_root() == REPO_ROOT
