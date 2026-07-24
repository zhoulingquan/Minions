-- Run as a database owner after replacing the sample password/secret method.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='minions_tenancy_runtime') THEN
    CREATE ROLE minions_tenancy_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOINHERIT NOBYPASSRLS;
  END IF;
END $$;

REVOKE ALL ON SCHEMA public FROM minions_tenancy_runtime;
GRANT USAGE ON SCHEMA public TO minions_tenancy_runtime;
GRANT SELECT ON tenancy_schema_version TO minions_tenancy_runtime;
GRANT SELECT, INSERT, UPDATE ON tenants, users, tenant_memberships,
  tenant_invites, agent_grants, tenant_quotas, tenant_usage,
  auth_sessions, tenant_task_leases TO minions_tenancy_runtime;
GRANT DELETE ON agent_grants, tenant_task_leases TO minions_tenancy_runtime;
GRANT SELECT, INSERT ON tenant_audit_events TO minions_tenancy_runtime;
GRANT EXECUTE ON FUNCTION tenancy_first_active_owner()
  TO minions_tenancy_runtime;
GRANT EXECUTE ON FUNCTION tenancy_login_memberships(uuid)
  TO minions_tenancy_runtime;
GRANT EXECUTE ON FUNCTION tenancy_invite_tenant(text)
  TO minions_tenancy_runtime;
GRANT EXECUTE ON FUNCTION tenancy_agent_grant(text)
  TO minions_tenancy_runtime;
GRANT EXECUTE ON FUNCTION tenancy_agent_runtime_identity(text)
  TO minions_tenancy_runtime;

ALTER ROLE minions_tenancy_runtime SET statement_timeout='30s';
ALTER ROLE minions_tenancy_runtime SET idle_in_transaction_session_timeout='15s';
ALTER ROLE minions_tenancy_runtime SET lock_timeout='5s';
