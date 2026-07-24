# -*- coding: utf-8 -*-
"""Build model-facing process and request environment context."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import platform
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


logger = logging.getLogger(__name__)


def build_env_context(
    session_id: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    channel: str | None = None,
    working_dir: str | None = None,
    add_hint: bool = True,
    default_shell: str | None = None,
) -> str:
    """Return model-facing request, platform, shell, and date context."""
    from minions.config import load_config

    parts: list[str] = []
    user_tz = load_config().user_timezone or "UTC"
    try:
        now = datetime.now(ZoneInfo(user_tz))
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning("Invalid timezone %r, falling back to UTC", user_tz)
        now = datetime.now(timezone.utc)
        user_tz = "UTC"

    if session_id is not None:
        parts.append(f"- Session ID: {session_id}")
    if user_id is not None:
        parts.append(f"- User ID: {user_id}")
    if user_name:
        parts.append(f"- User Name: {user_name}")
    if channel is not None:
        parts.append(f"- Channel: {channel}")
    parts.append(
        f"- OS: {platform.system()} {platform.release()} "
        f"({platform.machine()})",
    )
    if default_shell:
        parts.append(f"- Default Shell: {default_shell}")
    if working_dir is not None:
        parts.append(f"- Working directory: {working_dir}")
    parts.append(
        f"- Current date: {now.strftime('%Y-%m-%d')} "
        f"{user_tz} ({now.strftime('%A')})",
    )

    if add_hint:
        parts.append(
            "- Important:\n"
            "  1. Prefer using skills when completing tasks "
            "(e.g. use the cron skill for scheduled tasks). "
            "Consult the relevant skill documentation if unsure.\n"
            "  2. When using write_file, if you want to avoid overwriting "
            "existing content, use read_file first to inspect the file, "
            "then use edit_file for partial updates or appending.\n"
            "  3. Use tool calls to perform actions. A response without a "
            "tool call indicates the task is complete. To continue a task, "
            "you must generate a tool call or provide useful feedback if "
            "you are blocked.\n",
        )

    return (
        "====================\n" + "\n".join(parts) + "\n===================="
    )
