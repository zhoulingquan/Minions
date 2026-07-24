# -*- coding: utf-8 -*-
"""Explicit, idempotent environment initialization for composition roots."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import threading


_LOG_LEVEL_ENV = "MINIONS_LOG_LEVEL"
_INITIALIZE_LOCK = threading.Lock()
_status: BootstrapStatus | None = None


@dataclass(frozen=True)
class BootstrapStatus:
    """Result of the process-wide environment initialization attempt."""

    initialized: bool
    persisted_env_loaded: bool
    env_file: Path | None
    error: str | None


def _load_environment_file(env_file: str | Path | None) -> Path | None:
    """Load an explicit or cwd-local dotenv without overriding process env."""
    candidate = (
        Path(env_file).expanduser()
        if env_file is not None
        else Path.cwd() / ".env"
    ).resolve()
    if not candidate.is_file():
        return None

    # Keep this import local: importing the bootstrap module itself must not
    # load environment-backed Minions modules or infer a repository root.
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=candidate, override=False)
    return candidate


def _load_persisted_environment() -> None:
    """Recover and load the persisted environment under the restore lock."""
    # All imports stay below the dotenv boundary because these modules freeze
    # the protected working/secret paths from the effective process env.
    from minions.core.paths import get_bootstrap_secret_dir
    from minions.core.restore import (
        cleanup_stale_restore_artifacts,
        restore_process_lock,
    )
    from minions.envs.store import load_envs_into_environ

    with restore_process_lock():
        cleanup_stale_restore_artifacts(get_bootstrap_secret_dir())
        load_envs_into_environ()


def _initialize_logging() -> None:
    """Configure the project logger from the now-final environment."""
    from minions.utils.logging import setup_logger

    setup_logger(os.environ.get(_LOG_LEVEL_ENV, "info"))


def _record_bootstrap_error(errors: list[str], exc: Exception) -> None:
    message = str(exc) or type(exc).__name__
    errors.append(message)
    logging.getLogger(__name__).warning(
        "Minions environment initialization could not complete a step: %s",
        message,
        exc_info=True,
    )


def initialize_environment(
    env_file: str | Path | None = None,
) -> BootstrapStatus:
    """Initialize dotenv, persisted env, and basic logging exactly once.

    Startup is deliberately best-effort. Failures are warned and represented
    in the returned immutable status so imports and CLI doctor commands remain
    usable even when persisted state cannot be recovered.
    """
    global _status  # pylint: disable=global-statement

    if _status is not None:
        return _status

    with _INITIALIZE_LOCK:
        if _status is not None:
            return _status

        errors: list[str] = []
        resolved_env_file: Path | None = None
        persisted_env_loaded = False

        try:
            resolved_env_file = _load_environment_file(env_file)
        except Exception as exc:  # bootstrap must leave doctor/import usable
            _record_bootstrap_error(errors, exc)

        try:
            _load_persisted_environment()
            persisted_env_loaded = True
        except Exception as exc:  # bootstrap must leave doctor/import usable
            _record_bootstrap_error(errors, exc)

        try:
            _initialize_logging()
        except Exception as exc:  # bootstrap must leave doctor/import usable
            _record_bootstrap_error(errors, exc)

        _status = BootstrapStatus(
            initialized=True,
            persisted_env_loaded=persisted_env_loaded,
            env_file=resolved_env_file,
            error="; ".join(errors) if errors else None,
        )
        return _status
