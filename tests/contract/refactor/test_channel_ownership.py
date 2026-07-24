# -*- coding: utf-8 -*-
"""Contracts for the independent channel implementation distribution."""
from __future__ import annotations

import importlib
from importlib import resources
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CHANNELS_ROOT = (
    REPO_ROOT / "packages" / "minions-channels" / "src" / "minions"
)
APP_ROOT = REPO_ROOT / "packages" / "minions-app" / "src" / "minions"
AGENTS_ROOT = (
    REPO_ROOT / "packages" / "minions-agents" / "src" / "minions"
)


def test_channel_implementation_and_console_store_have_moved() -> None:
    channels_root = CHANNELS_ROOT / "channels"

    assert (channels_root / "console" / "channel.py").is_file()
    assert (channels_root / "console_push_store.py").is_file()
    assert not (APP_ROOT / "app" / "console_push_store.py").exists()


def test_app_channels_contains_only_public_facades_and_qr_handler() -> None:
    app_channels_root = APP_ROOT / "app" / "channels"
    actual = {
        path.name
        for path in app_channels_root.iterdir()
        if path.is_file() and path.suffix == ".py"
    }

    assert actual == {
        "__init__.py",
        "base.py",
        "registry.py",
        "schema.py",
        "utils.py",
        "qrcode_auth_handler.py",
    }
    assert [
        path.relative_to(app_channels_root).as_posix()
        for path in app_channels_root.rglob("*.py")
        if path.parent != app_channels_root
    ] == []


def test_app_channel_facades_reexport_real_owner() -> None:
    pairs = (
        ("base", "BaseChannel"),
        ("registry", "get_available_channels"),
        ("schema", "DEFAULT_CHANNEL"),
        ("utils", "split_text"),
    )
    for module_name, symbol in pairs:
        real = importlib.import_module(f"minions.channels.{module_name}")
        facade = importlib.import_module(
            f"minions.app.channels.{module_name}",
        )
        assert getattr(facade, symbol) is getattr(real, symbol)

    real_package = importlib.import_module("minions.channels")
    facade_package = importlib.import_module("minions.app.channels")
    assert facade_package.ChannelManager is real_package.ChannelManager


def test_headline_renderer_is_owned_by_channels() -> None:
    renderer = importlib.import_module("minions.channels.renderer")
    scroll_serialize = importlib.import_module(
        "minions.agents.context.scroll.serialize",
    )
    scroll_source = (
        AGENTS_ROOT / "agents" / "context" / "scroll" / "serialize.py"
    ).read_text(encoding="utf-8")
    app_chat_source = (
        APP_ROOT / "app" / "chats" / "utils.py"
    ).read_text(encoding="utf-8")

    assert renderer.strip_headline("answer\n<!-- ⟦ milestone ⟧ -->") == "answer"
    assert not hasattr(scroll_serialize, "strip_headline")
    assert "minions.channels" not in scroll_source
    assert "from minions.channels.renderer import strip_headline" in (
        app_chat_source
    )
    assert "minions.agents.context.scroll.serialize" not in app_chat_source


def test_channel_registry_is_low_level_and_plugin_independent() -> None:
    registry = importlib.import_module("minions.channels.registry")
    source = (CHANNELS_ROOT / "channels" / "registry.py").read_text(
        encoding="utf-8",
    )

    assert hasattr(registry, "register_channel")
    assert hasattr(registry, "unregister_channel")
    assert "minions.plugins" not in source
    assert "..plugins" not in source


def test_channel_tree_has_no_agents_app_or_plugins_dependencies() -> None:
    offenders: list[str] = []
    forbidden = (
        "from minions.agents",
        "import minions.agents",
        "from minions.app",
        "import minions.app",
        "from minions.plugins",
        "import minions.plugins",
        "from ..agents",
        "from ..app",
        "from ..plugins",
    )
    for path in (CHANNELS_ROOT / "channels").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in forbidden):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())

    assert offenders == []


def test_yuanbao_proto_resources_belong_to_channels() -> None:
    package = resources.files("minions.channels.yuanbao")

    assert package.joinpath("proto", "biz.json").is_file()
    assert package.joinpath("proto", "conn.json").is_file()


def test_qr_handler_uses_absolute_channel_client_import() -> None:
    source = (
        APP_ROOT / "app" / "channels" / "qrcode_auth_handler.py"
    ).read_text(encoding="utf-8")

    assert "minions.channels.wechat.client" in source
    assert "..channels.wechat.client" not in source
