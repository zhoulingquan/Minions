# -*- coding: utf-8 -*-
"""Application-owned orchestration for loading persisted bootstrap env."""
from __future__ import annotations


def load_bootstrap_env() -> dict[str, str]:
    """Recover the env store, then load its bootstrap-safe values.

    Restore cleanup and env loading share the cross-process restore lock so
    startup never observes the secret directory midway through a restore.
    """
    from minions.backup._utils.safe_swap import (
        cleanup_stale_restore_artifacts,
        restore_process_lock,
    )
    from minions._bootstrap_paths import get_bootstrap_secret_dir
    from minions.envs.store import load_envs_into_environ

    with restore_process_lock():
        cleanup_stale_restore_artifacts(get_bootstrap_secret_dir())
        return load_envs_into_environ()
