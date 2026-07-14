# ADR-0011: Multi-tenant control plane 2.1

**Status:** Accepted
**Date:** 2026-07-13

## Context

Minions historically resolved authentication from one `auth.json` account and
resolved Agents directly from global configuration. Adding `tenant_id` to a
token did not isolate Agent configuration, workspaces, channels, Cron, ACP or
SAGE. The product needs a stable SME deployment model that still runs locally
without PostgreSQL during development.

## Decision

Introduce `minions.tenancy` as the authoritative control plane for tenants,
users, memberships, sessions, Agent ownership, invites, quotas and audit.
Every entry point binds an immutable `TenantPrincipal`; resource resolution is
fail-closed. SQLite is supported for development and tests. Tenant and
production modes require PostgreSQL and may not fall back to SQLite.

Existing `config.json` remains a runtime manifest, not an authorization source.
Existing workspaces are initially bound in place; new workspaces use a tenant
directory. SAGE consumes the same principal via an explicit conversion.

Users are global identities and memberships bind them to one or more tenants.
Only a tenant owner may provision a new enterprise space. Switching spaces
issues a new session bound to the selected tenant and revokes the replaced
session; a client-provided tenant ID never changes the current authorization
scope.

## Consequences

- Cross-tenant access is denied before a Workspace is loaded.
- Member disable and tenant suspension can invalidate sessions centrally.
- Background Agent execution receives a least-privilege service principal.
- Local development remains one-command and uses an attested local owner.
- PostgreSQL deployment needs the optional driver, migrations and runtime role.
- Legacy authentication is retained only as a migration/compatibility path.

## Rejected alternatives

- Header-provided tenant IDs: forgeable and inconsistent across entry points.
- One database/process per tenant: operationally expensive for SMEs.
- SQLite in production with a fallback: weak concurrency and unsafe failure
  semantics.
- Authorization embedded in every router: easy to omit and hard to audit.
