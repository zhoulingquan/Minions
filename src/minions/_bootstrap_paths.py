# -*- coding: utf-8 -*-
"""Resolve protected bootstrap paths without importing runtime constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def _resolve_bootstrap_working_dir() -> Path:
    configured = os.environ.get("MINIONS_WORKING_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path("~/.minions").expanduser().resolve()


def _resolve_bootstrap_secret_dir(working_dir: Path) -> Path:
    configured = os.environ.get("MINIONS_SECRET_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(f"{working_dir}.secret").expanduser().resolve()


# Protected bootstrap paths are process identity.  Freeze both from the same
# environment snapshot so the env store, master key, restore lock, and cleanup
# target cannot diverge if os.environ is mutated later in the process.
_BOOTSTRAP_WORKING_DIR = _resolve_bootstrap_working_dir()
_BOOTSTRAP_SECRET_DIR = _resolve_bootstrap_secret_dir(
    _BOOTSTRAP_WORKING_DIR,
)


def get_bootstrap_working_dir() -> Path:
    """Return the frozen process working directory used during bootstrap."""
    return _BOOTSTRAP_WORKING_DIR


def get_bootstrap_secret_dir() -> Path:
    """Return the frozen process secret directory used during bootstrap."""
    return _BOOTSTRAP_SECRET_DIR
