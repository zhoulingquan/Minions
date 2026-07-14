-- Crash-tolerant concurrent task quota leases.
CREATE TABLE IF NOT EXISTS tenant_task_leases (
    lease_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    agent_id varchar(128) NOT NULL,
    acquired_at timestamptz NOT NULL,
    renewed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_leases_tenant_expiry
    ON tenant_task_leases (tenant_id, expires_at);

ALTER TABLE tenant_task_leases ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname=current_schema()
      AND tablename='tenant_task_leases'
      AND policyname='tenant_task_leases_tenant_isolation'
  ) THEN
    CREATE POLICY tenant_task_leases_tenant_isolation
      ON tenant_task_leases
      USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
      )
      WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
      );
  END IF;
END $$;

INSERT INTO tenancy_schema_version(version) VALUES (2)
ON CONFLICT (version) DO NOTHING;
