# -*- coding: utf-8 -*-
"""Tests for safe SAGE operational commands."""

from click.testing import CliRunner

from minions.cli.main import cli
from minions.sage.postgres_schema import core_migration_checksum


def test_sage_migrate_is_dry_run_without_yes() -> None:
    result = CliRunner().invoke(cli, ["sage", "migrate"])
    assert result.exit_code == 0
    assert "dry-run" in result.output
    assert core_migration_checksum() in result.output


def test_sage_status_never_prints_dsn(monkeypatch) -> None:
    secret_dsn = "postgresql://owner:very-secret@db/minions"
    monkeypatch.setenv("MINIONS_SAGE_MODE", "production")
    monkeypatch.setenv("MINIONS_SAGE_STORE", "postgres")
    monkeypatch.setenv("MINIONS_SAGE_POSTGRES_DSN", secret_dsn)
    result = CliRunner().invoke(cli, ["sage", "status"])
    assert result.exit_code == 0
    assert "postgres_dsn: configured" in result.output
    assert secret_dsn not in result.output
    assert "very-secret" not in result.output


def test_sage_schema_sql_exposes_rls_for_review() -> None:
    result = CliRunner().invoke(cli, ["sage", "schema-sql"])
    assert result.exit_code == 0
    assert "FORCE ROW LEVEL SECURITY" in result.output
