# ADR-0013: Promote Agent Skill Copies with Optimistic Concurrency

## Status

Accepted

## Context

Agents run local skill copies so one agent can tune behavior independently. A successful local tuning session needs a safe way to update the reusable global skill. Direct automatic reverse synchronization can overwrite concurrent global work and can unexpectedly affect other agents.

## Decision

Add an explicit agent-skill promotion operation. The operation compares the current global content with the agent's `synced_from_global_hash`, rejects concurrent changes by default, and permits a deliberate forced promotion. Promotion updates global content only; rollout is a separate opt-in action. New synchronization hashes cover the complete skill directory, while legacy `SKILL.md` hashes remain readable.

## Consequences

### Positive

- Locally validated improvements can become reusable without silent data loss.
- Concurrent global edits are detected.
- Other agents are not changed merely because one agent was promoted.
- Script and reference changes participate in synchronization state.

### Negative

- Users must perform an explicit promotion step.
- Legacy hashes cannot detect historical auxiliary-file changes until the next synchronization.
- A forced promotion can still discard global changes, so the UI must make it deliberate.

### Neutral

- Per-agent configuration remains separate from promoted skill content.
- A future version-history UI can build on the same promotion boundary.

## Alternatives Considered

- Automatic reverse synchronization was rejected as unsafe for shared behavior.
- A mandatory new global name for every promotion was rejected because it fragments lineage.
- A Git-like revision store was deferred to avoid over-engineering the current local filesystem system.

## References

- `src/minions/agents/skill_system/global_skill_service.py`

