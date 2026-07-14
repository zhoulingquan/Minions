# SAGE Complete Experience System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete SAGE as a governed, multi-tenant experience system with policy-controlled activation, hybrid recall, feedback learning, nightly consolidation, management surfaces, evaluation, and production hardening.

**Architecture:** Extend the current modular monolith and durable database outbox. SQLite remains the complete development adapter and PostgreSQL remains the production adapter; no broker, cache, graph store, or external vector database is added. All derived changes pass through persisted capability policy and governance candidates before they can affect active knowledge.

**Tech Stack:** Python 3.11+, Pydantic, asyncio, SQLite/FTS5, PostgreSQL/psycopg/pgvector, FastAPI, React, TypeScript, Pytest, Vitest.

**Implementation status (2026-07-13):** Tasks 1–12 are implemented. SAGE now
includes persisted capability policies, bounded feedback learning, hybrid recall,
optional pgvector scoring, durable nightly work, governed consolidation and
rollback, a tenant-authorized API, a non-technical management center, operational
metrics, an end-to-end recovery/isolation test, and an activation runbook.

---

### Task 1: Add capability policy domain models

**Files:**
- Modify: `src/minions/sage/models.py`
- Modify: `src/minions/sage/__init__.py`
- Test: `tests/unit/sage/test_models_and_policy.py`

1. Write failing serialization/default tests for `ActivationMode`, `SageCapability`, and `CapabilityPolicy`.
2. Add deterministic tenant policy IDs, policy version, optional scope override, automatic risk ceiling, settings, modifier, and timestamps.
3. Add conservative defaults: recall AUTO, feedback/nightly SHADOW, merge/promotion APPROVAL, transfer OFF.
4. Run `pytest -q tests/unit/sage/test_models_and_policy.py`.

### Task 2: Persist policy in SQLite and PostgreSQL

**Files:**
- Modify: `src/minions/sage/store.py`
- Modify: `src/minions/sage/sqlite_store.py`
- Modify: `src/minions/sage/postgres_store.py`
- Create: `src/minions/sage/migrations/0002_sage_governance.sql`
- Modify: `src/minions/sage/postgres_schema.py`
- Test: `tests/unit/sage/test_sqlite_store.py`
- Test: `tests/unit/sage/test_postgres_schema.py`

1. Add failing tests for tenant isolation, idempotent upsert, scope overrides, and migration RLS.
2. Add `save_capability_policy`, `get_capability_policy`, and `list_capability_policies` to the store port.
3. Add the SQLite `sage_capability_policy` table and equivalent PostgreSQL migration with tenant-first primary key and RLS.
4. Update PostgreSQL migration validation to support ordered versioned migrations without changing migration 0001.
5. Run the two store test files.

### Task 3: Implement PolicyCenter and runtime gates

**Files:**
- Create: `src/minions/sage/control.py`
- Modify: `src/minions/sage/runtime.py`
- Modify: `src/minions/sage/commands.py`
- Test: `tests/unit/sage/test_control.py`
- Test: `tests/unit/sage/test_runtime.py`
- Test: `tests/unit/sage/test_commands.py`

1. Test default resolution, scope override precedence, permission-protected updates, and mode decisions.
2. Implement `PolicyCenter.resolve`, `set_policy`, and `decision` with fail-closed risk checks.
3. Attach PolicyCenter to SageRuntime and add `/sage-policy` read output; mutations remain service/API operations requiring `sage.policy.manage`.
4. Verify existing recall and reflection behavior remains compatible.

### Task 4: Add feedback signals and bounded utility learning

**Files:**
- Modify: `src/minions/sage/models.py`
- Modify: `src/minions/sage/store.py`
- Modify: both store adapters and PostgreSQL migration 0002
- Create: `src/minions/sage/evaluation.py`
- Modify: `src/minions/sage/runtime.py`
- Test: `tests/unit/sage/test_evaluation.py`

1. Add `KnowledgeSignal` and aggregated source quality models.
2. Persist idempotent signals derived from feedback and verified outcomes.
3. Implement bounded utility calculation with minimum evidence and anti-abuse caps.
4. In SHADOW mode write proposed utility only; in AUTO mode update low-risk items through a new catalog version.

### Task 5: Implement entity, temporal, and feedback-aware hybrid recall

**Files:**
- Modify: `src/minions/sage/models.py`
- Modify: `src/minions/sage/store.py`
- Modify: both store adapters
- Modify: `src/minions/sage/recall.py`
- Test: `tests/unit/sage/test_recall.py`

1. Add a structured `RecallQuery` containing text, entities, domain/process/task and as-of time.
2. Generate authorized lexical candidates before ranking.
3. Add entity overlap, applicability, freshness, validity, utility and feedback score components.
4. Record every component in RecallReceipt and support old-vs-new shadow ranking.
5. Preserve section budgets and deterministic tie-breaking.

### Task 6: Add optional PostgreSQL semantic scoring

**Files:**
- Create: `src/minions/sage/embeddings.py`
- Modify: `src/minions/sage/postgres_store.py`
- Modify: `src/minions/sage/recall.py`
- Test: `tests/unit/sage/test_embeddings.py`
- Test: `tests/unit/sage/test_postgres_schema.py`

1. Define an optional embedding provider protocol with explicit dimensions and timeout.
2. Store/query pgvector embeddings only after RLS candidate restriction.
3. Degrade to lexical/entity/temporal recall when no provider or on timeout.
4. Expose degradation reasons in the receipt without failing the request.

### Task 7: Add consolidation runs and candidates

**Files:**
- Modify: `src/minions/sage/models.py`
- Modify: `src/minions/sage/store.py`
- Modify: both adapters and migration 0002
- Create: `src/minions/sage/consolidation.py`
- Test: `tests/unit/sage/test_consolidation.py`

1. Model `ConsolidationRun` and `ConsolidationCandidate` state machines.
2. Detect exact duplicates, likely conflicts, expired content, low-utility content, and playbook promotion opportunities.
3. Store source IDs, score evidence, before snapshots, risk and proposed action.
4. Make tenant/date runs idempotent and safe to resume.

### Task 8: Build SAGE Nightly on the durable outbox

**Files:**
- Modify: `src/minions/sage/models.py`
- Create: `src/minions/sage/maintenance.py`
- Modify: `src/minions/sage/runtime.py`
- Modify: `src/minions/sage/factory.py`
- Test: `tests/unit/sage/test_maintenance.py`
- Test: `tests/unit/sage/test_runtime.py`

1. Add growth job types for tenant consolidation, utility recalculation, and shadow evaluation.
2. Persist one deterministic job per tenant/local date and support catch-up after downtime.
3. Add a lightweight in-process coordinator for known tenant principals; keep actual work in the outbox.
4. Enforce one active consolidation lease per tenant and configurable work/time budgets.

### Task 9: Apply, approve, reject, and roll back candidates

**Files:**
- Modify: `src/minions/sage/consolidation.py`
- Modify: `src/minions/sage/catalog.py`
- Modify: `src/minions/sage/growth.py`
- Test: `tests/unit/sage/test_consolidation.py`
- Test: `tests/unit/sage/test_growth.py`

1. Implement optimistic version checks and permission-protected review.
2. Allow AUTO only for operations below the policy risk ceiling.
3. Always require approval for deletion, shared-scope mutation, high risk, and playbook publication.
4. Persist audit traces and reversible before/after references.

### Task 10: Add management API

**Files:**
- Create: `src/minions/app/routers/sage.py`
- Modify: `src/minions/app/_app.py`
- Test: `tests/unit/app/routers/test_sage_router.py`

1. Add tenant-authorized endpoints for overview, policies, items, receipts, signals, jobs, runs, candidates and evaluation snapshots.
2. Add approve/reject/rollback operations with explicit permissions.
3. Paginate all list endpoints and redact content by classification.
4. Test forged tenant IDs, missing identity and cross-scope access.

### Task 11: Add the non-technical SAGE management center

**Files:**
- Create: `console/src/api/modules/sage.ts`
- Create: `console/src/api/types/sage.ts`
- Create: `console/src/pages/Settings/Sage/**`
- Modify: `console/src/layouts/registry/builtinRoutes.tsx`
- Modify: `console/src/layouts/registry/builtinMenu.ts`
- Test: `console/src/pages/Settings/Sage/SagePage.test.tsx`

1. Build overview cards for knowledge health, recent growth and pending decisions.
2. Add plain-language policy controls for closed/shadow/approval/automatic modes.
3. Add candidate review, conflict comparison, receipt explanation, job history and rollback flows.
4. Verify loading, empty, error, permission-denied and success states visually and with Vitest.

### Task 12: Add evaluation, operations, and release gates

**Files:**
- Create: `src/minions/sage/metrics.py`
- Create: `tests/integration/test_sage_complete_flow.py`
- Modify: SAGE docs and deployment documentation

1. Add recall quality, feedback, candidate, job latency/failure and degradation metrics.
2. Add end-to-end tests for shadow-to-approval-to-auto evolution, restart recovery and tenant isolation.
3. Add PostgreSQL migration/rollback rehearsal, backup/restore, concurrency and fault-injection checks.
4. Run SAGE backend tests, affected backend tests, frontend tests/build, Ruff, compile checks and security searches.
5. Document activation runbook: start SHADOW, observe, approve, then enable low-risk AUTO.
