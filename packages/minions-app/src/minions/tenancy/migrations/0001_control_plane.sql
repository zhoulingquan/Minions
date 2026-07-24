-- Minions tenancy 2.1 control plane (PostgreSQL 15+)
CREATE TABLE IF NOT EXISTS tenancy_schema_version (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id uuid PRIMARY KEY,
    slug varchar(63) NOT NULL,
    name varchar(128) NOT NULL,
    status varchar(16) NOT NULL CHECK (status IN ('active','suspended','archived')),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_tenants_slug UNIQUE (slug)
);

CREATE TABLE IF NOT EXISTS users (
    user_id uuid PRIMARY KEY,
    username varchar(128) NOT NULL,
    display_name varchar(128) NOT NULL,
    password_hash text NOT NULL,
    password_salt text NOT NULL,
    password_algorithm varchar(32) NOT NULL,
    password_iterations integer NOT NULL CHECK (password_iterations >= 0),
    status varchar(16) NOT NULL CHECK (status IN ('active','disabled')),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE TABLE IF NOT EXISTS tenant_memberships (
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    user_id uuid NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    role varchar(16) NOT NULL CHECK (role IN ('owner','admin','operator','member','viewer')),
    status varchar(16) NOT NULL CHECK (status IN ('active','disabled')),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_memberships_user_status
    ON tenant_memberships (user_id, status, tenant_id);

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash char(64) NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_sessions_identity_active
    ON auth_sessions (tenant_id, user_id, expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS tenant_invites (
    invite_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    username varchar(128) NOT NULL,
    role varchar(16) NOT NULL CHECK (role IN ('admin','operator','member','viewer')),
    token_hash char(64) NOT NULL UNIQUE,
    status varchar(16) NOT NULL CHECK (status IN ('pending','accepted','revoked','expired')),
    expires_at timestamptz NOT NULL,
    created_by uuid NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL,
    accepted_by uuid REFERENCES users(user_id) ON DELETE RESTRICT,
    accepted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_invites_tenant_status
    ON tenant_invites (tenant_id, status, expires_at);

CREATE TABLE IF NOT EXISTS agent_grants (
    agent_id varchar(128) PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    owner_user_id uuid NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    access varchar(16) NOT NULL CHECK (access IN ('private','tenant')),
    status varchar(16) NOT NULL CHECK (status IN ('active','disabled','archived')),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_grants_tenant_status
    ON agent_grants (tenant_id, status, agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_grants_owner
    ON agent_grants (tenant_id, owner_user_id);

CREATE TABLE IF NOT EXISTS tenant_quotas (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    max_members integer NOT NULL CHECK (max_members >= 1),
    max_agents integer NOT NULL CHECK (max_agents >= 1),
    max_concurrent_tasks integer NOT NULL CHECK (max_concurrent_tasks >= 1),
    max_storage_mb integer NOT NULL CHECK (max_storage_mb >= 1),
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_usage (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    members integer NOT NULL DEFAULT 0 CHECK (members >= 0),
    agents integer NOT NULL DEFAULT 0 CHECK (agents >= 0),
    concurrent_tasks integer NOT NULL DEFAULT 0 CHECK (concurrent_tasks >= 0),
    storage_mb integer NOT NULL DEFAULT 0 CHECK (storage_mb >= 0),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_audit_events (
    event_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE RESTRICT,
    actor_user_id uuid REFERENCES users(user_id) ON DELETE SET NULL,
    action varchar(128) NOT NULL,
    resource_type varchar(64) NOT NULL,
    resource_id varchar(256) NOT NULL,
    outcome varchar(32) NOT NULL,
    request_id varchar(128),
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time
    ON tenant_audit_events (tenant_id, created_at DESC, event_id DESC);

CREATE TABLE IF NOT EXISTS tenancy_migrations (
    migration_key varchar(128) PRIMARY KEY,
    completed_at timestamptz NOT NULL,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- RLS is a second boundary. The application still performs service-layer
-- authorization first. Control/migration roles may be granted BYPASSRLS;
-- the runtime role below never is.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_audit_events ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'tenants','tenant_memberships','auth_sessions','tenant_invites',
    'agent_grants','tenant_quotas','tenant_usage','tenant_audit_events'
  ] LOOP
    IF NOT EXISTS (
      SELECT 1 FROM pg_policies
      WHERE schemaname=current_schema()
        AND tablename=table_name
        AND policyname=table_name || '_tenant_isolation'
    ) THEN
      EXECUTE format(
        'CREATE POLICY %I ON %I USING (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid) WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id'', true), '''')::uuid)',
        table_name || '_tenant_isolation', table_name
      );
    END IF;
  END LOOP;
END $$;

-- Narrow SECURITY DEFINER lookups cover the few authentication/bootstrap
-- reads that necessarily start before app.tenant_id is known. They return no
-- password hashes and all generic PUBLIC execution is revoked below.
CREATE OR REPLACE FUNCTION tenancy_first_active_owner()
RETURNS TABLE(
    tenant_id uuid, user_id uuid, username varchar,
    role varchar, membership_status varchar
)
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT t.tenant_id,u.user_id,u.username,m.role,m.status
    FROM public.tenant_memberships m
    JOIN public.tenants t USING(tenant_id)
    JOIN public.users u USING(user_id)
    WHERE m.role='owner' AND m.status='active'
      AND t.status='active' AND u.status='active' AND u.password_hash<>''
    ORDER BY m.created_at LIMIT 1
$$;

CREATE OR REPLACE FUNCTION tenancy_login_memberships(p_user_id uuid)
RETURNS TABLE(
    tenant_id uuid, slug varchar, name varchar, status varchar, version bigint,
    created_at timestamptz, updated_at timestamptz,
    membership_role varchar, membership_status varchar,
    membership_created_at timestamptz, membership_updated_at timestamptz
)
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT t.tenant_id,t.slug,t.name,t.status,t.version,t.created_at,t.updated_at,
           m.role,m.status,m.created_at,m.updated_at
    FROM public.tenant_memberships m
    JOIN public.tenants t USING(tenant_id)
    WHERE m.user_id=p_user_id AND m.status='active' AND t.status='active'
    ORDER BY t.created_at
$$;

CREATE OR REPLACE FUNCTION tenancy_invite_tenant(p_token_hash text)
RETURNS uuid
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT tenant_id FROM public.tenant_invites
    WHERE token_hash=p_token_hash AND status='pending' AND expires_at>now()
    LIMIT 1
$$;

CREATE OR REPLACE FUNCTION tenancy_agent_grant(p_agent_id text)
RETURNS SETOF agent_grants
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT * FROM public.agent_grants WHERE agent_id=p_agent_id LIMIT 1
$$;

CREATE OR REPLACE FUNCTION tenancy_agent_runtime_identity(p_agent_id text)
RETURNS TABLE(
    agent_id varchar, tenant_id uuid, owner_user_id uuid,
    agent_status varchar, tenant_status varchar, username varchar,
    user_status varchar, membership_status varchar
)
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT g.agent_id,g.tenant_id,g.owner_user_id,g.status,t.status,
           u.username,u.status,m.status
    FROM public.agent_grants g
    JOIN public.tenants t USING(tenant_id)
    JOIN public.users u ON u.user_id=g.owner_user_id
    JOIN public.tenant_memberships m
      ON m.tenant_id=g.tenant_id AND m.user_id=g.owner_user_id
    WHERE g.agent_id=p_agent_id LIMIT 1
$$;

REVOKE ALL ON FUNCTION tenancy_first_active_owner() FROM PUBLIC;
REVOKE ALL ON FUNCTION tenancy_login_memberships(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION tenancy_invite_tenant(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION tenancy_agent_grant(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION tenancy_agent_runtime_identity(text) FROM PUBLIC;

INSERT INTO tenancy_schema_version(version) VALUES (1)
ON CONFLICT (version) DO NOTHING;
