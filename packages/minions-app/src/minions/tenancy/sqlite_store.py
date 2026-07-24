"""Transactional SQLite development store for the tenancy control plane."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid4

from .errors import Conflict, QuotaExceeded, ResourceNotFound
from .models import (
    AgentAccess,
    AgentGrant,
    AgentStatus,
    AuthSession,
    InviteStatus,
    MembershipStatus,
    Tenant,
    TenantAuditEvent,
    TenantInvite,
    TenantMembership,
    TenantQuota,
    TenantRole,
    TenantStatus,
    TenantUsage,
    UserAccount,
    UserStatus,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenancy_schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL COLLATE NOCASE UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','suspended','archived')),
    version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    password_algorithm TEXT NOT NULL,
    password_iterations INTEGER NOT NULL CHECK(password_iterations >= 0),
    status TEXT NOT NULL CHECK(status IN ('active','disabled')),
    version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tenant_memberships (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK(role IN ('owner','admin','operator','member','viewer')),
    status TEXT NOT NULL CHECK(status IN ('active','disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_memberships_user_status
    ON tenant_memberships(user_id, status, tenant_id);
CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_identity_active
    ON auth_sessions(tenant_id, user_id, revoked_at, expires_at);
CREATE TABLE IF NOT EXISTS tenant_invites (
    invite_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    username TEXT NOT NULL COLLATE NOCASE,
    role TEXT NOT NULL CHECK(role IN ('admin','operator','member','viewer')),
    token_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('pending','accepted','revoked','expired')),
    expires_at TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL,
    accepted_by TEXT REFERENCES users(user_id) ON DELETE RESTRICT,
    accepted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_invites_tenant_status
    ON tenant_invites(tenant_id, status, expires_at);
UPDATE tenant_invites SET status='revoked'
WHERE status='pending' AND invite_id IN (
    SELECT invite_id FROM (
        SELECT invite_id,
               ROW_NUMBER() OVER (
                   PARTITION BY tenant_id, lower(username)
                   ORDER BY created_at DESC, invite_id DESC
               ) AS duplicate_rank
        FROM tenant_invites WHERE status='pending'
    ) WHERE duplicate_rank > 1
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_invite_username
    ON tenant_invites(tenant_id, username COLLATE NOCASE)
    WHERE status='pending';
CREATE TABLE IF NOT EXISTS agent_grants (
    agent_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    owner_user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    access TEXT NOT NULL CHECK(access IN ('private','tenant')),
    status TEXT NOT NULL CHECK(status IN ('active','disabled','archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_grants_tenant_status
    ON agent_grants(tenant_id, status, agent_id);
CREATE TABLE IF NOT EXISTS tenant_quotas (
    tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    max_members INTEGER NOT NULL CHECK(max_members >= 1),
    max_agents INTEGER NOT NULL CHECK(max_agents >= 1),
    max_concurrent_tasks INTEGER NOT NULL CHECK(max_concurrent_tasks >= 1),
    max_storage_mb INTEGER NOT NULL CHECK(max_storage_mb >= 1),
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tenant_usage (
    tenant_id TEXT PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    members INTEGER NOT NULL DEFAULT 0 CHECK(members >= 0),
    agents INTEGER NOT NULL DEFAULT 0 CHECK(agents >= 0),
    concurrent_tasks INTEGER NOT NULL DEFAULT 0 CHECK(concurrent_tasks >= 0),
    storage_mb INTEGER NOT NULL DEFAULT 0 CHECK(storage_mb >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK(version > 0),
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tenant_task_leases (
    lease_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    renewed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_leases_tenant_expiry
    ON tenant_task_leases(tenant_id, expires_at);
CREATE TABLE IF NOT EXISTS tenant_audit_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    actor_user_id TEXT REFERENCES users(user_id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    request_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time
    ON tenant_audit_events(tenant_id, created_at DESC, event_id DESC);
CREATE TABLE IF NOT EXISTS tenancy_migrations (
    migration_key TEXT PRIMARY KEY,
    completed_at TEXT NOT NULL,
    details_json TEXT NOT NULL
);
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteTenancyStore:
    """SQLite store with short transactions and process-local write locking."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.executescript(_SCHEMA)
                conn.execute(
                    "INSERT OR IGNORE INTO tenancy_schema_version(version, applied_at) VALUES(1, ?)",
                    (_iso(_utcnow()),),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO tenancy_schema_version(version, applied_at) VALUES(2, ?)",
                    (_iso(_utcnow()),),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO tenancy_schema_version(version, applied_at) VALUES(3, ?)",
                    (_iso(_utcnow()),),
                )
                conn.commit()
            finally:
                conn.close()

    def close(self) -> None:
        return None

    def integrity_check(self) -> str:
        with self._read() as conn:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0])

    def has_login_users(self) -> bool:
        with self._read() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE password_hash <> '' LIMIT 1",
            ).fetchone()
        return row is not None

    def ensure_local_identity(
        self,
    ) -> tuple[Tenant, UserAccount, TenantMembership]:
        now = _utcnow()
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE slug = 'local'",
            ).fetchone()
            if row is None:
                tenant_id = uuid4()
                user_id = uuid4()
                conn.execute(
                    "INSERT INTO tenants VALUES(?,?,?,?,?,?,?)",
                    (
                        str(tenant_id),
                        "local",
                        "本地开发空间",
                        TenantStatus.ACTIVE.value,
                        1,
                        _iso(now),
                        _iso(now),
                    ),
                )
                conn.execute(
                    "INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(user_id),
                        f"local-admin-{str(user_id)[:8]}",
                        "本地管理员",
                        "",
                        "",
                        "none",
                        0,
                        UserStatus.ACTIVE.value,
                        1,
                        _iso(now),
                        _iso(now),
                    ),
                )
                self._insert_membership_and_defaults(
                    conn,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=TenantRole.OWNER,
                    now=now,
                )
            else:
                tenant_id = UUID(row["tenant_id"])
                member = conn.execute(
                    """SELECT u.user_id FROM users u
                       JOIN tenant_memberships m ON m.user_id=u.user_id
                       WHERE m.tenant_id=? AND m.role='owner'
                       ORDER BY m.created_at LIMIT 1""",
                    (str(tenant_id),),
                ).fetchone()
                if member is None:
                    raise Conflict("local tenant has no owner")
                user_id = UUID(member["user_id"])
        tenant = self.get_tenant(tenant_id)
        user = self._get_user(user_id)
        membership = self._get_membership(tenant_id, user_id)
        assert tenant and user and membership
        return tenant, user, membership

    def _insert_membership_and_defaults(
        self,
        conn: sqlite3.Connection,
        *,
        tenant_id: UUID,
        user_id: UUID,
        role: TenantRole,
        now: datetime,
    ) -> None:
        conn.execute(
            "INSERT INTO tenant_memberships VALUES(?,?,?,?,?,?)",
            (
                str(tenant_id),
                str(user_id),
                role.value,
                MembershipStatus.ACTIVE.value,
                _iso(now),
                _iso(now),
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO tenant_quotas VALUES(?,?,?,?,?,?)",
            (str(tenant_id), 25, 20, 20, 10240, _iso(now)),
        )
        conn.execute(
            "INSERT OR IGNORE INTO tenant_usage VALUES(?,?,?,?,?,?,?)",
            (str(tenant_id), 1, 0, 0, 0, 1, _iso(now)),
        )

    def create_tenant_owner(
        self,
        *,
        tenant_id: UUID | None = None,
        user_id: UUID | None = None,
        slug: str,
        tenant_name: str,
        username: str,
        display_name: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
    ) -> tuple[Tenant, UserAccount, TenantMembership]:
        tenant_id, user_id, now = tenant_id or uuid4(), user_id or uuid4(), _utcnow()
        try:
            with self._transaction() as conn:
                conn.execute(
                    "INSERT INTO tenants VALUES(?,?,?,?,?,?,?)",
                    (
                        str(tenant_id),
                        slug,
                        tenant_name,
                        TenantStatus.ACTIVE.value,
                        1,
                        _iso(now),
                        _iso(now),
                    ),
                )
                conn.execute(
                    "INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(user_id),
                        username,
                        display_name,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        UserStatus.ACTIVE.value,
                        1,
                        _iso(now),
                        _iso(now),
                    ),
                )
                self._insert_membership_and_defaults(
                    conn,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=TenantRole.OWNER,
                    now=now,
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict("tenant slug or username already exists") from exc
        tenant = self.get_tenant(tenant_id)
        user = self._get_user(user_id)
        membership = self._get_membership(tenant_id, user_id)
        assert tenant and user and membership
        return tenant, user, membership

    def create_tenant_for_existing_owner(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        slug: str,
        tenant_name: str,
        now: datetime,
    ) -> tuple[Tenant, UserAccount, TenantMembership]:
        try:
            with self._transaction() as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE user_id=? AND status='active'",
                    (str(user_id),),
                ).fetchone()
                if user is None:
                    raise ResourceNotFound("user not found")
                conn.execute(
                    "INSERT INTO tenants VALUES(?,?,?,?,?,?,?)",
                    (
                        str(tenant_id),
                        slug,
                        tenant_name,
                        TenantStatus.ACTIVE.value,
                        1,
                        _iso(now),
                        _iso(now),
                    ),
                )
                self._insert_membership_and_defaults(
                    conn,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=TenantRole.OWNER,
                    now=now,
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict("tenant slug already exists") from exc
        tenant = self.get_tenant(tenant_id)
        account = self._get_user(user_id)
        membership = self._get_membership(tenant_id, user_id)
        assert tenant and account and membership
        return tenant, account, membership

    def get_user_credentials(self, username: str) -> dict[str, Any] | None:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
        return dict(row) if row else None

    def update_user_password(
        self,
        *,
        user_id: UUID,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        now: datetime,
    ) -> None:
        with self._transaction() as conn:
            cursor = conn.execute(
                """UPDATE users SET password_hash=?, password_salt=?,
                          password_algorithm=?, password_iterations=?,
                          version=version+1, updated_at=?
                   WHERE user_id=?""",
                (
                    password_hash,
                    password_salt,
                    password_algorithm,
                    password_iterations,
                    _iso(now),
                    str(user_id),
                ),
            )
            if cursor.rowcount != 1:
                raise ResourceNotFound("user not found")

    def update_user_profile(
        self,
        *,
        user_id: UUID,
        username: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        now: datetime,
    ) -> None:
        try:
            with self._transaction() as conn:
                cursor = conn.execute(
                    """UPDATE users SET username=?,password_hash=?,password_salt=?,
                              password_algorithm=?,password_iterations=?,
                              version=version+1,updated_at=? WHERE user_id=?""",
                    (
                        username,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        _iso(now),
                        str(user_id),
                    ),
                )
                if cursor.rowcount != 1:
                    raise ResourceNotFound("user not found")
        except sqlite3.IntegrityError as exc:
            raise Conflict("username already exists") from exc

    def get_first_active_owner(self) -> dict[str, Any] | None:
        with self._read() as conn:
            row = conn.execute(
                """SELECT t.tenant_id, u.user_id, u.username, m.role,
                          m.status AS membership_status
                   FROM tenant_memberships m
                   JOIN tenants t ON t.tenant_id=m.tenant_id
                   JOIN users u ON u.user_id=m.user_id
                   WHERE m.role='owner' AND m.status='active'
                     AND t.status='active' AND u.status='active'
                     AND u.password_hash<>''
                   ORDER BY m.created_at LIMIT 1""",
            ).fetchone()
        return dict(row) if row else None

    def list_active_memberships(
        self,
        user_id: UUID,
    ) -> list[tuple[Tenant, TenantMembership]]:
        with self._read() as conn:
            rows = conn.execute(
                """SELECT t.*, m.role AS membership_role,
                          m.status AS membership_status,
                          m.created_at AS membership_created_at,
                          m.updated_at AS membership_updated_at
                   FROM tenant_memberships m
                   JOIN tenants t ON t.tenant_id=m.tenant_id
                   WHERE m.user_id=? AND m.status='active' AND t.status='active'
                   ORDER BY t.created_at""",
                (str(user_id),),
            ).fetchall()
        return [
            (
                self._tenant(row),
                TenantMembership(
                    tenant_id=UUID(row["tenant_id"]),
                    user_id=user_id,
                    role=TenantRole(row["membership_role"]),
                    status=MembershipStatus(row["membership_status"]),
                    created_at=_dt(row["membership_created_at"]),
                    updated_at=_dt(row["membership_updated_at"]),
                ),
            )
            for row in rows
        ]

    def create_session(self, session: AuthSession) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO auth_sessions VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(session.session_id),
                    str(session.tenant_id),
                    str(session.user_id),
                    session.token_hash,
                    _iso(session.expires_at),
                    _iso(session.created_at),
                    _iso(session.last_seen_at),
                    None,
                ),
            )

    def resolve_session(
        self,
        token_hash: str,
        now: datetime,
        tenant_id: UUID,
    ) -> dict[str, Any] | None:
        with self._read() as conn:
            row = conn.execute(
                """SELECT s.session_id, s.tenant_id, s.user_id,
                          s.expires_at, s.revoked_at, u.username,
                          u.status AS user_status, t.status AS tenant_status,
                          m.role, m.status AS membership_status
                   FROM auth_sessions s
                   JOIN users u ON u.user_id=s.user_id
                   JOIN tenants t ON t.tenant_id=s.tenant_id
                   JOIN tenant_memberships m
                     ON m.tenant_id=s.tenant_id AND m.user_id=s.user_id
                   WHERE s.token_hash=? AND s.tenant_id=?""",
                (token_hash, str(tenant_id)),
            ).fetchone()
        if row is None or row["revoked_at"] is not None:
            return None
        if _dt(row["expires_at"]) <= now:
            return None
        if (
            row["user_status"] != UserStatus.ACTIVE.value
            or row["tenant_status"] != TenantStatus.ACTIVE.value
            or row["membership_status"] != MembershipStatus.ACTIVE.value
        ):
            return None
        return dict(row)

    def touch_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> None:
        with self._transaction() as conn:
            conn.execute(
                """UPDATE auth_sessions SET last_seen_at=?
                   WHERE session_id=? AND tenant_id=?""",
                (_iso(now), str(session_id), str(tenant_id)),
            )

    def revoke_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> bool:
        with self._transaction() as conn:
            cur = conn.execute(
                """UPDATE auth_sessions SET revoked_at=?
                   WHERE session_id=? AND tenant_id=? AND revoked_at IS NULL""",
                (_iso(now), str(session_id), str(tenant_id)),
            )
        return cur.rowcount == 1

    def revoke_user_sessions(
        self,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> int:
        with self._transaction() as conn:
            cur = conn.execute(
                """UPDATE auth_sessions SET revoked_at=?
                   WHERE tenant_id=? AND user_id=? AND revoked_at IS NULL""",
                (_iso(now), str(tenant_id), str(user_id)),
            )
        return cur.rowcount

    def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE tenant_id=?",
                (str(tenant_id),),
            ).fetchone()
        return self._tenant(row) if row else None

    def _get_user(self, user_id: UUID) -> UserAccount | None:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id=?",
                (str(user_id),),
            ).fetchone()
        return self._user(row) if row else None

    def _get_membership(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> TenantMembership | None:
        with self._read() as conn:
            row = conn.execute(
                """SELECT * FROM tenant_memberships
                   WHERE tenant_id=? AND user_id=?""",
                (str(tenant_id), str(user_id)),
            ).fetchone()
        return self._membership(row) if row else None

    def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]:
        with self._read() as conn:
            rows = conn.execute(
                """SELECT m.*, u.username, u.display_name,
                          u.status AS user_status
                   FROM tenant_memberships m JOIN users u USING(user_id)
                   WHERE m.tenant_id=? ORDER BY m.created_at""",
                (str(tenant_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_membership(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        role: TenantRole | None,
        status: MembershipStatus | None,
        now: datetime,
    ) -> TenantMembership:
        with self._transaction() as conn:
            current = conn.execute(
                "SELECT * FROM tenant_memberships WHERE tenant_id=? AND user_id=?",
                (str(tenant_id), str(user_id)),
            ).fetchone()
            if current is None:
                raise ResourceNotFound("member not found")
            next_role = role or TenantRole(current["role"])
            next_status = status or MembershipStatus(current["status"])
            if current["role"] == TenantRole.OWNER.value and (
                next_role is not TenantRole.OWNER
                or next_status is not MembershipStatus.ACTIVE
            ):
                owners = conn.execute(
                    """SELECT COUNT(*) FROM tenant_memberships
                       WHERE tenant_id=? AND role='owner' AND status='active'""",
                    (str(tenant_id),),
                ).fetchone()[0]
                if owners <= 1:
                    raise Conflict("tenant must retain an active owner")
            member_delta = 0
            if current["status"] != next_status.value:
                member_delta = 1 if next_status is MembershipStatus.ACTIVE else -1
            conn.execute(
                """UPDATE tenant_memberships
                   SET role=?, status=?, updated_at=?
                   WHERE tenant_id=? AND user_id=?""",
                (
                    next_role.value,
                    next_status.value,
                    _iso(now),
                    str(tenant_id),
                    str(user_id),
                ),
            )
            if member_delta:
                conn.execute(
                    """UPDATE tenant_usage SET members=members+?,
                       version=version+1, updated_at=? WHERE tenant_id=?""",
                    (member_delta, _iso(now), str(tenant_id)),
                )
        value = self._get_membership(tenant_id, user_id)
        assert value
        return value

    def create_invite(self, invite: TenantInvite) -> None:
        try:
            with self._transaction() as conn:
                usage, quota = conn.execute(
                    """SELECT u.members, q.max_members FROM tenant_usage u
                       JOIN tenant_quotas q USING(tenant_id) WHERE u.tenant_id=?""",
                    (str(invite.tenant_id),),
                ).fetchone()
                pending = conn.execute(
                    """SELECT COUNT(*) FROM tenant_invites
                       WHERE tenant_id=? AND status='pending' AND expires_at>?""",
                    (str(invite.tenant_id), _iso(invite.created_at)),
                ).fetchone()[0]
                if usage + pending >= quota:
                    raise QuotaExceeded("member quota exceeded")
                conn.execute(
                    "INSERT INTO tenant_invites VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(invite.invite_id),
                        str(invite.tenant_id),
                        invite.username,
                        invite.role.value,
                        invite.token_hash,
                        invite.status.value,
                        _iso(invite.expires_at),
                        str(invite.created_by),
                        _iso(invite.created_at),
                        None,
                        None,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict("invite already exists") from exc

    def list_invites(
        self,
        tenant_id: UUID,
        now: datetime,
    ) -> list[TenantInvite]:
        with self._transaction() as conn:
            conn.execute(
                """UPDATE tenant_invites SET status='expired'
                   WHERE tenant_id=? AND status='pending' AND expires_at<=?""",
                (str(tenant_id), _iso(now)),
            )
            rows = conn.execute(
                """SELECT * FROM tenant_invites WHERE tenant_id=?
                   ORDER BY created_at DESC""",
                (str(tenant_id),),
            ).fetchall()
        return [self._invite(row) for row in rows]

    def revoke_invite(
        self,
        tenant_id: UUID,
        invite_id: UUID,
        now: datetime,
    ) -> bool:
        with self._transaction() as conn:
            cursor = conn.execute(
                """UPDATE tenant_invites SET status='revoked'
                   WHERE tenant_id=? AND invite_id=? AND status='pending'
                     AND expires_at>?""",
                (str(tenant_id), str(invite_id), _iso(now)),
            )
        return cursor.rowcount == 1

    def get_pending_invite(
        self,
        *,
        token_hash: str,
        now: datetime,
    ) -> TenantInvite | None:
        with self._transaction() as conn:
            row = conn.execute(
                """SELECT * FROM tenant_invites
                   WHERE token_hash=? AND status='pending' AND expires_at>?""",
                (token_hash, _iso(now)),
            ).fetchone()
        return self._invite(row) if row is not None else None

    def accept_invite(
        self,
        *,
        token_hash: str,
        username: str,
        display_name: str,
        password_hash: str,
        password_salt: str,
        password_algorithm: str,
        password_iterations: int,
        now: datetime,
    ) -> tuple[Tenant, UserAccount, TenantMembership]:
        with self._transaction() as conn:
            invite = conn.execute(
                "SELECT * FROM tenant_invites WHERE token_hash=?",
                (token_hash,),
            ).fetchone()
            if (
                invite is None
                or invite["status"] != InviteStatus.PENDING.value
                or _dt(invite["expires_at"]) <= now
            ):
                raise ResourceNotFound("invite is invalid or expired")
            if invite["username"].casefold() != username.casefold():
                raise Conflict("invite username does not match")
            user_row = conn.execute(
                "SELECT * FROM users WHERE username=? COLLATE NOCASE",
                (username,),
            ).fetchone()
            if user_row is None:
                user_id = uuid4()
                conn.execute(
                    "INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(user_id),
                        username,
                        display_name,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        UserStatus.ACTIVE.value,
                        1,
                        _iso(now),
                        _iso(now),
                    ),
                )
            else:
                user_id = UUID(user_row["user_id"])
            tenant_id = UUID(invite["tenant_id"])
            exists = conn.execute(
                """SELECT 1 FROM tenant_memberships
                   WHERE tenant_id=? AND user_id=?""",
                (str(tenant_id), str(user_id)),
            ).fetchone()
            if exists:
                raise Conflict("user is already a tenant member")
            conn.execute(
                "INSERT INTO tenant_memberships VALUES(?,?,?,?,?,?)",
                (
                    str(tenant_id),
                    str(user_id),
                    invite["role"],
                    MembershipStatus.ACTIVE.value,
                    _iso(now),
                    _iso(now),
                ),
            )
            conn.execute(
                """UPDATE tenant_usage SET members=members+1,
                   version=version+1, updated_at=? WHERE tenant_id=?""",
                (_iso(now), str(tenant_id)),
            )
            conn.execute(
                """UPDATE tenant_invites SET status='accepted',
                   accepted_by=?, accepted_at=? WHERE invite_id=?""",
                (str(user_id), _iso(now), invite["invite_id"]),
            )
        tenant = self.get_tenant(tenant_id)
        user = self._get_user(user_id)
        membership = self._get_membership(tenant_id, user_id)
        assert tenant and user and membership
        return tenant, user, membership

    def register_agent(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        access: AgentAccess,
        now: datetime,
    ) -> AgentGrant:
        try:
            with self._transaction() as conn:
                usage, quota = conn.execute(
                    """SELECT u.agents, q.max_agents FROM tenant_usage u
                       JOIN tenant_quotas q USING(tenant_id) WHERE u.tenant_id=?""",
                    (str(tenant_id),),
                ).fetchone()
                if usage >= quota:
                    raise QuotaExceeded("agent quota exceeded")
                restored = conn.execute(
                    """UPDATE agent_grants
                       SET owner_user_id=?,access=?,status='active',updated_at=?
                       WHERE agent_id=? AND tenant_id=? AND status='archived'""",
                    (
                        str(owner_user_id),
                        access.value,
                        _iso(now),
                        agent_id,
                        str(tenant_id),
                    ),
                )
                if restored.rowcount == 0:
                    conn.execute(
                        "INSERT INTO agent_grants VALUES(?,?,?,?,?,?,?)",
                        (
                            agent_id,
                            str(tenant_id),
                            str(owner_user_id),
                            access.value,
                            AgentStatus.ACTIVE.value,
                            _iso(now),
                            _iso(now),
                        ),
                    )
                conn.execute(
                    """UPDATE tenant_usage SET agents=agents+1,
                       version=version+1, updated_at=? WHERE tenant_id=?""",
                    (_iso(now), str(tenant_id)),
                )
        except sqlite3.IntegrityError as exc:
            raise Conflict("agent already belongs to a tenant") from exc
        grant = self.get_agent_grant(agent_id)
        assert grant
        return grant

    def import_agent(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        now: datetime,
    ) -> AgentGrant:
        existing = self.get_agent_grant(agent_id)
        if existing:
            if existing.tenant_id != tenant_id:
                raise Conflict("agent is already bound to another tenant")
            return existing
        return self.register_agent(
            agent_id=agent_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            access=AgentAccess.TENANT,
            now=now,
        )

    def get_agent_grant(self, agent_id: str) -> AgentGrant | None:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM agent_grants WHERE agent_id=?",
                (agent_id,),
            ).fetchone()
        return self._agent(row) if row else None

    def get_agent_runtime_identity(self, agent_id: str) -> dict[str, Any] | None:
        with self._read() as conn:
            row = conn.execute(
                """SELECT g.agent_id, g.tenant_id, g.owner_user_id,
                          g.status AS agent_status, t.status AS tenant_status,
                          u.username, u.status AS user_status,
                          m.status AS membership_status
                   FROM agent_grants g
                   JOIN tenants t ON t.tenant_id=g.tenant_id
                   JOIN users u ON u.user_id=g.owner_user_id
                   JOIN tenant_memberships m
                     ON m.tenant_id=g.tenant_id AND m.user_id=g.owner_user_id
                   WHERE g.agent_id=?""",
                (agent_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_agent_grants(self, tenant_id: UUID) -> list[AgentGrant]:
        with self._read() as conn:
            rows = conn.execute(
                """SELECT * FROM agent_grants
                   WHERE tenant_id=? AND status<>'archived'
                   ORDER BY created_at""",
                (str(tenant_id),),
            ).fetchall()
        return [self._agent(row) for row in rows]

    def archive_agent(
        self,
        agent_id: str,
        tenant_id: UUID,
        now: datetime,
    ) -> bool:
        with self._transaction() as conn:
            cur = conn.execute(
                """UPDATE agent_grants SET status='archived', updated_at=?
                   WHERE agent_id=? AND tenant_id=? AND status<>'archived'""",
                (_iso(now), agent_id, str(tenant_id)),
            )
            if cur.rowcount:
                conn.execute(
                    """UPDATE tenant_usage SET agents=MAX(agents-1,0),
                       version=version+1, updated_at=? WHERE tenant_id=?""",
                    (_iso(now), str(tenant_id)),
                )
        return cur.rowcount == 1

    def rollback_agent_registration(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        now: datetime,
    ) -> bool:
        """Remove only a same-request reservation and restore quota usage."""
        with self._transaction() as conn:
            cursor = conn.execute(
                """DELETE FROM agent_grants
                   WHERE agent_id=? AND tenant_id=? AND owner_user_id=?
                     AND status='active'""",
                (agent_id, str(tenant_id), str(owner_user_id)),
            )
            changed = cursor.rowcount == 1
            if changed:
                conn.execute(
                    """UPDATE tenant_usage SET agents=MAX(agents-1,0),
                              version=version+1,updated_at=?
                       WHERE tenant_id=?""",
                    (_iso(now), str(tenant_id)),
                )
        return changed

    def get_quota(self, tenant_id: UUID) -> TenantQuota:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM tenant_quotas WHERE tenant_id=?",
                (str(tenant_id),),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("tenant quota not found")
        return TenantQuota(
            tenant_id=UUID(row["tenant_id"]),
            max_members=row["max_members"],
            max_agents=row["max_agents"],
            max_concurrent_tasks=row["max_concurrent_tasks"],
            max_storage_mb=row["max_storage_mb"],
            updated_at=_dt(row["updated_at"]),
        )

    def get_usage(self, tenant_id: UUID) -> TenantUsage:
        with self._read() as conn:
            row = conn.execute(
                "SELECT * FROM tenant_usage WHERE tenant_id=?",
                (str(tenant_id),),
            ).fetchone()
        if row is None:
            raise ResourceNotFound("tenant usage not found")
        return TenantUsage(
            tenant_id=UUID(row["tenant_id"]),
            members=row["members"],
            agents=row["agents"],
            concurrent_tasks=row["concurrent_tasks"],
            storage_mb=row["storage_mb"],
            version=row["version"],
            updated_at=_dt(row["updated_at"]),
        )

    def update_storage_usage(
        self,
        tenant_id: UUID,
        storage_mb: int,
        now: datetime,
    ) -> None:
        with self._transaction() as conn:
            cursor = conn.execute(
                """UPDATE tenant_usage SET storage_mb=?,version=version+1,
                          updated_at=? WHERE tenant_id=?""",
                (max(0, storage_mb), _iso(now), str(tenant_id)),
            )
            if cursor.rowcount != 1:
                raise ResourceNotFound("tenant usage not found")

    def acquire_task_lease(
        self,
        *,
        tenant_id: UUID,
        agent_id: str,
        now: datetime,
        expires_at: datetime,
    ) -> UUID:
        lease_id = uuid4()
        with self._transaction() as conn:
            conn.execute(
                "DELETE FROM tenant_task_leases WHERE tenant_id=? AND expires_at<=?",
                (str(tenant_id), _iso(now)),
            )
            active = conn.execute(
                "SELECT count(*) FROM tenant_task_leases WHERE tenant_id=?",
                (str(tenant_id),),
            ).fetchone()[0]
            quota = conn.execute(
                "SELECT max_concurrent_tasks FROM tenant_quotas WHERE tenant_id=?",
                (str(tenant_id),),
            ).fetchone()
            if quota is None:
                raise ResourceNotFound("tenant quota not found")
            if active >= quota[0]:
                raise QuotaExceeded("concurrent task quota exceeded")
            conn.execute(
                "INSERT INTO tenant_task_leases VALUES(?,?,?,?,?,?)",
                (
                    str(lease_id),
                    str(tenant_id),
                    agent_id,
                    _iso(now),
                    _iso(now),
                    _iso(expires_at),
                ),
            )
            conn.execute(
                """UPDATE tenant_usage SET concurrent_tasks=?,
                          version=version+1,updated_at=? WHERE tenant_id=?""",
                (active + 1, _iso(now), str(tenant_id)),
            )
        return lease_id

    def renew_task_lease(
        self,
        *,
        lease_id: UUID,
        tenant_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        with self._transaction() as conn:
            cursor = conn.execute(
                """UPDATE tenant_task_leases SET renewed_at=?,expires_at=?
                   WHERE lease_id=? AND tenant_id=? AND expires_at>?""",
                (
                    _iso(now),
                    _iso(expires_at),
                    str(lease_id),
                    str(tenant_id),
                    _iso(now),
                ),
            )
        return cursor.rowcount == 1

    def release_task_lease(
        self,
        *,
        lease_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> bool:
        with self._transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM tenant_task_leases WHERE lease_id=? AND tenant_id=?",
                (str(lease_id), str(tenant_id)),
            )
            active = conn.execute(
                "SELECT count(*) FROM tenant_task_leases WHERE tenant_id=? AND expires_at>?",
                (str(tenant_id), _iso(now)),
            ).fetchone()[0]
            conn.execute(
                """UPDATE tenant_usage SET concurrent_tasks=?,
                          version=version+1,updated_at=? WHERE tenant_id=?""",
                (active, _iso(now), str(tenant_id)),
            )
        return cursor.rowcount == 1

    def append_audit(self, event: TenantAuditEvent) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO tenant_audit_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    str(event.event_id),
                    str(event.tenant_id),
                    str(event.actor_user_id) if event.actor_user_id else None,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    event.outcome,
                    event.request_id,
                    json.dumps(
                        event.metadata, ensure_ascii=False, separators=(",", ":")
                    ),
                    _iso(event.created_at),
                ),
            )

    def list_audit_events(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        before: datetime | None = None,
    ) -> list[TenantAuditEvent]:
        sql = "SELECT * FROM tenant_audit_events WHERE tenant_id=?"
        params: list[Any] = [str(tenant_id)]
        if before:
            sql += " AND created_at<?"
            params.append(_iso(before))
        sql += " ORDER BY created_at DESC, event_id DESC LIMIT ?"
        params.append(min(max(limit, 1), 500))
        with self._read() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._audit(row) for row in rows]

    @staticmethod
    def _tenant(row: sqlite3.Row) -> Tenant:
        return Tenant(
            tenant_id=UUID(row["tenant_id"]),
            slug=row["slug"],
            name=row["name"],
            status=TenantStatus(row["status"]),
            version=row["version"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    @staticmethod
    def _user(row: sqlite3.Row) -> UserAccount:
        return UserAccount(
            user_id=UUID(row["user_id"]),
            username=row["username"],
            display_name=row["display_name"],
            status=UserStatus(row["status"]),
            version=row["version"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    @staticmethod
    def _membership(row: sqlite3.Row) -> TenantMembership:
        return TenantMembership(
            tenant_id=UUID(row["tenant_id"]),
            user_id=UUID(row["user_id"]),
            role=TenantRole(row["role"]),
            status=MembershipStatus(row["status"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    @staticmethod
    def _agent(row: sqlite3.Row) -> AgentGrant:
        return AgentGrant(
            agent_id=row["agent_id"],
            tenant_id=UUID(row["tenant_id"]),
            owner_user_id=UUID(row["owner_user_id"]),
            access=AgentAccess(row["access"]),
            status=AgentStatus(row["status"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    @staticmethod
    def _invite(row: sqlite3.Row) -> TenantInvite:
        return TenantInvite(
            invite_id=UUID(row["invite_id"]),
            tenant_id=UUID(row["tenant_id"]),
            username=row["username"],
            role=TenantRole(row["role"]),
            token_hash=row["token_hash"],
            status=InviteStatus(row["status"]),
            expires_at=_dt(row["expires_at"]),
            created_by=UUID(row["created_by"]),
            created_at=_dt(row["created_at"]),
            accepted_by=UUID(row["accepted_by"]) if row["accepted_by"] else None,
            accepted_at=_dt(row["accepted_at"]),
        )

    @staticmethod
    def _audit(row: sqlite3.Row) -> TenantAuditEvent:
        return TenantAuditEvent(
            event_id=UUID(row["event_id"]),
            tenant_id=UUID(row["tenant_id"]),
            actor_user_id=UUID(row["actor_user_id"]) if row["actor_user_id"] else None,
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            outcome=row["outcome"],
            request_id=row["request_id"],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=_dt(row["created_at"]),
        )


__all__ = ["SQLiteTenancyStore"]
