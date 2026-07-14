# Agent Skills Bidirectional Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the Agent Skills page into two tabs (Global Skills / Agent Skills), enable "Add to Agent" from global pool, implement bidirectional auto-sync between pool and agent skills, and remove the standalone Skill Pool settings page.

**Architecture:** The Agent Skills page becomes the single entry point for all skill management. Two tabs: "Global Skills" (browsable pool skills with "Add to Agent") and "Current Agent Skills" (installed skills with enable/disable/edit). Bidirectional sync uses hash-based change detection on both sides with conflict resolution UI.

**Tech Stack:** React + TypeScript (frontend), Python FastAPI (backend), SHA-256 content hashing, file-based JSON manifests with `fcntl.flock` locking.

---

## Phase 1: Frontend Restructuring (Tabs + Global Skills)

### Task 1: Create Global Skills Tab Component

**Files:**
- Create: `console/src/pages/Agent/Skills/components/GlobalSkillsTab.tsx`
- Create: `console/src/pages/Agent/Skills/components/GlobalSkillCard.tsx`
- Create: `console/src/pages/Agent/Skills/components/GlobalSkillListItem.tsx`

**Step 1: Create GlobalSkillsTab component**

This component fetches pool skills via `api.listSkillPoolSkills()` and displays them in card/list view. Each skill shows an "Add to Agent" button if not already installed, or "Added" state if installed.

```tsx
// GlobalSkillsTab.tsx
// - Fetches pool skills via api.listSkillPoolSkills()
// - Fetches current agent skills via api.listSkills() to determine which are already added
// - Renders in card/list view (reuse existing SkillCard/SkillListItem patterns)
// - Each skill has "Add to Agent" button (calls api.downloadSkillPoolSkill)
// - Supports search and tag filtering (reuse useSkillFilter)
// - Shows sync status badge per skill
```

**Step 2: Create GlobalSkillCard component**

Card view for a pool skill. Shows: name, description, tags, sync status, "Add to Agent" / "Added" button.

**Step 3: Create GlobalSkillListItem component**

List view for a pool skill. Same info as card but in horizontal row format.

**Step 4: Verify lint**

Run: `npx eslint src/pages/Agent/Skills/components/GlobalSkillsTab.tsx src/pages/Agent/Skills/components/GlobalSkillCard.tsx src/pages/Agent/Skills/components/GlobalSkillListItem.tsx`

---

### Task 2: Restructure Agent Skills Page with Tabs

**Files:**
- Modify: `console/src/pages/Agent/Skills/index.tsx`
- Modify: `console/src/pages/Agent/Skills/index.module.less`

**Step 1: Add tab state and imports**

Add `useState<"global" | "agent">` for tab selection. Import `GlobalSkillsTab`.

**Step 2: Replace enabled/disabled sections with tab content**

Current structure:
```
PageHeader
SkillsToolbar
Enabled Skills panel
Disabled Skills panel
```

New structure:
```
PageHeader
Tab bar: [全局技能 | 当前智能体技能]
Tab content:
  - Global tab: <GlobalSkillsTab />
  - Agent tab: SkillsToolbar + Enabled Skills + Disabled Skills (existing)
```

**Step 3: Add tab styles to index.module.less**

Add `.tabBar`, `.tab`, `.tabActive` styles following the filter tab pattern from ACP/Channels pages.

**Step 4: Verify lint and TypeScript**

Run: `npx eslint src/pages/Agent/Skills/index.tsx && npx tsc --noEmit --skipLibCheck 2>&1 | grep -i skill`

---

### Task 3: Simplify Global Skills Actions

**Files:**
- Modify: `console/src/pages/Agent/Skills/components/GlobalSkillsTab.tsx`
- Modify: `console/src/locales/zh.json`

**Step 1: Add "Add to Agent" action**

In GlobalSkillsTab, each skill card/list item has an "Add to Agent" button that:
1. Calls `api.downloadSkillPoolSkill({ skill_name, targets: [{ workspace_id: selectedAgent }] })`
2. Shows loading state during download
3. Shows success message
4. Refreshes both pool and agent skill lists

**Step 2: Add i18n keys**

Add to zh.json under `skillPool`:
- `"addToAgent": "添加到智能体"`
- `"addedToAgent": "已添加"`
- `"globalSkills": "全局技能"`
- `"agentSkills": "当前智能体技能"`

**Step 3: Handle already-added state**

If a pool skill is already installed in the agent, show "已添加" badge instead of "Add to Agent" button. Clicking it could open the skill detail or scroll to it in the Agent Skills tab.

---

### Task 4: Remove Skill Pool Settings Page

**Files:**
- Modify: `console/src/layouts/registry/builtinMenu.ts`
- Modify: `console/src/layouts/registry/builtinRoutes.tsx`
- Keep: All backend API endpoints (still needed for global skills tab)

**Step 1: Remove menu entry from builtinMenu.ts**

Remove the Skill Pool entry from the Settings group (around line 157-163).

**Step 2: Remove route from builtinRoutes.tsx**

Remove the `/skill-pool` route definition.

**Step 3: Verify navigation still works**

Ensure the Agent Skills page is accessible and the Skill Pool page is no longer reachable from the sidebar.

---

## Phase 2: Backend Bidirectional Sync

### Task 5: Add Sync State Tracking

**Files:**
- Modify: `src/minions/agents/skill_system/store.py`
- Modify: `src/minions/agents/skill_system/models.py`

**Step 1: Add sync fields to workspace manifest model**

Add to workspace manifest entries:
```python
"synced_from_pool_hash": "",  # SHA-256 of pool SKILL.md when last synced
"last_synced_at": "",         # ISO timestamp of last sync
```

**Step 2: Add sync fields to pool manifest model**

Pool manifest already has `auto_update_synced_hash`. Add:
```python
"last_synced_at": "",  # ISO timestamp of last sync
"sync_direction": "pool_to_agent",  # or "bidirectional"
```

**Step 3: Add hash computation for workspace skills**

Add `compute_workspace_skill_hash(workspace_dir, skill_name) -> str` in store.py that computes SHA-256 of the workspace skill's SKILL.md content.

**Step 4: Update manifest migration**

Ensure existing manifests without sync fields are handled gracefully (default values).

---

### Task 6: Implement Agent → Pool Sync

**Files:**
- Modify: `src/minions/agents/skill_system/pool_service.py`
- Modify: `src/minions/app/routers/skills.py`

**Step 1: Add `push_workspace_skill_to_pool()` method**

In `SkillPoolService`, add method that:
1. Reads workspace skill's SKILL.md content
2. Computes hash
3. Compares with pool's `auto_update_synced_hash`
4. If different, updates pool skill content
5. Stamps new hash

**Step 2: Add sync trigger on workspace skill save**

In the workspace skill save endpoint (`PUT /skills/save`), after saving:
1. Check if the skill has `synced_from_pool_hash` (meaning it was installed from pool)
2. If yes, call `push_workspace_skill_to_pool()`
3. Update `synced_from_pool_hash` to match pool's new hash

**Step 3: Add conflict detection**

Before pushing, check if pool skill's content hash differs from `synced_from_pool_hash`:
- If same: safe to push (no conflict)
- If different: CONFLICT - both sides changed since last sync

**Step 4: Add conflict resolution endpoint**

New endpoint: `POST /skills/sync/resolve`
```python
class SyncResolveRequest(BaseModel):
    skill_name: str
    resolution: str  # "keep_pool" | "keep_agent" | "manual"
    merged_content: str | None = None  # for "manual" resolution
```

This overwrites the target (pool or agent) with the chosen version.

---

### Task 7: Implement Pool → Agent Auto-Sync

**Files:**
- Modify: `src/minions/agents/skill_system/pool_service.py`

**Step 1: Enhance `run_pool_auto_update_sync()`**

The existing auto-update already handles pool→agent. Enhance it to:
1. Before overwriting agent skill, check if agent has local changes (hash differs from `synced_from_pool_hash`)
2. If agent has changes: mark as conflict, skip auto-sync for that agent
3. Record conflict in a pending conflicts list

**Step 2: Add conflict notification**

When a conflict is detected during auto-sync, post a notification/message to the user indicating which skill has a conflict and needs manual resolution.

---

### Task 8: Add Sync Status API

**Files:**
- Modify: `src/minions/app/routers/skills.py`

**Step 1: Add `GET /skills/sync/status` endpoint**

Returns sync status for all skills in the current workspace:
```json
{
  "skills": {
    "skill_name": {
      "in_pool": true,
      "pool_hash": "abc123...",
      "agent_hash": "def456...",
      "last_synced_hash": "abc123...",
      "sync_status": "synced" | "outdated_pool" | "outdated_agent" | "conflict" | "not_synced",
      "last_synced_at": "2026-..."
    }
  }
}
```

Logic:
- `synced`: pool_hash == agent_hash == last_synced_hash
- `outdated_pool`: pool_hash != last_synced_hash (pool changed, agent didn't)
- `outdated_agent`: agent_hash != last_synced_hash (agent changed, pool didn't)
- `conflict`: both pool_hash and agent_hash differ from last_synced_hash
- `not_synced`: no sync history (skill not from pool, or first time)

---

## Phase 3: Conflict Resolution UI

### Task 9: Create Conflict Resolution Modal

**Files:**
- Create: `console/src/pages/Agent/Skills/components/SyncConflictModal.tsx`
- Create: `console/src/pages/Agent/Skills/components/SyncConflictModal.module.less`

**Step 1: Create modal component**

A modal that shows:
- Skill name
- Three options: "保留全局版本" / "保留智能体版本" / "手动编辑"
- Side-by-side diff view (or simplified text diff)
- Confirm button

**Step 2: Implement diff display**

Simple line-by-line diff:
- Green background for added lines
- Red background for removed lines
- Side-by-side or unified view

**Step 3: Wire up resolution**

On confirm, call `POST /skills/sync/resolve` with the chosen resolution. Refresh both skill lists.

---

### Task 10: Integrate Conflict Indicators

**Files:**
- Modify: `console/src/pages/Agent/Skills/components/GlobalSkillCard.tsx`
- Modify: `console/src/pages/Agent/Skills/components/GlobalSkillListItem.tsx`
- Modify: `console/src/pages/Agent/Skills/components/SkillCard.tsx`
- Modify: `console/src/pages/Agent/Skills/components/SkillListItem.tsx`

**Step 1: Add conflict badge**

Skills with `sync_status === "conflict"` show a warning badge/icon. Clicking it opens the SyncConflictModal.

**Step 2: Add sync status indicator**

Skills with `sync_status === "outdated_pool"` or `"outdated_agent"` show a sync icon indicating updates are available.

**Step 3: Add "Sync Now" action**

For outdated skills, show a "Sync Now" button that triggers immediate sync without conflict (since only one side changed).

---

## Phase 4: Cleanup and Polish

### Task 11: Update Navigation and Routing

**Files:**
- Modify: `console/src/layouts/registry/builtinMenu.ts`
- Modify: `console/src/layouts/registry/builtinRoutes.tsx`
- Modify: `console/src/locales/zh.json`

**Step 1: Verify menu structure**

Ensure Agent Skills is prominent in the sidebar. Remove any references to the old Skill Pool settings page.

**Step 2: Update breadcrumbs**

Agent Skills page breadcrumbs should be: Agent > Skills (no change needed).

**Step 3: Update translations**

Add all new i18n keys for:
- Tab labels
- Sync status text
- Conflict resolution options
- Action buttons

---

### Task 12: Integration Testing

**Files:**
- Create: `tests/unit/agents/test_skill_sync.py` (if needed)

**Step 1: Test pool → agent sync**

1. Create a pool skill
2. Add it to an agent
3. Edit the pool skill
4. Verify agent skill is updated

**Step 2: Test agent → pool sync**

1. Add a pool skill to an agent
2. Edit the agent skill
3. Verify pool skill is updated

**Step 3: Test conflict detection**

1. Add a pool skill to an agent
2. Edit both pool and agent versions
3. Verify conflict is detected
4. Resolve conflict and verify correct version is kept

**Step 4: Test edge cases**

- Skill not from pool (should not sync)
- Pool skill deleted (should handle gracefully)
- Agent deleted (should clean up sync state)

---

## Summary of Files Changed

### New Files (Frontend)
- `console/src/pages/Agent/Skills/components/GlobalSkillsTab.tsx`
- `console/src/pages/Agent/Skills/components/GlobalSkillCard.tsx`
- `console/src/pages/Agent/Skills/components/GlobalSkillListItem.tsx`
- `console/src/pages/Agent/Skills/components/SyncConflictModal.tsx`
- `console/src/pages/Agent/Skills/components/SyncConflictModal.module.less`

### Modified Files (Frontend)
- `console/src/pages/Agent/Skills/index.tsx` - Add tabs
- `console/src/pages/Agent/Skills/index.module.less` - Tab styles
- `console/src/pages/Agent/Skills/components/SkillCard.tsx` - Add sync indicator
- `console/src/pages/Agent/Skills/components/SkillListItem.tsx` - Add sync indicator
- `console/src/layouts/registry/builtinMenu.ts` - Remove skill pool menu
- `console/src/layouts/registry/builtinRoutes.tsx` - Remove skill pool route
- `console/src/locales/zh.json` - Add new translations

### Modified Files (Backend)
- `src/minions/agents/skill_system/store.py` - Sync state fields
- `src/minions/agents/skill_system/pool_service.py` - Bidirectional sync logic
- `src/minions/app/routers/skills.py` - New sync endpoints
