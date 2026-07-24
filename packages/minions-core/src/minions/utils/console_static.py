# -*- coding: utf-8 -*-
"""Resolve the web console static assets directory (shared by app and CLI)."""
from __future__ import annotations

import os
from importlib import metadata
from pathlib import Path

from ..constant import EnvVarLoader

CONSOLE_STATIC_ENV = "MINIONS_CONSOLE_STATIC_DIR"


def resolve_console_static_dir() -> str:
    """Return the directory expected to contain ``index.html`` for the console.

    Resolution order is env override, the ``minions-app`` distribution,
    source checkout, then cwd fallbacks. An empty string means unavailable.
    """
    static_dir = EnvVarLoader.get_str("MINIONS_CONSOLE_STATIC_DIR")
    if static_dir:
        return static_dir

    try:
        app_distribution = metadata.distribution("minions-app")
        candidate = Path(
            app_distribution.locate_file("minions/console"),
        )
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return str(candidate)
    except (metadata.PackageNotFoundError, OSError, TypeError):
        pass

    repo_dir = find_minions_source_repo_root()
    if repo_dir is not None:
        candidate = repo_dir / "console" / "dist"
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return str(candidate)

    cwd = Path(os.getcwd())
    for subdir in ("console/dist", "console_dist"):
        candidate = cwd / subdir
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return str(candidate)

    return ""


def find_minions_source_repo_root() -> Path | None:
    """Return the git checkout root if this Python
    is running from Minions source.

    Looks upward from this module for ``console/package.json``,
    ``console/package-lock.json``, and the app component source root.
    Returns ``None`` for a normal pip/wheel install.
    """
    cur = Path(__file__).resolve().parent
    for _ in range(20):
        con = cur / "console"
        if (
            (con / "package.json").is_file()
            and (con / "package-lock.json").is_file()
            and (
                cur
                / "packages"
                / "minions-app"
                / "src"
                / "minions"
                / "app"
            ).is_dir()
        ):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None
