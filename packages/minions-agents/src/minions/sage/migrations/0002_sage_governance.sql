BEGIN;

CREATE TABLE IF NOT EXISTS sage.capability_policy (
    tenant_id uuid NOT NULL,
    policy_id uuid NOT NULL,
    capability text NOT NULL,
    mode text NOT NULL,
    scope_type text,
    scope_id text,
    version integer NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, policy_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_policy_tenant_capability
    ON sage.capability_policy (
        tenant_id,
        capability,
        scope_type,
        scope_id
    );

ALTER TABLE sage.capability_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.capability_policy FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.capability_policy;
CREATE POLICY tenant_isolation ON sage.capability_policy
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

CREATE TABLE IF NOT EXISTS sage.knowledge_signal (
    tenant_id uuid NOT NULL,
    signal_id uuid NOT NULL,
    source_id uuid NOT NULL,
    kind text NOT NULL,
    occurred_at timestamptz NOT NULL,
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, signal_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_signal_tenant_source
    ON sage.knowledge_signal (tenant_id, source_id, occurred_at);

ALTER TABLE sage.knowledge_signal ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.knowledge_signal FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.knowledge_signal;
CREATE POLICY tenant_isolation ON sage.knowledge_signal
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

CREATE TABLE IF NOT EXISTS sage.consolidation_run (
    tenant_id uuid NOT NULL,
    run_id uuid NOT NULL,
    local_date text NOT NULL,
    state text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, run_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_run_tenant_date
    ON sage.consolidation_run (tenant_id, local_date, state);

ALTER TABLE sage.consolidation_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.consolidation_run FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.consolidation_run;
CREATE POLICY tenant_isolation ON sage.consolidation_run
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

CREATE TABLE IF NOT EXISTS sage.consolidation_candidate (
    tenant_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    run_id uuid NOT NULL,
    kind text NOT NULL,
    state text NOT NULL,
    scope_type text NOT NULL,
    scope_id text NOT NULL,
    version integer NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    body_json jsonb NOT NULL,
    PRIMARY KEY (tenant_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS ix_sage_candidate_tenant_state
    ON sage.consolidation_candidate (tenant_id, state, kind, updated_at);

ALTER TABLE sage.consolidation_candidate ENABLE ROW LEVEL SECURITY;
ALTER TABLE sage.consolidation_candidate FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON sage.consolidation_candidate;
CREATE POLICY tenant_isolation ON sage.consolidation_candidate
    USING (tenant_id = sage.current_tenant_id())
    WITH CHECK (tenant_id = sage.current_tenant_id());

COMMIT;
