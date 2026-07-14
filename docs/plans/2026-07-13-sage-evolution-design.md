# SAGE Evolution Design

## Objective

Evolve SAGE from a governed evidence store into an experience system that keeps a small set of critical business anchors in context, retrieves dynamic experience with predictable section budgets, records why experience was selected, accepts explicit feedback, and moves reflection work off the request path.

## Constraints

- Preserve TraceBook, CaseBook, GrowthCycle, InsightFoundry, RecallPlanner, tenant scopes, classification checks, approvals, versioning, and rollback.
- Keep SQLite as the single-process development adapter and PostgreSQL as the production adapter.
- Do not add a vector database, broker, graph database, or new service in phase one.
- Never let model-generated content bypass evidence and approval gates.
- Keep immutable source evidence separate from derived experience.

## Phase-One Architecture

### AnchorPack

Critical active knowledge uses `ItemKind.ANCHOR`. Anchor items remain normal governed `KnowledgeItem` objects with scope, classification, confidence, validity, state, and evidence links. Recall lists authorized anchors without requiring a query and includes them in a bounded `AnchorPack` section. The model cannot directly promote an item into an anchor.

### Sectioned ActionPack

`RecallBudget` divides the total prompt allowance into anchors, facts, insights, playbooks, and warnings. Each section has an independent maximum, so a large playbook cannot remove critical warnings. `ActionPack` exposes per-section token use and total estimated use.

### RecallReceipt and Feedback

Every turn-aware recall produces a `RecallReceipt` containing selected source IDs, section, estimated token cost, scope, and deterministic selection reasons. The receipt is appended as an immutable `TraceType.RECALL` event attached to the business case. User judgments are appended as `TraceType.FEEDBACK`; they never mutate published knowledge directly.

### Growth Outbox

Completing a verified case enqueues an idempotent `REFLECT_CASE` job instead of awaiting InsightFoundry. A best-effort background task claims jobs for the same trusted principal. Pending work survives crashes and is retried on a later request from that tenant. PostgreSQL uses its existing `sage.growth_job`; SQLite gains an equivalent development table.

## Failure and Security Model

- Recall failure does not invent experience and does not cross tenant or scope boundaries.
- Receipt persistence failure is observable but does not turn retrieved content into authority.
- Outbox enqueue is idempotent per case.
- Workers reuse the originating principal and receive no elevated approval permissions.
- Failed jobs retain attempts and error text for later operations and UI.
- Runtime shutdown waits for or cancels owned best-effort tasks without losing queued jobs.

## Verification

- Model validation and budget allocation tests.
- SQLite durability, idempotency, tenant isolation, claim, completion, and retry tests.
- PostgreSQL SQL-contract tests without requiring a local PostgreSQL server.
- Recall tests for queryless anchors, independent section caps, warnings, and receipt reasons.
- Lifecycle tests proving response completion enqueues work and does not synchronously reflect.
- Runtime tests for receipt and feedback traces.

## Later Phases

Phase two adds semantic/entity/temporal scoring, conflict detection, shadow evaluation, management APIs, and the SAGE console. Phase three adds sleep-time consolidation, playbook simulation, and controlled cross-agent transfer.
