# Agent Skill Promotion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let one agent tune a downloaded skill and safely promote the improved copy back to global skills without unexpectedly changing other agents.

**Architecture:** Keep global skills and workspace copies as separate directories. Track their relationship with a stable whole-directory hash, use optimistic concurrency for promotion, and expose the resulting state in the workspace UI. Promotion is explicit and does not roll out by default.

**Tech Stack:** Python, FastAPI, filesystem JSON manifests, React, TypeScript, Vitest, pytest.

---

### Task 1: Content hashing and manifest persistence

**Files:**
- Modify: `src/minions/agents/skill_system/store.py`
- Modify: `src/minions/agents/skill_system/registry.py`
- Test: `tests/unit/agents/test_skill_sync.py`

**Steps:**

1. Write tests proving auxiliary files affect the directory hash and ignored cache artifacts do not.
2. Write a reconciliation test proving `synced_from_global_hash` and `last_synced_at` survive.
3. Implement `compute_skill_content_hash()` and legacy hash matching.
4. Preserve synchronization fields during workspace manifest reconciliation.
5. Run the new unit tests.

### Task 2: Conflict-aware promotion service

**Files:**
- Modify: `src/minions/agents/skill_system/global_skill_service.py`
- Test: `tests/unit/agents/test_skill_sync.py`

**Steps:**

1. Test safe promotion when only the agent changed.
2. Test conflict rejection when both global and agent changed.
3. Test deliberate force promotion and preservation of global config.
4. Implement promotion with `force`, `expected_global_hash`, and `propagate` controls.
5. Update global-to-agent status and auto-update checks to use directory hashes.
6. Run the service tests.

### Task 3: Workspace edit and synchronization API

**Files:**
- Modify: `src/minions/app/routers/skills.py`
- Test: `tests/unit/app/routers/test_skills_router.py`

**Steps:**

1. Add router tests for workspace save, successful promotion, and HTTP 409 conflicts.
2. Restore workspace save through `SkillService.save_skill()` and schedule a reload.
3. Extend workspace skill specs with synchronization state.
4. Extend `/sync/push` into the promotion endpoint while keeping its path compatible.
5. Fix `/sync/resolve` so both resolution choices work.
6. Make normal global saves use conflict-aware auto-update instead of unconditional overwrite.
7. Run router tests.

### Task 4: Console promotion workflow

**Files:**
- Modify: `console/src/api/types/skill.ts`
- Modify: `console/src/api/modules/skill.ts`
- Modify: `console/src/pages/Agent/Skills/components/SkillCard.tsx`
- Modify: `console/src/pages/Agent/Skills/components/SkillListItem.tsx`
- Modify: `console/src/pages/Agent/Skills/index.tsx`
- Modify: `console/src/pages/Agent/Skills/useSkillsPage.tsx`
- Modify: `console/src/pages/Agent/Skills/index.module.less`
- Test: `console/src/api/modules/skill.test.ts`

**Steps:**

1. Add API tests for the promotion request and agent header.
2. Add synchronization fields to `SkillSpec`.
3. Add the typed `promoteSkillToGlobal()` API call.
4. Make skill cards/list items open the local editor.
5. Display synchronization status and an explicit promotion action.
6. On HTTP 409, require confirmation before a forced promotion.
7. Refresh workspace/global caches after success.
8. Run Vitest and TypeScript checks.

### Task 5: Verification

**Files:**
- Verify all files above.

**Steps:**

1. Run targeted Python unit tests.
2. Run targeted console unit tests.
3. Run Python formatting/lint checks for modified backend files.
4. Run TypeScript compilation.
5. Review the final diff for unrelated changes and document any pre-existing failures.

