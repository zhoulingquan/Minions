# -*- coding: utf-8 -*-
"""Explicit application bootstrap for Minions composition roots."""
from __future__ import annotations

import logging
import os
import threading
import time


_LOG_LEVEL_ENV = "MINIONS_LOG_LEVEL"
_bootstrap_lock = threading.Lock()
_bootstrap_complete = False


def bootstrap_minions() -> None:
    """Initialize persisted env, compatibility shims, and logging once.

    Initialization is marked complete only after every step succeeds.  A
    failure is deliberately allowed to propagate so a later call may retry.
    """
    global _bootstrap_complete  # pylint: disable=global-statement

    if _bootstrap_complete:
        return

    with _bootstrap_lock:
        if _bootstrap_complete:
            return

        started_at = time.perf_counter()

        # These imports are intentionally local: importing the PEP 420
        # ``minions`` namespace must not initialize application state.
        from minions.app.bootstrap_env import load_bootstrap_env

        load_bootstrap_env()

        # Importing the compatibility package installs the legacy AgentScope
        # message shims.  Keep that initialization behind this explicit gate.
        from minions import _compat as _compat_bootstrap  # noqa: F401
        from minions.utils.logging import setup_logger

        setup_logger(os.environ.get(_LOG_LEVEL_ENV, "info"))
        logging.getLogger(__name__).debug(
            "%.3fs package init",
            time.perf_counter() - started_at,
        )
        _bootstrap_complete = True
