"""PostgreSQL migration resources and tenant transaction contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib.resources import files

SET_LOCAL_TENANT_SQL = "SELECT set_config('sage.tenant_id', %s, true)"

RLS_TABLES = (
    "trace_event",
    "business_case",
    "knowledge_item",
    "insight",
    "playbook",
    "evidence_link",
    "growth_job",
    "audit_event",
    "capability_policy",
    "knowledge_signal",
    "consolidation_run",
    "consolidation_candidate",
)


@dataclass(frozen=True, slots=True)
class MigrationResource:
    version: int
    filename: str
    sql: str
    checksum: str


_MIGRATION_FILES = (
    (1, "0001_sage_core.sql"),
    (2, "0002_sage_governance.sql"),
    (3, "0003_sage_semantic.sql"),
)


def migration_manifest() -> tuple[MigrationResource, ...]:
    resources = files("minions.sage.migrations")
    manifest = []
    for version, filename in _MIGRATION_FILES:
        sql = resources.joinpath(filename).read_text(encoding="utf-8")
        manifest.append(
            MigrationResource(
                version=version,
                filename=filename,
                sql=sql,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            ),
        )
    return tuple(manifest)


def all_migrations_sql() -> str:
    """Return all ordered migration SQL for static verification."""

    return "\n".join(entry.sql for entry in migration_manifest())


def core_migration_sql() -> str:
    """Return the packaged SAGE core migration."""
    return (
        files("minions.sage.migrations")
        .joinpath("0001_sage_core.sql")
        .read_text(encoding="utf-8")
    )


def runtime_role_sql() -> str:
    """Return the hardened PostgreSQL runtime-role grants."""
    return (
        files("minions.sage.migrations")
        .joinpath("runtime_role.sql")
        .read_text(encoding="utf-8")
    )


def core_migration_checksum() -> str:
    """Return the release checksum expected by the runtime adapter."""
    return hashlib.sha256(core_migration_sql().encode("utf-8")).hexdigest()


async def apply_core_migration(dsn: str) -> None:
    """Apply every packaged migration with a privileged connection."""
    if not dsn.strip():
        raise ValueError("PostgreSQL migration DSN is required")
    try:
        from psycopg import AsyncConnection
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("migration requires minions[postgres]") from exc

    connection = await AsyncConnection.connect(dsn, autocommit=True)
    async with connection:
        for migration in migration_manifest():
            await connection.execute(migration.sql)
            await connection.execute(
                "INSERT INTO sage.schema_migration (version, checksum) "
                "VALUES (%s, %s) "
                "ON CONFLICT (version) DO UPDATE SET "
                "checksum=excluded.checksum, applied_at=clock_timestamp()",
                (migration.version, migration.checksum),
            )


__all__ = [
    "MigrationResource",
    "RLS_TABLES",
    "SET_LOCAL_TENANT_SQL",
    "all_migrations_sql",
    "apply_core_migration",
    "core_migration_checksum",
    "core_migration_sql",
    "migration_manifest",
    "runtime_role_sql",
]
