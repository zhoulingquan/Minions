"""PostgreSQL production store for the Minions tenancy control plane."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid4

from .errors import Conflict, QuotaExceeded, ResourceNotFound
from .models import (
    AgentAccess,
    AgentGrant,
    AuthSession,
    MembershipStatus,
    Tenant,
    TenantAuditEvent,
    TenantInvite,
    TenantMembership,
    TenantQuota,
    TenantRole,
    TenantUsage,
    UserAccount,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PostgresTenancyStore:
    """Psycopg pooled store using parameterized queries and short transactions."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        apply_schema: bool = True,
    ):
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "PostgreSQL tenancy requires: pip install 'minions[postgres]'",
            ) from exc
        self._dict_row = dict_row
        self._apply_schema = apply_schema
        self._pool = ConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    def initialize(self) -> None:
        self._pool.open(wait=True)
        if self._apply_schema:
            migration_dir = Path(__file__).parent / "migrations"
            for migration in sorted(migration_dir.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                schema = migration.read_text(encoding="utf-8")
                with self._pool.connection() as conn:
                    with conn.transaction():
                        conn.execute(schema)
            return
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT max(version) AS version FROM tenancy_schema_version",
            ).fetchone()
        if row is None or int(row["version"] or 0) < 3:
            raise RuntimeError("tenancy control-plane schema is not initialized")

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def _tx(self, tenant_id: UUID | None = None) -> Iterator[Any]:
        with self._pool.connection() as conn:
            with conn.transaction():
                if tenant_id is not None:
                    conn.execute(
                        "SELECT set_config('app.tenant_id', %s, true)",
                        (str(tenant_id),),
                    )
                yield conn

    def has_login_users(self) -> bool:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE password_hash<>'' LIMIT 1",
            ).fetchone()
        return row is not None

    def ensure_local_identity(
        self,
    ) -> tuple[Tenant, UserAccount, TenantMembership]:
        raise RuntimeError("local identity is not available in PostgreSQL mode")

    def _insert_defaults(
        self,
        conn: Any,
        tenant_id: UUID,
        user_id: UUID,
        role: TenantRole,
        now: datetime,
    ) -> None:
        conn.execute(
            """INSERT INTO tenant_memberships
               (tenant_id,user_id,role,status,created_at,updated_at)
               VALUES(%s,%s,%s,'active',%s,%s)""",
            (tenant_id, user_id, role.value, now, now),
        )
        conn.execute(
            """INSERT INTO tenant_quotas
               VALUES(%s,25,20,20,10240,%s)""",
            (tenant_id, now),
        )
        conn.execute(
            """INSERT INTO tenant_usage
               VALUES(%s,1,0,0,0,1,%s)""",
            (tenant_id, now),
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
        tenant_id, user_id, now = tenant_id or uuid4(), user_id or uuid4(), _now()
        try:
            with self._tx(tenant_id) as conn:
                conn.execute(
                    """INSERT INTO tenants VALUES
                       (%s,%s,%s,'active',1,%s,%s)""",
                    (tenant_id, slug, tenant_name, now, now),
                )
                conn.execute(
                    """INSERT INTO users VALUES
                       (%s,%s,%s,%s,%s,%s,%s,'active',1,%s,%s)""",
                    (
                        user_id,
                        username,
                        display_name,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        now,
                        now,
                    ),
                )
                self._insert_defaults(conn, tenant_id, user_id, TenantRole.OWNER, now)
        except Exception as exc:
            if getattr(exc, "sqlstate", "") == "23505":
                raise Conflict("tenant slug or username already exists") from exc
            raise
        return self._load_identity(tenant_id, user_id)

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
            with self._tx(tenant_id) as conn:
                user = conn.execute(
                    "SELECT user_id FROM users WHERE user_id=%s AND status='active'",
                    (user_id,),
                ).fetchone()
                if user is None:
                    raise ResourceNotFound("user not found")
                conn.execute(
                    """INSERT INTO tenants VALUES
                       (%s,%s,%s,'active',1,%s,%s)""",
                    (tenant_id, slug, tenant_name, now, now),
                )
                self._insert_defaults(
                    conn,
                    tenant_id,
                    user_id,
                    TenantRole.OWNER,
                    now,
                )
        except Exception as exc:
            if getattr(exc, "sqlstate", "") == "23505":
                raise Conflict("tenant slug already exists") from exc
            raise
        return self._load_identity(tenant_id, user_id)

    def _load_identity(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> tuple[Tenant, UserAccount, TenantMembership]:
        tenant = self.get_tenant(tenant_id)
        with self._tx(tenant_id) as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE user_id=%s", (user_id,)
            ).fetchone()
            member = conn.execute(
                """SELECT * FROM tenant_memberships
                   WHERE tenant_id=%s AND user_id=%s""",
                (tenant_id, user_id),
            ).fetchone()
        if tenant is None or user is None or member is None:
            raise ResourceNotFound("created identity not found")
        return tenant, self._user(user), self._membership(member)

    def get_user_credentials(self, username: str) -> dict[str, Any] | None:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE lower(username)=lower(%s)",
                (username,),
            ).fetchone()
        return row

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
        with self._tx() as conn:
            row = conn.execute(
                """UPDATE users SET password_hash=%s,password_salt=%s,
                          password_algorithm=%s,password_iterations=%s,
                          version=version+1,updated_at=%s
                   WHERE user_id=%s RETURNING user_id""",
                (
                    password_hash,
                    password_salt,
                    password_algorithm,
                    password_iterations,
                    now,
                    user_id,
                ),
            ).fetchone()
        if row is None:
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
            with self._tx() as conn:
                row = conn.execute(
                    """UPDATE users SET username=%s,password_hash=%s,
                              password_salt=%s,password_algorithm=%s,
                              password_iterations=%s,version=version+1,
                              updated_at=%s WHERE user_id=%s RETURNING user_id""",
                    (
                        username,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        now,
                        user_id,
                    ),
                ).fetchone()
        except Exception as exc:
            if getattr(exc, "sqlstate", "") == "23505":
                raise Conflict("username already exists") from exc
            raise
        if row is None:
            raise ResourceNotFound("user not found")

    def get_first_active_owner(self) -> dict[str, Any] | None:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM tenancy_first_active_owner()",
            ).fetchone()
        return row

    def list_active_memberships(
        self,
        user_id: UUID,
    ) -> list[tuple[Tenant, TenantMembership]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT * FROM tenancy_login_memberships(%s)",
                (user_id,),
            ).fetchall()
        return [
            (
                self._tenant(row),
                TenantMembership(
                    tenant_id=row["tenant_id"],
                    user_id=user_id,
                    role=TenantRole(row["membership_role"]),
                    status=MembershipStatus(row["membership_status"]),
                    created_at=row["membership_created_at"],
                    updated_at=row["membership_updated_at"],
                ),
            )
            for row in rows
        ]

    def create_session(self, session: AuthSession) -> None:
        with self._tx(session.tenant_id) as conn:
            conn.execute(
                """INSERT INTO auth_sessions VALUES
                   (%s,%s,%s,%s,%s,%s,%s,NULL)""",
                (
                    session.session_id,
                    session.tenant_id,
                    session.user_id,
                    session.token_hash,
                    session.expires_at,
                    session.created_at,
                    session.last_seen_at,
                ),
            )

    def resolve_session(
        self,
        token_hash: str,
        now: datetime,
        tenant_id: UUID,
    ) -> dict[str, Any] | None:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """SELECT s.session_id,s.tenant_id,s.user_id,s.expires_at,
                          s.revoked_at,u.username,u.status AS user_status,
                          t.status AS tenant_status,m.role,
                          m.status AS membership_status
                   FROM auth_sessions s JOIN users u USING(user_id)
                   JOIN tenants t USING(tenant_id)
                   JOIN tenant_memberships m
                     ON m.tenant_id=s.tenant_id AND m.user_id=s.user_id
                   WHERE s.token_hash=%s AND s.tenant_id=%s""",
                (token_hash, tenant_id),
            ).fetchone()
        if not row or row["revoked_at"] or row["expires_at"] <= now:
            return None
        if any(
            row[key] != "active"
            for key in (
                "user_status",
                "tenant_status",
                "membership_status",
            )
        ):
            return None
        return row

    def touch_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> None:
        with self._tx(tenant_id) as conn:
            conn.execute(
                """UPDATE auth_sessions SET last_seen_at=%s
                   WHERE session_id=%s AND tenant_id=%s""",
                (now, session_id, tenant_id),
            )

    def revoke_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> bool:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """UPDATE auth_sessions SET revoked_at=%s
                   WHERE session_id=%s AND tenant_id=%s AND revoked_at IS NULL
                   RETURNING session_id""",
                (now, session_id, tenant_id),
            ).fetchone()
        return row is not None

    def revoke_user_sessions(
        self,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> int:
        with self._tx(tenant_id) as conn:
            cur = conn.execute(
                """UPDATE auth_sessions SET revoked_at=%s
                   WHERE tenant_id=%s AND user_id=%s AND revoked_at IS NULL""",
                (now, tenant_id, user_id),
            )
        return cur.rowcount

    def get_tenant(self, tenant_id: UUID) -> Tenant | None:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()
        return self._tenant(row) if row else None

    def list_members(self, tenant_id: UUID) -> list[dict[str, Any]]:
        with self._tx(tenant_id) as conn:
            return conn.execute(
                """SELECT m.*,u.username,u.display_name,u.status AS user_status
                   FROM tenant_memberships m JOIN users u USING(user_id)
                   WHERE m.tenant_id=%s ORDER BY m.created_at""",
                (tenant_id,),
            ).fetchall()

    def update_membership(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        role: TenantRole | None,
        status: MembershipStatus | None,
        now: datetime,
    ) -> TenantMembership:
        with self._tx(tenant_id) as conn:
            current = conn.execute(
                """SELECT * FROM tenant_memberships
                   WHERE tenant_id=%s AND user_id=%s FOR UPDATE""",
                (tenant_id, user_id),
            ).fetchone()
            if not current:
                raise ResourceNotFound("member not found")
            next_role = role or TenantRole(current["role"])
            next_status = status or MembershipStatus(current["status"])
            if current["role"] == "owner" and (
                next_role is not TenantRole.OWNER
                or next_status is not MembershipStatus.ACTIVE
            ):
                owners = conn.execute(
                    """SELECT count(*) AS count FROM tenant_memberships
                       WHERE tenant_id=%s AND role='owner' AND status='active'""",
                    (tenant_id,),
                ).fetchone()["count"]
                if owners <= 1:
                    raise Conflict("tenant must retain an active owner")
            delta = 0
            if current["status"] != next_status.value:
                delta = 1 if next_status is MembershipStatus.ACTIVE else -1
            row = conn.execute(
                """UPDATE tenant_memberships SET role=%s,status=%s,updated_at=%s
                   WHERE tenant_id=%s AND user_id=%s RETURNING *""",
                (next_role.value, next_status.value, now, tenant_id, user_id),
            ).fetchone()
            if delta:
                conn.execute(
                    """UPDATE tenant_usage SET members=members+%s,
                       version=version+1,updated_at=%s WHERE tenant_id=%s""",
                    (delta, now, tenant_id),
                )
        return self._membership(row)

    def create_invite(self, invite: TenantInvite) -> None:
        try:
            with self._tx(invite.tenant_id) as conn:
                capacity = conn.execute(
                    """SELECT u.members,q.max_members FROM tenant_usage u
                       JOIN tenant_quotas q USING(tenant_id)
                       WHERE u.tenant_id=%s FOR UPDATE""",
                    (invite.tenant_id,),
                ).fetchone()
                pending = conn.execute(
                    """SELECT count(*) AS count FROM tenant_invites
                       WHERE tenant_id=%s AND status='pending' AND expires_at>%s""",
                    (invite.tenant_id, invite.created_at),
                ).fetchone()["count"]
                if capacity["members"] + pending >= capacity["max_members"]:
                    raise QuotaExceeded("member quota exceeded")
                conn.execute(
                    """INSERT INTO tenant_invites VALUES
                       (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL)""",
                    (
                        invite.invite_id,
                        invite.tenant_id,
                        invite.username,
                        invite.role.value,
                        invite.token_hash,
                        invite.status.value,
                        invite.expires_at,
                        invite.created_by,
                        invite.created_at,
                    ),
                )
        except Exception as exc:
            if getattr(exc, "sqlstate", "") == "23505":
                raise Conflict("invite already exists") from exc
            raise

    def list_invites(
        self,
        tenant_id: UUID,
        now: datetime,
    ) -> list[TenantInvite]:
        with self._tx(tenant_id) as conn:
            conn.execute(
                """UPDATE tenant_invites SET status='expired'
                   WHERE tenant_id=%s AND status='pending' AND expires_at<=%s""",
                (tenant_id, now),
            )
            rows = conn.execute(
                """SELECT * FROM tenant_invites WHERE tenant_id=%s
                   ORDER BY created_at DESC""",
                (tenant_id,),
            ).fetchall()
        return [self._invite(row) for row in rows]

    def revoke_invite(
        self,
        tenant_id: UUID,
        invite_id: UUID,
        now: datetime,
    ) -> bool:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """UPDATE tenant_invites SET status='revoked'
                   WHERE tenant_id=%s AND invite_id=%s AND status='pending'
                     AND expires_at>%s RETURNING invite_id""",
                (tenant_id, invite_id, now),
            ).fetchone()
        return row is not None

    def get_pending_invite(
        self,
        *,
        token_hash: str,
        now: datetime,
    ) -> TenantInvite | None:
        with self._tx() as conn:
            resolved = conn.execute(
                "SELECT tenancy_invite_tenant(%s) AS tenant_id",
                (token_hash,),
            ).fetchone()
        tenant_id = resolved["tenant_id"] if resolved else None
        if tenant_id is None:
            return None
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """SELECT * FROM tenant_invites
                   WHERE token_hash=%s AND status='pending' AND expires_at>%s""",
                (token_hash, now),
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
        with self._tx() as conn:
            resolved = conn.execute(
                "SELECT tenancy_invite_tenant(%s) AS tenant_id",
                (token_hash,),
            ).fetchone()
        tenant_id = resolved["tenant_id"] if resolved else None
        if tenant_id is None:
            raise ResourceNotFound("invite is invalid or expired")
        with self._tx(tenant_id) as conn:
            invite = conn.execute(
                "SELECT * FROM tenant_invites WHERE token_hash=%s FOR UPDATE",
                (token_hash,),
            ).fetchone()
            if (
                not invite
                or invite["status"] != "pending"
                or invite["expires_at"] <= now
            ):
                raise ResourceNotFound("invite is invalid or expired")
            if invite["username"].casefold() != username.casefold():
                raise Conflict("invite username does not match")
            user = conn.execute(
                "SELECT * FROM users WHERE lower(username)=lower(%s)",
                (username,),
            ).fetchone()
            if user:
                user_id = user["user_id"]
            else:
                user_id = uuid4()
                conn.execute(
                    """INSERT INTO users VALUES
                       (%s,%s,%s,%s,%s,%s,%s,'active',1,%s,%s)""",
                    (
                        user_id,
                        username,
                        display_name,
                        password_hash,
                        password_salt,
                        password_algorithm,
                        password_iterations,
                        now,
                        now,
                    ),
                )
            try:
                conn.execute(
                    """INSERT INTO tenant_memberships VALUES
                       (%s,%s,%s,'active',%s,%s)""",
                    (tenant_id, user_id, invite["role"], now, now),
                )
            except Exception as exc:
                if getattr(exc, "sqlstate", "") == "23505":
                    raise Conflict("user is already a tenant member") from exc
                raise
            conn.execute(
                """UPDATE tenant_usage SET members=members+1,
                   version=version+1,updated_at=%s WHERE tenant_id=%s""",
                (now, tenant_id),
            )
            conn.execute(
                """UPDATE tenant_invites SET status='accepted',accepted_by=%s,
                   accepted_at=%s WHERE invite_id=%s""",
                (user_id, now, invite["invite_id"]),
            )
        return self._load_identity(tenant_id, user_id)

    def register_agent(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        access: AgentAccess,
        now: datetime,
    ) -> AgentGrant:
        with self._tx(tenant_id) as conn:
            capacity = conn.execute(
                """SELECT u.agents,q.max_agents FROM tenant_usage u
                   JOIN tenant_quotas q USING(tenant_id)
                   WHERE u.tenant_id=%s FOR UPDATE""",
                (tenant_id,),
            ).fetchone()
            if capacity["agents"] >= capacity["max_agents"]:
                raise QuotaExceeded("agent quota exceeded")
            row = conn.execute(
                """UPDATE agent_grants
                   SET owner_user_id=%s,access=%s,status='active',updated_at=%s
                   WHERE agent_id=%s AND tenant_id=%s AND status='archived'
                   RETURNING *""",
                (owner_user_id, access.value, now, agent_id, tenant_id),
            ).fetchone()
            if row is None:
                try:
                    row = conn.execute(
                        """INSERT INTO agent_grants VALUES
                           (%s,%s,%s,%s,'active',%s,%s) RETURNING *""",
                        (
                            agent_id,
                            tenant_id,
                            owner_user_id,
                            access.value,
                            now,
                            now,
                        ),
                    ).fetchone()
                except Exception as exc:
                    if getattr(exc, "sqlstate", "") == "23505":
                        raise Conflict(
                            "agent already belongs to a tenant",
                        ) from exc
                    raise
            conn.execute(
                """UPDATE tenant_usage SET agents=agents+1,
                   version=version+1,updated_at=%s WHERE tenant_id=%s""",
                (now, tenant_id),
            )
        return self._agent(row)

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
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM tenancy_agent_grant(%s)",
                (agent_id,),
            ).fetchone()
        return self._agent(row) if row else None

    def get_agent_runtime_identity(self, agent_id: str) -> dict[str, Any] | None:
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM tenancy_agent_runtime_identity(%s)",
                (agent_id,),
            ).fetchone()
        return row

    def list_agent_grants(self, tenant_id: UUID) -> list[AgentGrant]:
        with self._tx(tenant_id) as conn:
            rows = conn.execute(
                """SELECT * FROM agent_grants
                   WHERE tenant_id=%s AND status<>'archived' ORDER BY created_at""",
                (tenant_id,),
            ).fetchall()
        return [self._agent(row) for row in rows]

    def archive_agent(self, agent_id: str, tenant_id: UUID, now: datetime) -> bool:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """UPDATE agent_grants SET status='archived',updated_at=%s
                   WHERE agent_id=%s AND tenant_id=%s AND status<>'archived'
                   RETURNING agent_id""",
                (now, agent_id, tenant_id),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE tenant_usage SET agents=GREATEST(agents-1,0),
                       version=version+1,updated_at=%s WHERE tenant_id=%s""",
                    (now, tenant_id),
                )
        return row is not None

    def rollback_agent_registration(
        self,
        *,
        agent_id: str,
        tenant_id: UUID,
        owner_user_id: UUID,
        now: datetime,
    ) -> bool:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """DELETE FROM agent_grants
                   WHERE agent_id=%s AND tenant_id=%s AND owner_user_id=%s
                     AND status='active' RETURNING agent_id""",
                (agent_id, tenant_id, owner_user_id),
            ).fetchone()
            if row is not None:
                conn.execute(
                    """UPDATE tenant_usage SET agents=GREATEST(agents-1,0),
                              version=version+1,updated_at=%s
                       WHERE tenant_id=%s""",
                    (now, tenant_id),
                )
        return row is not None

    def get_quota(self, tenant_id: UUID) -> TenantQuota:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                "SELECT * FROM tenant_quotas WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()
        if not row:
            raise ResourceNotFound("tenant quota not found")
        return TenantQuota(**row)

    def get_usage(self, tenant_id: UUID) -> TenantUsage:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                "SELECT * FROM tenant_usage WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()
        if not row:
            raise ResourceNotFound("tenant usage not found")
        return TenantUsage(**row)

    def update_storage_usage(
        self,
        tenant_id: UUID,
        storage_mb: int,
        now: datetime,
    ) -> None:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """UPDATE tenant_usage SET storage_mb=%s,version=version+1,
                          updated_at=%s WHERE tenant_id=%s RETURNING tenant_id""",
                (max(0, storage_mb), now, tenant_id),
            ).fetchone()
        if row is None:
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
        with self._tx(tenant_id) as conn:
            conn.execute(
                """DELETE FROM tenant_task_leases
                   WHERE tenant_id=%s AND expires_at<=%s""",
                (tenant_id, now),
            )
            capacity = conn.execute(
                """SELECT q.max_concurrent_tasks FROM tenant_usage u
                   JOIN tenant_quotas q USING(tenant_id)
                   WHERE u.tenant_id=%s FOR UPDATE OF u""",
                (tenant_id,),
            ).fetchone()
            if capacity is None:
                raise ResourceNotFound("tenant quota not found")
            active = conn.execute(
                "SELECT count(*) AS count FROM tenant_task_leases WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()["count"]
            if active >= capacity["max_concurrent_tasks"]:
                raise QuotaExceeded("concurrent task quota exceeded")
            conn.execute(
                """INSERT INTO tenant_task_leases VALUES
                   (%s,%s,%s,%s,%s,%s)""",
                (lease_id, tenant_id, agent_id, now, now, expires_at),
            )
            conn.execute(
                """UPDATE tenant_usage SET concurrent_tasks=%s,
                          version=version+1,updated_at=%s WHERE tenant_id=%s""",
                (active + 1, now, tenant_id),
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
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """UPDATE tenant_task_leases SET renewed_at=%s,expires_at=%s
                   WHERE lease_id=%s AND tenant_id=%s AND expires_at>%s
                   RETURNING lease_id""",
                (now, expires_at, lease_id, tenant_id, now),
            ).fetchone()
        return row is not None

    def release_task_lease(
        self,
        *,
        lease_id: UUID,
        tenant_id: UUID,
        now: datetime,
    ) -> bool:
        with self._tx(tenant_id) as conn:
            row = conn.execute(
                """DELETE FROM tenant_task_leases
                   WHERE lease_id=%s AND tenant_id=%s RETURNING lease_id""",
                (lease_id, tenant_id),
            ).fetchone()
            conn.execute(
                """DELETE FROM tenant_task_leases
                   WHERE tenant_id=%s AND expires_at<=%s""",
                (tenant_id, now),
            )
            active = conn.execute(
                "SELECT count(*) AS count FROM tenant_task_leases WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()["count"]
            conn.execute(
                """UPDATE tenant_usage SET concurrent_tasks=%s,
                          version=version+1,updated_at=%s WHERE tenant_id=%s""",
                (active, now, tenant_id),
            )
        return row is not None

    def append_audit(self, event: TenantAuditEvent) -> None:
        with self._tx(event.tenant_id) as conn:
            conn.execute(
                """INSERT INTO tenant_audit_events VALUES
                   (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (
                    event.event_id,
                    event.tenant_id,
                    event.actor_user_id,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    event.outcome,
                    event.request_id,
                    json.dumps(event.metadata, ensure_ascii=False, default=str),
                    event.created_at,
                ),
            )

    def list_audit_events(
        self,
        tenant_id: UUID,
        *,
        limit: int,
        before: datetime | None = None,
    ) -> list[TenantAuditEvent]:
        sql = "SELECT * FROM tenant_audit_events WHERE tenant_id=%s"
        params: list[Any] = [tenant_id]
        if before:
            sql += " AND created_at<%s"
            params.append(before)
        sql += " ORDER BY created_at DESC,event_id DESC LIMIT %s"
        params.append(min(max(limit, 1), 500))
        with self._tx(tenant_id) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._audit(row) for row in rows]

    @staticmethod
    def _tenant(row: dict[str, Any]) -> Tenant:
        return Tenant(**row)

    @staticmethod
    def _user(row: dict[str, Any]) -> UserAccount:
        public = {
            key: row[key]
            for key in (
                "user_id",
                "username",
                "display_name",
                "status",
                "version",
                "created_at",
                "updated_at",
            )
        }
        return UserAccount(**public)

    @staticmethod
    def _membership(row: dict[str, Any]) -> TenantMembership:
        return TenantMembership(**row)

    @staticmethod
    def _agent(row: dict[str, Any]) -> AgentGrant:
        return AgentGrant(**row)

    @staticmethod
    def _invite(row: dict[str, Any]) -> TenantInvite:
        return TenantInvite(**row)

    @staticmethod
    def _audit(row: dict[str, Any]) -> TenantAuditEvent:
        value = dict(row)
        value["metadata"] = value.pop("metadata_json")
        return TenantAuditEvent(**value)


__all__ = ["PostgresTenancyStore"]
