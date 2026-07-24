# -*- coding: utf-8 -*-
"""Request-local identity and session context shared by lower layers."""
from __future__ import annotations

from contextvars import ContextVar, Token


_current_agent_id: ContextVar[str | None] = ContextVar(
    "current_agent_id",
    default=None,
)
_current_session_id: ContextVar[str | None] = ContextVar(
    "current_session_id",
    default=None,
)
_current_root_session_id: ContextVar[str | None] = ContextVar(
    "current_root_session_id",
    default=None,
)
_current_user_id: ContextVar[str | None] = ContextVar(
    "current_user_id",
    default=None,
)
_current_channel: ContextVar[str | None] = ContextVar(
    "current_channel",
    default=None,
)


def get_active_agent_id() -> str:
    """Return the configured active agent, falling back to ``default``."""
    try:
        from minions.config.utils import load_config

        config = load_config()
        return config.agents.active_agent or "default"
    except Exception:
        return "default"


def set_current_agent_id(agent_id: str) -> Token[str | None]:
    """Set the current agent and return a token for exact restoration."""
    return _current_agent_id.set(agent_id)


def reset_current_agent_id(token: Token[str | None]) -> None:
    """Restore the request-local agent selection represented by *token*."""
    _current_agent_id.reset(token)


def get_current_agent_id() -> str:
    """Return the request-local agent or the configured active agent."""
    return _current_agent_id.get() or get_active_agent_id()


def set_current_session_id(session_id: str) -> None:
    _current_session_id.set(session_id)


def get_current_session_id() -> str | None:
    return _current_session_id.get()


def set_current_root_session_id(root_session_id: str | None) -> None:
    _current_root_session_id.set(root_session_id)


def get_current_root_session_id() -> str | None:
    return _current_root_session_id.get()


def set_current_user_id(user_id: str | None) -> None:
    _current_user_id.set(user_id)


def get_current_user_id() -> str | None:
    return _current_user_id.get()


def set_current_channel(channel: str | None) -> None:
    _current_channel.set(channel)


def get_current_channel() -> str | None:
    return _current_channel.get()
