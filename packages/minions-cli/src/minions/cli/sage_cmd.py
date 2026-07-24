"""Operational commands for the SAGE experience engine."""

from __future__ import annotations

import asyncio
import os

import click

from ..sage.factory import SageStoreSettings
from ..sage.postgres_schema import (
    apply_core_migration,
    core_migration_checksum,
    core_migration_sql,
    runtime_role_sql,
)


@click.group("sage", help="Manage the SAGE experience engine.")
def sage_group() -> None:
    """SAGE production and migration operations."""


@sage_group.command("status")
def sage_status_cmd() -> None:
    """Show deployment policy without revealing credentials."""
    try:
        settings = SageStoreSettings.from_env()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"mode: {settings.mode.value}")
    click.echo(f"store: {settings.backend.value}")
    click.echo(
        "postgres_dsn: configured"
        if settings.postgres_dsn
        else "postgres_dsn: missing",
    )
    click.echo(f"core_schema_checksum: {core_migration_checksum()}")


@sage_group.command("schema-sql")
@click.option(
    "--runtime-role",
    is_flag=True,
    help="Print hardened runtime-role grants instead of the core schema.",
)
def sage_schema_sql_cmd(runtime_role: bool) -> None:
    """Print reviewed SQL for administrator-controlled application."""
    click.echo(runtime_role_sql() if runtime_role else core_migration_sql())


@sage_group.command("migrate")
@click.option(
    "--dsn",
    envvar="MINIONS_SAGE_MIGRATION_DSN",
    help="Privileged migration DSN; prefer the environment variable.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Actually apply the migration. Without this flag, only dry-run.",
)
def sage_migrate_cmd(dsn: str | None, yes: bool) -> None:
    """Apply the versioned core schema with an explicit confirmation."""
    resolved_dsn = dsn or os.environ.get("MINIONS_SAGE_POSTGRES_DSN", "")
    click.echo("migration: 0001_sage_core")
    click.echo(f"checksum: {core_migration_checksum()}")
    if not yes:
        click.echo("dry-run: no database changes; pass --yes to apply")
        return
    if not resolved_dsn.strip():
        raise click.ClickException(
            "Set MINIONS_SAGE_MIGRATION_DSN before applying migration",
        )
    try:
        asyncio.run(apply_core_migration(resolved_dsn))
    except Exception as exc:  # Database drivers expose backend-specific errors.
        raise click.ClickException(
            f"migration failed ({type(exc).__name__}); review database logs",
        ) from exc
    click.echo("migration applied successfully")


__all__ = ["sage_group"]
