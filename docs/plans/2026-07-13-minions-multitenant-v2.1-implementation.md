# Minions Multi-Tenant 2.1 Implementation Plan

**Status:** Implemented and verified with the SQLite development runtime. PostgreSQL schema and fail-closed production configuration are statically verified; the live PostgreSQL deployment drill remains pending until PostgreSQL is installed.

**Goal:** Deliver a complete SQLite-development / PostgreSQL-production multi-tenant control plane and connect it to Minions authentication, Agents, workspaces, entry points, SAGE, administration UI, migration, and verification.

**Architecture:** Add a fail-closed `minions.tenancy` module as the source of truth for identity, membership, permissions, Agent ownership, quotas, sessions, invitations, and audit. Existing runtime config remains the Agent execution manifest; tenancy gates every resource resolution before the runtime is reached. SAGE consumes the same attested principal.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, sqlite3 for development, psycopg 3 for production, React/TypeScript/Zustand/Ant Design for console, pytest and Vitest.

---

### Task 1: Freeze 2.1 contracts and ADR

**Files:**
- Create: `docs/adr/0011-multitenant-control-plane-v2.1.md`
- Test: `tests/unit/tenancy/test_contracts.py`

**Acceptance:** Principal is immutable; role-permission mapping is explicit; production modes reject SQLite.

### Task 2: Build the control-plane domain

**Files:**
- Create: `src/minions/tenancy/models.py`
- Create: `src/minions/tenancy/permissions.py`
- Create: `src/minions/tenancy/context.py`
- Create: `src/minions/tenancy/store.py`
- Create: `src/minions/tenancy/service.py`
- Create: `src/minions/tenancy/factory.py`
- Create: `src/minions/tenancy/__init__.py`
- Test: `tests/unit/tenancy/test_service.py`

**Acceptance:** Tenant/user/membership/invite/session/Agent/audit/quota operations are tenant-safe and transactional.

### Task 3: Implement SQLite and PostgreSQL persistence

**Files:**
- Create: `src/minions/tenancy/sqlite_store.py`
- Create: `src/minions/tenancy/postgres_store.py`
- Create: `src/minions/tenancy/migrations/0001_control_plane.sql`
- Create: `src/minions/tenancy/migrations/runtime_role.sql`
- Modify: `pyproject.toml`
- Test: `tests/unit/tenancy/test_sqlite_store.py`
- Test: `tests/unit/tenancy/test_postgres_schema.py`

**Acceptance:** SQLite uses WAL/FK/transactions; PostgreSQL has tenant-leading indexes, RLS, runtime least privilege, and no unsafe fallback.

### Task 4: Replace online single-user authentication

**Files:**
- Modify: `src/minions/app/auth.py`
- Modify: `src/minions/app/routers/auth.py`
- Create: `src/minions/app/routers/tenancy.py`
- Modify: `src/minions/app/routers/__init__.py`
- Test: `tests/integration/test_tenancy_auth.py`

**Acceptance:** Bootstrap registration, enterprise provisioning, multi-user login, invite acceptance, in-app tenant switching, tenant selection, cross-space session revocation, member disable, and trusted principal binding work end-to-end. Legacy auth remains only as an idempotent migration source.

### Task 5: Gate Agents and workspaces

**Files:**
- Modify: `src/minions/app/agent_context.py`
- Modify: `src/minions/app/routers/agent_scoped.py`
- Modify: `src/minions/app/routers/agents.py`
- Modify: `src/minions/app/multi_agent_manager.py`
- Test: `tests/integration/test_tenant_agent_isolation.py`

**Acceptance:** List/read/create/update/delete/run are scoped; spoofed path/header cannot cross tenants; new workspaces use tenant directories.

### Task 6: Bind every runtime entry point

**Files:**
- Modify: `src/minions/app/channels/base.py`
- Modify: `src/minions/app/crons/executor.py`
- Modify: `src/minions/agents/acp/service.py`
- Create: `src/minions/tenancy/runtime.py`
- Test: `tests/integration/test_tenant_entry_points.py`

**Acceptance:** HTTP, channel, Cron, ACP and internal work all bind the same attested tenant identity and fail closed when tenant/Agent is inactive.

### Task 7: Close the SAGE growth loop

**Files:**
- Modify: `src/minions/sage/identity.py`
- Modify: `src/minions/sage/lifecycle.py`
- Modify: `src/minions/sage/foundry.py`
- Modify: `src/minions/app/routers/sage.py`
- Test: `tests/integration/test_tenant_sage_growth.py`

**Acceptance:** SAGE identity is derived from TenantPrincipal; outcomes are server-attested; case/insight review APIs complete the growth loop.

### Task 8: Add the enterprise-space console

**Files:**
- Create: `console/src/api/types/tenancy.ts`
- Create: `console/src/api/modules/tenancy.ts`
- Create: `console/src/stores/tenantStore.ts`
- Create: `console/src/pages/Settings/Tenancy/index.tsx`
- Create: `console/src/pages/Settings/Tenancy/index.module.css`
- Modify: `console/src/pages/Login/index.tsx`
- Modify: `console/src/layouts/registry/builtinRoutes.tsx`
- Modify: `console/src/layouts/registry/builtinMenu.ts`
- Modify: `console/src/api/index.ts`
- Test: `console/src/api/modules/tenancy.test.ts`

**Acceptance:** A nontechnical admin can create/switch spaces, safely copy one-time invites, see space status, members, roles, Agent ownership, enforced storage/concurrency quotas and audit; protected actions are hidden or disabled by permission.

### Task 9: Migrate legacy installations

**Files:**
- Create: `src/minions/tenancy/migration.py`
- Modify: `src/minions/app/_app.py`
- Test: `tests/integration/test_tenancy_migration.py`

**Acceptance:** Existing user and Agents migrate once without moving data; reruns are safe; partial failures do not mark completion.

### Task 10: Security, regression and operations verification

**Files:**
- Create: `docs/multitenancy-operations.md`
- Modify: `.env.example`
- Modify: `deploy/config/.env.example`
- Test: `tests/integration/test_tenancy_security.py`

**Acceptance:** Targeted backend/frontend suites pass; lint/type/build pass; SQLite integrity check passes; PostgreSQL configuration is documented and enforced; no cross-tenant negative test succeeds.

---

## Completion record

- Backend tenancy, routing, SAGE, workspace and security regression: 173 tests passed.
- Frontend tenancy API/store/page regression: 26 tests passed.
- Production console build completed successfully.
- Python formatting checks and bytecode compilation completed successfully.
- PostgreSQL migrations through schema version 3 are covered by static contract tests. A live PostgreSQL migration, rollback and recovery drill is intentionally deferred until the database is installed.
- Repository-wide TypeScript checking still reports pre-existing errors outside the multi-tenant and SAGE changes; the newly added multi-tenant paths do not introduce additional reported errors.
