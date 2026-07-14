# Remove Legacy Memory System Implementation Plan

> **For Codex:** Execute this plan task-by-task and verify each layer before continuing.

**Goal:** Remove the former ReMe/ADBPG and Markdown-based long-term memory system so SAGE is the only long-lived business experience system in Minions.

**Architecture:** Keep session state, Native/Scroll compaction, and dialog offloading as short-term context infrastructure. Remove every former long-term memory backend, tool, command, configuration field, workspace API, UI surface, dependency, and current documentation reference. Preserve SAGE's lifecycle integration and storage adapters unchanged.

**Tech Stack:** Python 3.11+, Pydantic, FastAPI, React, TypeScript, Vitest, Pytest, SQLite.

---

### Task 1: Establish the removal boundary

**Files:**
- Create: `docs/plans/2026-07-13-remove-legacy-memory-system.md`
- Inspect: `src/minions/agents/memory/**`
- Inspect: `src/minions/agents/context/scroll/**`
- Inspect: `src/minions/sage/**`

1. Classify ReMe, ADBPG, Markdown daily memory, memory search, dream, memorize, and legacy proactive-memory mode as removable.
2. Classify session state, Scroll history, Native compaction, tool-output offloading, and SAGE as retained.
3. Record the boundary in this plan.

### Task 2: Remove legacy backend and runtime integration

**Files:**
- Delete: `src/minions/agents/memory/**`
- Modify: `src/minions/agents/react_agent.py`
- Modify: `src/minions/agents/middlewares.py`
- Modify: `src/minions/agents/command_handler.py`
- Modify: `src/minions/runtime/builtin_commands.py`
- Modify: `src/minions/runtime/commands/daemon.py`
- Modify: `src/minions/cli/daemon_cmd.py`
- Modify: `src/minions/runtime/prompt_contributors.py`
- Modify: `src/minions/agents/prompt.py`
- Modify: `src/minions/agents/context/scroll/manager.py`
- Modify: `src/minions/agents/context/scroll/prompt.py`

1. Remove legacy manager constructor parameters and compatibility attributes.
2. Remove memory middleware and former memory commands.
3. Make `/new` clear session context without scheduling old summarization.
4. Remove memory-prompt injection and old auto-search stripping.
5. Run focused runtime, command, prompt, and Scroll tests.

### Task 3: Remove configuration, dependency, and operational checks

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/minions/config/config.py`
- Modify: `src/minions/config/utils.py`
- Modify: `src/minions/config/__init__.py`
- Modify: `src/minions/constant.py`
- Modify: `src/minions/cli/doctor_checks.py`
- Modify: `src/minions/app/migration.py`
- Modify: `src/minions/governance/tool_registry.py`

1. Remove ReMe dependency and all former backend configuration models/fields.
2. Remove old dream scheduling, vector-memory doctor checks, constants, migration entries, and tool aliases.
3. Verify old agent JSON fields are ignored safely by Pydantic during transition.

### Task 4: Remove Markdown memory API and workspace UI

**Files:**
- Create: `src/minions/agents/workspace_markdown.py`
- Modify: `src/minions/app/routers/workspace.py`
- Modify: `console/src/api/modules/workspace.ts`
- Modify: `console/src/api/types/workspace.ts`
- Modify: `console/src/pages/Agent/Workspace/**`
- Delete: former daily-memory API and integration tests

1. Retain safe CRUD for ordinary workspace Markdown files in a newly named manager.
2. Delete `/workspace/memory` endpoints and daily-memory frontend methods/types.
3. Simplify the workspace file tree to ordinary prompt files only.
4. Verify workspace file CRUD and frontend rendering.

### Task 5: Remove legacy configuration UI and tool rendering

**Files:**
- Delete: `console/src/pages/Agent/Config/components/ReMeLightMemoryCard.tsx`
- Delete: `console/src/pages/Agent/Config/components/ADBPGConfigCard.tsx`
- Delete: `console/src/components/Chat/ToolCards/cards/MemorySearchCard.tsx`
- Modify: `console/src/pages/Agent/Config/**`
- Modify: `console/src/constants/backendMappings.ts`
- Modify: `console/src/api/types/agent.ts`
- Modify: tool-card registry and formatting helpers

1. Remove backend selector, long-term-memory tabs, and old config merge logic.
2. Remove former memory-search card and formatter.
3. Update or delete affected Vitest cases.

### Task 6: Remove templates, tests, and current documentation

**Files:**
- Delete: `src/minions/agents/md_files/*/MEMORY.md`
- Modify: bootstrap/persona templates that instruct the agent to maintain Markdown memory
- Delete: legacy memory unit/integration/E2E tests
- Replace: current website memory documentation with SAGE documentation
- Modify: README and current documentation links

1. Ensure new workspaces no longer create Markdown long-term memory files.
2. Remove tests that assert deleted behavior.
3. Document SAGE as the sole long-term experience system.

### Task 7: Prove cleanup completeness

1. Search functional code for `ReMe`, `ADBPG`, `memory_manager`, `memory_search`, `auto_memory`, and removed API paths.
2. Run `python3 -m pytest tests/unit/sage -q`.
3. Run focused backend tests for runtime, workspace, config, and Scroll.
4. Run focused frontend tests and `npx vite build`.
5. Report any unrelated pre-existing type-check failures separately.
