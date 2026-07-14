# SAGE Evolution Phase One Implementation Plan

> **For Codex:** Execute this plan task-by-task using the executing-plans and Code skills.
>
> **Status:** Implemented and verified on 2026-07-13.

**Goal:** Add governed anchors, sectioned recall budgets, recall receipts and feedback traces, and a durable growth outbox without adding infrastructure.

**Architecture:** Reuse KnowledgeItem and Trace for anchors, receipts, and feedback. Extend the storage-neutral SageStore port with queryless item listing and tenant-scoped growth jobs, implement both SQLite and PostgreSQL adapters, then integrate the new primitives through RecallPlanner and SageRuntime.

**Tech Stack:** Python 3.11+, Pydantic, asyncio, SQLite, PostgreSQL/psycopg, Pytest.

---

### Task 1: Add phase-one domain models

**Files:**
- Modify: `src/minions/sage/models.py`
- Modify: `src/minions/sage/__init__.py`
- Test: `tests/unit/sage/test_models_and_policy.py`

1. Add `ItemKind.ANCHOR` and `TraceType.RECALL`.
2. Add `RecallBudget`, `RecallSelection`, `RecallReceipt`, `FeedbackVerdict`, `GrowthJobType`, `GrowthJobState`, and `GrowthJob`.
3. Extend `ActionPack` with anchors, warnings, section token counts, and a receipt.
4. Test budget scaling, validation, and serialization.

### Task 2: Extend the storage port and SQLite adapter

**Files:**
- Modify: `src/minions/sage/store.py`
- Modify: `src/minions/sage/sqlite_store.py`
- Test: `tests/unit/sage/test_sqlite_store.py`

1. Add an authorized `list_items` operation with state and kind filters.
2. Add the SQLite `sage_growth_job` table.
3. Implement idempotent enqueue, tenant-scoped claim, completion, and failure.
4. Test durability, isolation, lease recovery, and idempotency.

### Task 3: Implement the PostgreSQL storage contract

**Files:**
- Modify: `src/minions/sage/postgres_store.py`
- Test: `tests/unit/sage/test_postgres_schema.py`

1. Implement `list_items` using RLS-scoped queries.
2. Implement outbox operations against the existing `sage.growth_job` table.
3. Keep migration 0001 unchanged and verify expected SQL and RLS tables.

### Task 4: Build AnchorPack, section budgets, and receipts

**Files:**
- Modify: `src/minions/sage/recall.py`
- Modify: `src/minions/sage/lifecycle.py`
- Test: `tests/unit/sage/test_recall.py`
- Test: `tests/unit/sage/test_lifecycle.py`

1. Load active, valid, authorized anchors without a text query.
2. Allocate independent budgets to anchors, facts, insights, playbooks, and warnings.
3. Generate deterministic `RecallSelection` reasons and a `RecallReceipt`.
4. Render anchors and warnings as untrusted historical evidence.

### Task 5: Move reflection to the durable outbox

**Files:**
- Modify: `src/minions/sage/runtime.py`
- Modify: `src/minions/sage/lifecycle.py`
- Test: `tests/unit/sage/test_runtime.py`
- Test: `tests/unit/sage/test_lifecycle.py`

1. Enqueue one idempotent reflection job for each completed verified case.
2. Add `run_growth_once` and best-effort task ownership.
3. Record turn-aware recall receipts as trace events.
4. Record explicit feedback as trace events.
5. Verify that request completion no longer awaits InsightFoundry.

### Task 6: Expose minimal feedback commands and verify

**Files:**
- Modify: `src/minions/sage/commands.py`
- Test: `tests/unit/sage/test_commands.py`

1. Include the receipt ID in `/sage-find` output.
2. Add `/sage-feedback <receipt-id> <useful|irrelevant|wrong|outdated> [source-id] [comment]`.
3. Run all SAGE tests, compile the package, and scan for unsafe cross-tenant calls.
