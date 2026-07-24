# -*- coding: utf-8 -*-
"""Channel registry: built-in + plugin-registered channels."""

from __future__ import annotations

import importlib
import logging
import threading
from typing import TYPE_CHECKING

from ..constant import EnvVarLoader
from .base import BaseChannel

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_BUILTIN_SPECS: dict[str, tuple[str, str]] = {
    "dingtalk": (".dingtalk", "DingTalkChannel"),
    "feishu": (".feishu", "FeishuChannel"),
    "qq": (".qq", "QQChannel"),
    "console": (".console", "ConsoleChannel"),
    "wecom": (".wecom", "WecomChannel"),
    "yuanbao": (".yuanbao", "YuanbaoChannel"),
    "wechat": (".wechat", "WeChatChannel"),
}

# Required channels must load; failures are raised, not skipped.
_REQUIRED_CHANNEL_KEYS: frozenset[str] = frozenset({"console"})

_BUILTIN_CHANNEL_CACHE: dict[str, type[BaseChannel]] | None = None
_BUILTIN_CHANNEL_CACHE_LOCK = threading.Lock()
_REGISTERED_CHANNELS: dict[str, type[BaseChannel]] = {}
_REGISTERED_CHANNELS_LOCK = threading.RLock()


def _load_builtin_channels() -> dict[str, type[BaseChannel]]:
    """Load built-in channels safely.

    A single optional dependency failure should not break CLI startup.
    """
    out: dict[str, type[BaseChannel]] = {}
    for key, (module_name, class_name) in _BUILTIN_SPECS.items():
        try:
            mod = importlib.import_module(module_name, package=__package__)
            cls = getattr(mod, class_name)
            if not (
                isinstance(cls, type)
                and issubclass(cls, BaseChannel)
                and cls is not BaseChannel
            ):
                raise TypeError(
                    f"{module_name}.{class_name} is not a BaseChannel subtype",
                )
        except Exception:
            if key in _REQUIRED_CHANNEL_KEYS:
                logger.error(
                    'failed to load required built-in channel "%s"',
                    key,
                    exc_info=True,
                )
                raise
            logger.debug(
                "built-in channel unavailable: %s",
                key,
                exc_info=True,
            )
            continue
        out[key] = cls
    return out


def _get_cached_builtin_channels() -> dict[str, type[BaseChannel]]:
    """Return cached built-in channels (loaded once per process)."""
    global _BUILTIN_CHANNEL_CACHE
    with _BUILTIN_CHANNEL_CACHE_LOCK:
        if _BUILTIN_CHANNEL_CACHE is None:
            _BUILTIN_CHANNEL_CACHE = _load_builtin_channels()
        return dict(_BUILTIN_CHANNEL_CACHE)


def clear_builtin_channel_cache() -> None:
    """Reset built-in channel cache. Primarily for tests."""
    global _BUILTIN_CHANNEL_CACHE
    with _BUILTIN_CHANNEL_CACHE_LOCK:
        _BUILTIN_CHANNEL_CACHE = None


BUILTIN_CHANNEL_KEYS = frozenset(_BUILTIN_SPECS.keys())


def register_channel(channel_key: str, channel_class: type[BaseChannel]) -> None:
    """Register a concrete channel class without importing its provider."""
    normalized_key = channel_key.strip().lower()
    if not normalized_key or normalized_key != channel_key:
        raise ValueError("channel_key must be normalized and non-empty")
    if normalized_key in BUILTIN_CHANNEL_KEYS:
        raise ValueError(
            f"Channel '{normalized_key}' conflicts with a built-in channel",
        )
    if not (
        isinstance(channel_class, type)
        and issubclass(channel_class, BaseChannel)
        and channel_class is not BaseChannel
    ):
        raise TypeError("channel_class must be a concrete BaseChannel subclass")
    with _REGISTERED_CHANNELS_LOCK:
        if normalized_key in _REGISTERED_CHANNELS:
            raise ValueError(f"Channel '{normalized_key}' is already registered")
        _REGISTERED_CHANNELS[normalized_key] = channel_class


def unregister_channel(channel_key: str) -> None:
    """Remove a previously registered non-built-in channel."""
    with _REGISTERED_CHANNELS_LOCK:
        _REGISTERED_CHANNELS.pop(channel_key, None)


def clear_registered_channels() -> None:
    """Clear dynamic registrations, primarily for composition/test teardown."""
    with _REGISTERED_CHANNELS_LOCK:
        _REGISTERED_CHANNELS.clear()


def get_channel_registry() -> dict[str, type[BaseChannel]]:
    """Return built-in plus explicitly registered channel classes."""
    out = _get_cached_builtin_channels()
    with _REGISTERED_CHANNELS_LOCK:
        out.update(_REGISTERED_CHANNELS)
    return out


def get_available_channels() -> tuple[str, ...]:
    """Return discovered channel keys filtered by environment settings."""
    all_keys = tuple(get_channel_registry().keys())

    raw_enabled = EnvVarLoader.get_str(
        "MINIONS_ENABLED_CHANNELS",
        "",
    ).strip()
    if raw_enabled:
        enabled = {ch.strip() for ch in raw_enabled.split(",") if ch.strip()}
        return tuple(key for key in all_keys if key in enabled) or all_keys

    raw_disabled = EnvVarLoader.get_str(
        "MINIONS_DISABLED_CHANNELS",
        "",
    ).strip()
    if raw_disabled:
        disabled = {
            ch.strip() for ch in raw_disabled.split(",") if ch.strip()
        }
        return tuple(key for key in all_keys if key not in disabled) or all_keys

    return all_keys
