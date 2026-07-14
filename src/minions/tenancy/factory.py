"""Fail-closed tenancy configuration and service construction."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from ..constant import WORKING_DIR
from .models import DeploymentMode, StoreBackend


@dataclass(frozen=True, slots=True)
class TenancySettings:
    mode: DeploymentMode
    backend: StoreBackend
    sqlite_path: Path
    postgres_dsn: str = ""
    postgres_pool_min: int = 1
    postgres_pool_max: int = 10
    token_ttl_seconds: int = 7 * 24 * 3600

    @classmethod
    def from_env(cls) -> "TenancySettings":
        raw_mode = os.environ.get(
            "MINIONS_TENANCY_MODE",
            os.environ.get("MINIONS_SAGE_MODE", "development"),
        ).strip().lower()
        try:
            mode = DeploymentMode(raw_mode)
        except ValueError as exc:
            raise ValueError("invalid MINIONS_TENANCY_MODE") from exc
        raw_backend = os.environ.get("MINIONS_TENANCY_STORE", "").strip().lower()
        if not raw_backend:
            raw_backend = (
                StoreBackend.POSTGRES.value
                if mode in {DeploymentMode.TENANT, DeploymentMode.PRODUCTION}
                else StoreBackend.SQLITE.value
            )
        try:
            backend = StoreBackend(raw_backend)
        except ValueError as exc:
            raise ValueError("invalid MINIONS_TENANCY_STORE") from exc
        sqlite_path = Path(
            os.environ.get(
                "MINIONS_TENANCY_SQLITE_PATH",
                str(WORKING_DIR / "control" / "tenancy.db"),
            ),
        ).expanduser()
        ttl = _positive_int("MINIONS_TENANCY_TOKEN_TTL_SECONDS", 7 * 24 * 3600)
        settings = cls(
            mode=mode,
            backend=backend,
            sqlite_path=sqlite_path,
            postgres_dsn=os.environ.get("MINIONS_TENANCY_POSTGRES_DSN", ""),
            postgres_pool_min=_positive_int("MINIONS_TENANCY_POSTGRES_POOL_MIN", 1),
            postgres_pool_max=_positive_int("MINIONS_TENANCY_POSTGRES_POOL_MAX", 10),
            token_ttl_seconds=ttl,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        enterprise = self.mode in {DeploymentMode.TENANT, DeploymentMode.PRODUCTION}
        if enterprise and self.backend is not StoreBackend.POSTGRES:
            raise RuntimeError(
                "tenant/production mode requires PostgreSQL; SQLite fallback denied",
            )
        if self.backend is StoreBackend.POSTGRES and not self.postgres_dsn.strip():
            raise RuntimeError("MINIONS_TENANCY_POSTGRES_DSN is required")
        if self.postgres_pool_max < self.postgres_pool_min:
            raise ValueError("PostgreSQL pool max must be >= pool min")


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


_SERVICE = None
_SERVICE_KEY: tuple | None = None
_LOCK = threading.Lock()


def build_tenancy_service(settings: TenancySettings | None = None):
    """Create and initialize a tenancy service for one configured backend."""
    from .service import TenancyService

    resolved = settings or TenancySettings.from_env()
    resolved.validate()
    if resolved.backend is StoreBackend.SQLITE:
        from .sqlite_store import SQLiteTenancyStore

        store = SQLiteTenancyStore(resolved.sqlite_path)
    else:
        from .postgres_store import PostgresTenancyStore

        store = PostgresTenancyStore(
            resolved.postgres_dsn,
            min_size=resolved.postgres_pool_min,
            max_size=resolved.postgres_pool_max,
            apply_schema=resolved.mode in {
                DeploymentMode.DEVELOPMENT,
                DeploymentMode.TEST,
            },
        )
    store.initialize()
    return TenancyService(store=store, settings=resolved)


def get_tenancy_service():
    """Return a process singleton, rebuilding when test/env settings change."""
    global _SERVICE, _SERVICE_KEY  # noqa: PLW0603
    settings = TenancySettings.from_env()
    key = (
        settings.mode,
        settings.backend,
        str(settings.sqlite_path),
        settings.postgres_dsn,
        settings.postgres_pool_min,
        settings.postgres_pool_max,
        settings.token_ttl_seconds,
    )
    if _SERVICE is not None and _SERVICE_KEY == key:
        return _SERVICE
    with _LOCK:
        if _SERVICE is not None and _SERVICE_KEY == key:
            return _SERVICE
        if _SERVICE is not None:
            _SERVICE.close()
        _SERVICE = build_tenancy_service(settings)
        _SERVICE_KEY = key
        return _SERVICE


def reset_tenancy_service() -> None:
    """Close and forget the singleton (primarily for tests and reloads)."""
    global _SERVICE, _SERVICE_KEY  # noqa: PLW0603
    with _LOCK:
        if _SERVICE is not None:
            _SERVICE.close()
        _SERVICE = None
        _SERVICE_KEY = None


__all__ = [
    "TenancySettings",
    "build_tenancy_service",
    "get_tenancy_service",
    "reset_tenancy_service",
]
