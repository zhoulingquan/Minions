BEGIN;

CREATE SCHEMA IF NOT EXISTS sage;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sage.schema_migration (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    checksum text NOT NULL
);

CREATE OR REPLACE FUNCTION sage.current_tenant_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('sage.tenant_id', true), '')::uuid
$$;

CREATE TABLE IF NOT EXISTS sage.trace_event (
    tenant_id uuid NOT NULL,
    trace_id uuid NOT NULL,
    event_key text NOT NULL,
    user_id uuid NOT NULL,
    agent_uid uuid NOT NULL,
    session_id text NOT NULL,
    case_id uuid,
    trace_type text NOT NULL,
    classification text NOT NULL,
    occurred_at timestamptz NOT NULL,
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, trace_id),
    UNIQUE (tenant_id, event_key)
);
CREATE INDEX IF NOT EXISTS ix_sage_trace_tenant_session
    ON sage.trace_event (tenant_id, session_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_sage_trace_tenant_case
    ON sage.trace_event (tenant_id, case_id, occurred_at);

CREATE TABLE IF NOT EXISTS sage.business_case (
    tenant_id uuid NOT NULL,
    case_id uuid NOT NULL,
    scope_type text NOT NULL,
    scope_id text NOT NULL,
    state text NOT NULL,
    classification text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, case_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_case_tenant_scope
    ON sage.business_case (tenant_id, scope_type, scope_id, state);

CREATE TABLE IF NOT EXISTS sage.knowledge_item (
    tenant_id uuid NOT NULL,
    item_id uuid NOT NULL,
    scope_type text NOT NULL,
    scope_id text NOT NULL,
    kind text NOT NULL,
    state text NOT NULL,
    classification text NOT NULL,
    title text NOT NULL,
    content text NOT NULL,
    search_document tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(content, '')), 'B')
    ) STORED,
    embedding vector,
    valid_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, item_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_item_tenant_scope
    ON sage.knowledge_item (tenant_id, scope_type, scope_id, state);
CREATE INDEX IF NOT EXISTS ix_sage_item_tenant_kind
    ON sage.knowledge_item (tenant_id, kind, state, valid_until);
CREATE INDEX IF NOT EXISTS ix_sage_item_search
    ON sage.knowledge_item USING gin (search_document);

CREATE TABLE IF NOT EXISTS sage.insight (
    tenant_id uuid NOT NULL,
    insight_id uuid NOT NULL,
    scope_type text NOT NULL,
    scope_id text NOT NULL,
    state text NOT NULL,
    classification text NOT NULL,
    fingerprint text NOT NULL DEFAULT '',
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, insight_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_insight_tenant_scope
    ON sage.insight (tenant_id, scope_type, scope_id, state);
CREATE INDEX IF NOT EXISTS ix_sage_insight_tenant_fingerprint
    ON sage.insight (tenant_id, fingerprint, state);

CREATE TABLE IF NOT EXISTS sage.playbook (
    tenant_id uuid NOT NULL,
    playbook_id uuid NOT NULL,
    scope_type text NOT NULL,
    scope_id text NOT NULL,
    state text NOT NULL,
    classification text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, playbook_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_playbook_tenant_scope
    ON sage.playbook (tenant_id, scope_type, scope_id, state);

CREATE TABLE IF NOT EXISTS sage.evidence_link (
    tenant_id uuid NOT NULL,
    link_id uuid NOT NULL,
    source_type text NOT NULL,
    source_id uuid NOT NULL,
    target_type text NOT NULL,
    target_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, link_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_evidence_tenant_target
    ON sage.evidence_link (tenant_id, target_type, target_id);

CREATE TABLE IF NOT EXISTS sage.growth_job (
    tenant_id uuid NOT NULL,
    job_id uuid NOT NULL,
    job_type text NOT NULL,
    state text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    leased_until timestamptz,
    worker_id text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, job_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_job_tenant_claim
    ON sage.growth_job (tenant_id, state, available_at, leased_until);

CREATE TABLE IF NOT EXISTS sage.audit_event (
    tenant_id uuid NOT NULL,
    audit_id uuid NOT NULL,
    actor_user_id uuid,
    actor_service_id text,
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, audit_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_audit_tenant_time
    ON sage.audit_event (tenant_id, occurred_at);

ALTER TABLE sage.trace_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.trace_event FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.trace_event;
CREATE POLICY tenant_isolation ON sage.trace_event
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.business_case ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.business_case FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.business_case;
CREATE POLICY tenant_isolation ON sage.business_case
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.knowledge_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.knowledge_item FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.knowledge_item;
CREATE POLICY tenant_isolation ON sage.knowledge_item
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.insight ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.insight FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.insight;
CREATE POLICY tenant_isolation ON sage.insight
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.playbook ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.playbook FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.playbook;
CREATE POLICY tenant_isolation ON sage.playbook
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.evidence_link ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.evidence_link FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.evidence_link;
CREATE POLICY tenant_isolation ON sage.evidence_link
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.growth_job ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.growth_job FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.growth_job;
CREATE POLICY tenant_isolation ON sage.growth_job
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

ALTER TABLE sage.audit_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.audit_event FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.audit_event;
CREATE POLICY tenant_isolation ON sage.audit_event
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

COMMIT;
