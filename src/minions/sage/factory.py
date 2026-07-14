"""Fail-closed SAGE storage selection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .postgres_store import PostgresSageStore
from .sqlite_store import SQLiteSageStore
from .store import SageStore
from .embeddings import build_embedding_service_from_env


class SageDeploymentMode(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"
    TENANT = "tenant"


class SageStoreBackend(StrEnum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"


@dataclass(frozen=True, slots=True)
class SageStoreSettings:
    mode: SageDeploymentMode
    backend: SageStoreBackend
    postgres_dsn: str = ""
    postgres_pool_min: int = 1
    postgres_pool_max: int = 10

    @classmethod
    def from_env(cls) -> "SageStoreSettings":
        try:
            mode = SageDeploymentMode(
                os.environ.get("MINIONS_SAGE_MODE", "development").lower(),
            )
        except ValueError as exc:
            raise ValueError("invalid MINIONS_SAGE_MODE") from exc
        raw_backend = os.environ.get("MINIONS_SAGE_STORE", "").lower()
        if not raw_backend:
            raw_backend = (
                SageStoreBackend.POSTGRES.value
                if mode in {SageDeploymentMode.PRODUCTION, SageDeploymentMode.TENANT}
                else SageStoreBackend.SQLITE.value
            )
        try:
            backend = SageStoreBackend(raw_backend)
        except ValueError as exc:
            raise ValueError("invalid MINIONS_SAGE_STORE") from exc
        return cls(
            mode=mode,
            backend=backend,
            postgres_dsn=os.environ.get("MINIONS_SAGE_POSTGRES_DSN", ""),
            postgres_pool_min=_positive_int(
                "MINIONS_SAGE_POSTGRES_POOL_MIN",
                1,
            ),
            postgres_pool_max=_positive_int(
                "MINIONS_SAGE_POSTGRES_POOL_MAX",
                10,
            ),
        )


def build_sage_store(
    workspace_dir: str | Path,
    settings: SageStoreSettings | None = None,
) -> SageStore:
    """Build the configured store without compatibility fallback."""
    resolved = settings or SageStoreSettings.from_env()
    enterprise = resolved.mode in {
        SageDeploymentMode.PRODUCTION,
        SageDeploymentMode.TENANT,
    }
    if enterprise and resolved.backend is not SageStoreBackend.POSTGRES:
        raise RuntimeError(
            "production/tenant SAGE requires PostgreSQL; SQLite fallback denied",
        )
    if resolved.backend is SageStoreBackend.POSTGRES:
        if not resolved.postgres_dsn.strip():
            raise RuntimeError("MINIONS_SAGE_POSTGRES_DSN is required")
        return PostgresSageStore(
            resolved.postgres_dsn,
            min_size=resolved.postgres_pool_min,
            max_size=resolved.postgres_pool_max,
        )
    return SQLiteSageStore(Path(workspace_dir) / "sage" / "sage.db")


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


__all__ = [
    "SageDeploymentMode",
    "SageStoreBackend",
    "SageStoreSettings",
    "build_sage_store",
    "build_embedding_service_from_env",
]
