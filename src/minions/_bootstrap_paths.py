# -*- coding: utf-8 -*-
"""Resolve protected bootstrap paths without importing runtime constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

_initial_env = os.environ.copy()
_WORKING_DIR_SETTING = _initial_env.get("MINIONS_WORKING_DIR")
_SECRET_DIR_SETTING = _initial_env.get("MINIONS_SECRET_DIR")
_KEYRING_ACCOUNT_SETTING = _initial_env.get("MINIONS_KEYRING_ACCOUNT", "")
del _initial_env


def _resolve_bootstrap_working_dir(configured: str | None) -> Path:
    if configured:
        return Path(configured).expanduser().resolve()
    return Path("~/.minions").expanduser().resolve()


def _resolve_bootstrap_secret_dir(
    working_dir: Path,
    configured: str | None,
) -> Path:
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(f"{working_dir}.secret").expanduser().resolve()


# Protected bootstrap paths are process identity.  Freeze both from the same
# environment snapshot so the env store, master key, restore lock, and cleanup
# target cannot diverge if os.environ is mutated later in the process.
_BOOTSTRAP_WORKING_DIR = _resolve_bootstrap_working_dir(
    _WORKING_DIR_SETTING,
)
_BOOTSTRAP_SECRET_DIR = _resolve_bootstrap_secret_dir(
    _BOOTSTRAP_WORKING_DIR,
    _SECRET_DIR_SETTING,
)
_BOOTSTRAP_PATHS_RELOCATED = bool(
    _WORKING_DIR_SETTING or _SECRET_DIR_SETTING,
)
_BOOTSTRAP_KEYRING_ACCOUNT_OVERRIDE = _KEYRING_ACCOUNT_SETTING


def get_bootstrap_working_dir() -> Path:
    """Return the frozen process working directory used during bootstrap."""
    return _BOOTSTRAP_WORKING_DIR


def get_bootstrap_secret_dir() -> Path:
    """Return the frozen process secret directory used during bootstrap."""
    return _BOOTSTRAP_SECRET_DIR


def bootstrap_paths_are_relocated() -> bool:
    """Return whether the initial process env relocated bootstrap paths."""
    return _BOOTSTRAP_PATHS_RELOCATED


def get_bootstrap_keyring_account_override() -> str:
    """Return the keyring account override from the initial env snapshot."""
    return _BOOTSTRAP_KEYRING_ACCOUNT_OVERRIDE
