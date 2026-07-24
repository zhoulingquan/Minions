# -*- coding: utf-8 -*-
from __future__ import annotations

import secrets
from uuid import uuid4

import pytest

from minions.tenancy.errors import QuotaExceeded
from minions.tenancy.models import AgentStatus, TenantRole


def test_sqlite_wal_foreign_keys_and_integrity(tenancy_service):
    store = tenancy_service.store
    with store._read() as conn:  # pylint: disable=protected-access
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert journal.lower() == "wal"
    assert foreign_keys == 1
    assert store.integrity_check() == "ok"
    with store._read() as conn:  # pylint: disable=protected-access
        version = conn.execute(
            "SELECT MAX(version) FROM tenancy_schema_version",
        ).fetchone()[0]
    assert version == 3


def test_sqlite_upgrade_reconciles_duplicate_pending_invites(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    invite, _ = tenancy_service.invite_member(
        owner,
        username="staff",
        role=TenantRole.MEMBER,
    )
    store = tenancy_service.store
    with store._transaction() as conn:  # pylint: disable=protected-access
        conn.execute("DROP INDEX uq_pending_invite_username")
        conn.execute(
            """INSERT INTO tenant_invites
               SELECT ?,tenant_id,username,role,?,status,expires_at,created_by,
                      datetime(created_at, '+1 second'),NULL,NULL
               FROM tenant_invites WHERE invite_id=?""",
            (str(uuid4()), secrets.token_hex(32), str(invite.invite_id)),
        )

    store.initialize()
    with store._read() as conn:  # pylint: disable=protected-access
        statuses = conn.execute(
            """SELECT status,COUNT(*) AS count FROM tenant_invites
               WHERE tenant_id=? AND username='staff' GROUP BY status""",
            (str(owner.tenant_id),),
        ).fetchall()
    assert {row["status"]: row["count"] for row in statuses} == {
        "pending": 1,
        "revoked": 1,
    }


def test_agent_registration_updates_usage_atomically(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.register_agent(owner, agent_id="alpha")
    assert tenancy_service.overview(owner).usage.agents == 1
    tenancy_service.archive_agent(owner, "alpha")
    assert tenancy_service.overview(owner).usage.agents == 0


def test_archived_agent_id_can_be_registered_again(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.register_agent(owner, agent_id="reusable")
    tenancy_service.archive_agent(owner, "reusable")

    restored = tenancy_service.register_agent(owner, agent_id="reusable")

    assert restored.status is AgentStatus.ACTIVE
    assert tenancy_service.overview(owner).usage.agents == 1


def test_failed_agent_creation_can_release_reservation(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.register_agent(owner, agent_id="unfinished")

    assert tenancy_service.rollback_agent_registration(owner, "unfinished")
    assert tenancy_service.store.get_agent_grant("unfinished") is None
    assert tenancy_service.overview(owner).usage.agents == 0


def test_concurrent_task_quota_uses_recoverable_leases(tenancy_service):
    _, owner = tenancy_service.bootstrap_owner(
        username="owner",
        password="correct-horse",
        tenant_name="Acme",
        tenant_slug="acme",
    )
    tenancy_service.register_agent(owner, agent_id="worker")
    # Direct transaction access is intentional test-fixture control.
    with tenancy_service.store._transaction() as conn:
        conn.execute(
            "UPDATE tenant_quotas SET max_concurrent_tasks=1 "
            "WHERE tenant_id=?",
            (str(owner.tenant_id),),
        )

    first = tenancy_service.acquire_task_lease(owner, "worker")
    with pytest.raises(QuotaExceeded, match="concurrent task"):
        tenancy_service.acquire_task_lease(owner, "worker")
    assert tenancy_service.overview(owner).usage.concurrent_tasks == 1

    assert tenancy_service.release_task_lease(owner, first)
    second = tenancy_service.acquire_task_lease(owner, "worker")
    assert second != first
    tenancy_service.release_task_lease(owner, second)
    assert tenancy_service.overview(owner).usage.concurrent_tasks == 0
