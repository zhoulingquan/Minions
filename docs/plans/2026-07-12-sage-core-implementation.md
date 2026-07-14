# SAGE Core Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first production-shaped SAGE core as a completely new subsystem for tenant-scoped traces, cases, knowledge, insights, playbooks, recall, and controlled growth.

**Architecture:** Add a standalone `src/minions/sage` package with no imports from the legacy memory package. Domain models and service ports remain storage-neutral; the first adapter is a durable SQLite implementation for development and tests, while the interfaces preserve a PostgreSQL path for production. Every operation requires an immutable `Principal` and tenant filtering is enforced inside the store, not delegated to callers.

**Tech Stack:** Python 3.11+, Pydantic v2, SQLite/WAL/FTS5, pytest, AgentScope-compatible async runtime API.

---

### Task 1: Domain model and tenant invariants

**Files:**
- Create: `src/minions/sage/models.py`
- Create: `src/minions/sage/errors.py`
- Create: `src/minions/sage/policy.py`
- Test: `tests/unit/sage/test_models_and_policy.py`

**Steps:**
1. Write failing tests for immutable IDs, required tenant identity, scope validation, and cross-tenant rejection.
2. Run `python -m pytest tests/unit/sage/test_models_and_policy.py -q` and verify failure.
3. Implement Principal, Trace, CaseRecord, KnowledgeItem, InsightDraft, Playbook, ActionPack, enums, and ScopePolicy.
4. Run the test and verify pass.

### Task 2: Storage port and SQLite TraceBook

**Files:**
- Create: `src/minions/sage/store.py`
- Create: `src/minions/sage/sqlite_store.py`
- Test: `tests/unit/sage/test_sqlite_store.py`

**Steps:**
1. Write failing tests for schema creation, WAL mode, idempotent trace append, tenant-scoped reads, and close/reopen durability.
2. Run the test and verify failure.
3. Define the `SageStore` protocol and implement parameterized SQLite queries.
4. Add tenant-first indexes and FTS5 with LIKE fallback.
5. Run the test and verify pass.

### Task 3: CaseBook and SageCatalog

**Files:**
- Create: `src/minions/sage/casebook.py`
- Create: `src/minions/sage/catalog.py`
- Test: `tests/unit/sage/test_casebook_catalog.py`

**Steps:**
1. Write failing tests for opening/finishing cases, outcome validation, knowledge versioning, and disputed facts.
2. Implement CaseBook and SageCatalog over `SageStore`.
3. Verify tenant isolation and state transitions.

### Task 4: GrowthCycle

**Files:**
- Create: `src/minions/sage/growth.py`
- Test: `tests/unit/sage/test_growth.py`

**Steps:**
1. Write failing tests proving reflection cannot activate itself, evidence is independent, and high-risk promotion requires approval.
2. Implement draft, validation, approval, activation, supersede, rollback, and archive transitions.
3. Verify illegal transitions fail closed.

### Task 5: RecallPlanner and ActionPack

**Files:**
- Create: `src/minions/sage/recall.py`
- Test: `tests/unit/sage/test_recall.py`

**Steps:**
1. Write failing tests for tenant filtering, scope specificity, active-state filtering, token budget, and source IDs.
2. Implement lexical/structured retrieval and deterministic ranking.
3. Verify no draft, erased, expired, or foreign-tenant item is returned.

### Task 6: SageRuntime facade

**Files:**
- Create: `src/minions/sage/runtime.py`
- Create: `src/minions/sage/__init__.py`
- Test: `tests/unit/sage/test_runtime.py`

**Steps:**
1. Write failing end-to-end tests for begin → observe → finish → prepare.
2. Implement the async facade with strict Principal requirements.
3. Verify restart durability and explanatory source links.

### Task 7: Runtime integration without legacy imports

**Files:**
- Create: `src/minions/sage/lifecycle.py`
- Modify: `src/minions/app/workspace/workspace.py`
- Modify: `src/minions/runtime/builder.py`
- Test: `tests/unit/sage/test_lifecycle.py`

**Steps:**
1. Write failing integration tests proving the lifecycle receives user, assistant, tool, and outcome observations.
2. Add a new `SageLifecycle` extension; do not subclass or import legacy memory classes.
3. Register SAGE as a separate workspace service and middleware contribution.
4. Keep activation explicit until parity tests pass; do not silently fall back to legacy storage.

### Task 8: Verification and handoff

**Steps:**
1. Run `python -m pytest tests/unit/sage -q`.
2. Run existing context and memory regression suites to detect accidental coupling.
3. Run formatting/static checks for changed Python files.
4. Review `git diff` and confirm no unrelated user changes were modified.
5. Document completed milestone and remaining PostgreSQL/admin UI work.
