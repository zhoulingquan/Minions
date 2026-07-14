# -*- coding: utf-8 -*-
"""Resolve protected bootstrap paths without importing runtime constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def get_bootstrap_working_dir() -> Path:
    """Return the process-selected working directory used during bootstrap."""
    configured = os.environ.get("MINIONS_WORKING_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path("~/.minions").expanduser().resolve()


def get_bootstrap_secret_dir() -> Path:
    """Return the process-selected secret directory used during bootstrap."""
    configured = os.environ.get("MINIONS_SECRET_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    working_dir = get_bootstrap_working_dir()
    return Path(f"{working_dir}.secret").expanduser().resolve()
