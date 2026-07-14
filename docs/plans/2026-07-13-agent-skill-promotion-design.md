# Agent Skill Promotion Design

## Current-State Diagnosis

Before this change, global skills were the reusable source in
`WORKING_DIR/global_skills`, while each agent executed a materialized copy in
`workspaces/<agent>/skills`. Downloads recorded a `synced_from_global_hash`,
but the implementation was in a hybrid state:

- Runtime execution correctly used the agent copy, so local tuning was
  isolated.
- Workspace manifest reconciliation could discard the synchronization
  baseline.
- Hashes covered only `SKILL.md`, so script/reference changes were invisible.
- The existing push endpoint did not provide a deliberate, conflict-aware
  promotion workflow in the console.
- Saving a global skill could force-overwrite installed workspace copies,
  including copies with local improvements.

The refactor keeps the existing filesystem model and closes those gaps instead
of introducing a second source of truth.

## Requirements

### Functional

- A skill downloaded from global skills can be edited inside one agent without immediately changing other agents.
- The agent copy exposes whether it is synchronized, locally improved, globally outdated, or conflicted.
- A locally improved agent copy can be promoted back to global skills explicitly.
- Promotion must refuse a silent overwrite when the global copy changed after the agent copy was created.
- A user can explicitly force promotion after reviewing a conflict.
- Promotion updates the global skill but does not roll it out to other agents by default.
- Per-agent runtime settings (`enabled`, `channels`, and `config`) stay private to the agent unless a future workflow explicitly promotes them.

### Non-functional

- Reuse the existing filesystem manifests and avoid introducing a database.
- Preserve compatibility with manifests that stored a `SKILL.md`-only hash.
- Scan the complete candidate skill before promotion.
- Replace skill directories atomically enough that a failed manifest update does not leave an untracked global version.
- Keep automatic global-to-agent rollout conflict-aware.

## Architecture

```text
global skill G0
     |
     | download (record base hash B=G0)
     v
agent copy A0 -- local edit --> A1
                              |
                              | promote(expected G0)
                              v
                        compare G with B
                         /           \
                   G == B           G != B
                     |                 |
               safe promotion      conflict/force
                     |
                     v
                 global G1
                     |
                     | optional, explicit rollout
                     v
                other agents
```

The global skill remains the reusable source, while each agent runs a materialized workspace copy. `synced_from_global_hash` is an optimistic-concurrency token. New writes use a stable hash over the whole skill directory; legacy `SKILL.md` hashes remain readable until the next successful synchronization.

## Components

- `store.py`: stable directory hashing and legacy hash matching.
- `registry.py`: manifest reconciliation preserves synchronization metadata.
- `global_skill_service.py`: status calculation and conflict-aware promotion.
- `skills.py`: workspace editing, promotion API, and conflict resolution.
- Console skill API/types: typed status and promotion request.
- Workspace skill UI: status badges, local editing, and explicit “promote to global” action.

## Key Decisions

1. Promotion is explicit. Automatic reverse synchronization is rejected because one agent's optimization may be unsafe for other use cases.
2. Promotion and rollout are separate. The default promotion updates only the global source. Existing global-to-agent controls remain responsible for distribution.
3. Content and runtime configuration are separate. Skill files are promoted; agent config remains local and global default config is preserved.
4. Optimistic concurrency uses the last synchronized hash. When both sides changed, the server returns a conflict instead of choosing a winner.
5. Hashing covers the full directory. Auxiliary scripts and references are part of skill behavior and must participate in change detection.

## Failure Modes

| Failure | Handling |
|---|---|
| Global changed during agent tuning | Return HTTP 409 with global, agent, and base hashes |
| Agent has no global relationship but same name exists | Require explicit force confirmation |
| Security scan fails | Reject promotion and preserve both existing versions |
| Manifest reconciliation runs | Preserve base hash and last-sync timestamp |
| Automatic rollout meets local agent changes | Skip that agent and report a conflict |
| Promotion succeeds but rollout is not requested | Stamp the auto-update observation hash so later startup does not unexpectedly broadcast it |

## Alternatives Considered

- Automatic agent-to-global synchronization: rejected because it silently changes shared behavior.
- Always create a new global skill name: safe but creates duplicate skills and loses lineage.
- Full version-control/PR subsystem: valuable later, but too large for the current filesystem architecture. The optimistic promotion flow is the smallest safe foundation.
