-- Run as a PostgreSQL administrator after creating the LOGIN role.
-- Replace sage_runtime with the deployment-specific runtime role if needed.
ALTER ROLE sage_runtime NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
REVOKE ALL ON SCHEMA sage FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA sage FROM PUBLIC;
GRANT USAGE ON SCHEMA sage TO sage_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA sage TO sage_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA sage
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sage_runtime;
