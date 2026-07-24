# Minions Multi-Distribution Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Minions from one setuptools distribution into thirteen independently installable implementation distributions plus a source-free `minions==0.1.0` meta distribution without breaking supported imports or runtime behavior.

**Architecture:** Use a native PEP 420 `minions` namespace with mutually exclusive wheel ownership. Remove upward dependencies before moving source files, enforce the locked distribution allowlist with static and dynamic import analysis, and keep CLI/app as composition roots that explicitly initialize environment and high-level adapters.

**Tech Stack:** Python 3.11-3.13, setuptools/PEP 621, uv workspace, pytest, import-linter, `build`, `venv`, AST analysis, wheel ZIP inspection.

## Global Constraints

- `C:/MyProject/REFACTOR_PLAN_1.md` is the normative specification; this file is the executable checkpoint map.
- Preserve `pip install minions`, `minions`, and `python -m minions`.
- Keep Python `>=3.11,<3.14` and every distribution at exactly `0.1.0`.
- Preserve user configuration, agent/session/backup/plugin/channel/REST formats and the public import paths listed in specification section 0.2.
- Do not use delayed imports, `TYPE_CHECKING`, `try/except ImportError`, string service locators, or upward compatibility shims to hide forbidden dependencies.
- Preserve existing worktree changes; never use destructive reset or clean commands.
- Every production change follows red-green-refactor and each checkpoint ends with targeted verification.

---

### Task 1: Rebase the Working Baseline and Preserve Existing Guardrails

**Files:**
- Modify: `src/minions/__version__.py`
- Modify: `packages/*/pyproject.toml`
- Modify: `docs/refactor/import-baseline.json`
- Modify: `docs/refactor/public-api-baseline.json`
- Test: `tests/contract/refactor/test_workspace_scaffold.py`
- Test: `tests/contract/refactor/test_baseline_tools.py`

**Interfaces:**
- Consumes: GitHub `main@ab6d8781dc924c7895b1f4b6411a0c5ddac72307` and the two current unstaged public-API scanner files.
- Produces: a conflict-free branch based on the documented baseline, with every current workspace version equal to `0.1.0` and compatibility baselines reflecting the merged source tree.

- [ ] Add a failing workspace contract asserting root/component version `0.1.0`, thirteen component directories, and no missing `minions-app`/`minions-cli` entries.
- [ ] Run `uv run --no-sync python -m pytest tests/contract/refactor/test_workspace_scaffold.py -q` and confirm it fails on the old eleven-component/`2.0.0` scaffold.
- [ ] Merge `origin/main` without discarding unstaged changes, add the two missing component placeholders, and change all placeholder versions to `0.1.0`.
- [ ] Regenerate `uv.lock`, import baseline, and public-API baseline only after inspecting the source changes introduced by the merge.
- [ ] Run the workspace, baseline, namespace, and bootstrap contract suites and confirm they pass.

### Task 2: Complete the Stage 0 Architecture Analyzer

**Files:**
- Modify: `architecture.toml`
- Modify: `scripts/refactor/check_architecture.py`
- Modify: `scripts/refactor/analyze_imports.py`
- Modify: `scripts/refactor/_architecture_common.py`
- Test: `tests/contract/refactor/test_architecture_checker.py`

**Interfaces:**
- Consumes: Python source roots and the exact `ALLOWED` matrix from specification section 2.3.
- Produces: `check_architecture(root, config) -> ArchitectureReport` covering normal, local, `TYPE_CHECKING`, literal dynamic imports, forbidden module literals, unknown owners, and distribution SCCs; CLI supports `--report`.

- [ ] Add failing tests for `importlib.import_module("minions.agents.x")`, `__import__("minions.app.x")`, `sys.modules.get("minions.agents.tools")`, report metrics, and the complete fourteen-distribution config.
- [ ] Run the new tests and confirm each fails because calls/literals/reporting are currently unimplemented.
- [ ] Add `ast.Call` and literal scanning, explicit documented-string exemptions, report aggregation, and the locked ownership/allowlist configuration.
- [ ] Run `tests/contract/refactor/test_architecture_checker.py`, then run the checker in report mode against the monolith and retain actionable forbidden-edge diagnostics instead of mapping everything silently to the umbrella distribution.

### Task 3: Establish the Real Core Bootstrap Boundary

**Files:**
- Create: `src/minions/core/__init__.py`
- Create: `src/minions/core/bootstrap.py`
- Modify: `src/minions/constant.py`
- Modify: `src/minions/cli/main.py`
- Modify: `src/minions/app/_app.py`
- Restore: `src/minions/app/__init__.py`
- Modify: `src/minions/agents/__init__.py`
- Remove after callers migrate: `src/minions/bootstrap.py`
- Remove after callers migrate: `src/minions/_bootstrap_paths.py`
- Remove after callers migrate: `src/minions/app/bootstrap_env.py`
- Test: `tests/contract/refactor/test_namespace_bootstrap.py`

**Interfaces:**
- Produces: `initialize_environment(env_file: str | Path | None = None) -> BootstrapStatus`, where repeated calls are idempotent and failures are represented in the returned status after warning rather than breaking import.
- Produces: `minions.agents.__init__`-owned installation of the AgentScope compatibility shim.

- [ ] Replace current bootstrap expectations with failing tests for cwd/explicit `.env`, no namespace import side effects, warning/status on persisted-env failure, idempotence, CLI-before-config ordering, app-before-FastAPI ordering, and a retained real `minions.app` package.
- [ ] Run the focused tests and confirm failures expose the current app/backup dependency, repository-relative dotenv loading, propagated exception, and missing app initializer.
- [ ] Implement `minions.core.bootstrap` with a lock and state, move restore/env orchestration behind core-owned helpers, move compatibility installation to agents, and update composition roots.
- [ ] Run bootstrap, CLI import, app import, env-store, and secret-store tests until green.

### Task 4: Make L0 Independently Installable

**Files:**
- Create: `src/minions/core/context.py`
- Create: `src/minions/core/protocols.py`
- Create: `src/minions/core/restore.py` (or focused modules below `core/restore/`)
- Create: `src/minions/security/access_control.py`
- Modify: `src/minions/app/agent_context.py`
- Modify: `src/minions/config/config.py`
- Modify: `src/minions/config/utils.py`
- Modify: `src/minions/config/context.py`
- Modify: `src/minions/envs/store.py`
- Modify: `src/minions/backup/**`
- Modify: `src/minions/utils/console_static.py`
- Test: `tests/unit/**`
- Test: `tests/contract/refactor/**`

**Interfaces:**
- Produces: real ContextVar set/get/reset APIs in `minions.core.context`, with the legacy app module re-exporting them.
- Produces: `AgentBuilderProtocol`, `ApprovalRequester`, `WorkspaceProtocol`, and minimal `ChannelProtocol`.
- Produces: core-only config/env/security/utils imports with no AgentScope dependency.

- [ ] Add focused failing tests for ContextVar identity/reset, config construction without plugin import, access-control migration, core restore locking/stale recovery, and core import isolation.
- [ ] Run each focused test and confirm the expected upward dependency is what fails.
- [ ] Move the ContextVars and restore primitives, split config helpers to their specified owners, remove plugin/provider/channel scanning from core config, and change resource resolution to metadata/resources APIs.
- [ ] Run unit/contract tests plus an isolated `minions-core` dependency/import smoke test.

### Task 5: Remove Runtime Upward Dependencies

**Files:**
- Move: `src/minions/runtime/builder.py` -> `src/minions/agents/runtime_builder.py`
- Move: `src/minions/runtime/builtin_commands.py` -> `src/minions/agents/builtin_commands.py`
- Move: `src/minions/runtime/prompt_contributors.py` -> `src/minions/agents/prompt_contributors.py`
- Move: runtime control handlers to `agents/control_handlers/` and `app/control_handlers/`
- Move: `src/minions/runtime/commands/daemon.py` -> `src/minions/app/commands/daemon.py`
- Modify: `src/minions/runtime/runtime.py`
- Modify: `src/minions/runtime/tool_guard.py`
- Modify: affected callers and tests.

**Interfaces:**
- Runtime consumes an `AgentBuilderProtocol`/factory and optional `ApprovalRequester`; it never imports agents/app/providers/plugins/governance/drivers.
- Agents/app composition roots register high-level handlers and pass concrete factories explicitly.

- [ ] Add failing import-isolation and injection tests for Runtime, tool guard, handler registration, and moved public/internal paths.
- [ ] Verify tests fail on current direct `AgentBuilder` and app approval imports.
- [ ] Move composition code, inject the builder/requester, update all real callers and monkeypatch targets, and do not add runtime-to-agents compatibility shims.
- [ ] Run runtime, agents, app, command, and architecture tests.

### Task 6: Decouple Agents, Hooks, and Plugins

**Files:**
- Create: `src/minions/agents/acp/host.py`
- Create: `src/minions/app/acp_host.py`
- Create: `src/minions/plugins/host.py`
- Move: hook implementations to `agents/lifecycle_hooks/` and `app/lifecycle_hooks/`
- Modify: `src/minions/agents/acp/server.py`
- Modify: `src/minions/plugins/api.py`
- Modify: `src/minions/plugins/registry.py`
- Modify: `src/minions/plugins/loader.py`
- Modify: app composition/bootstrap code.

**Interfaces:**
- Produces: typed `ACPHostServices` and `PluginHost`; host-required paths raise explicit `RuntimeError` when not configured.
- Plugin manifest/list/install operations remain usable without importing agents/app/loop.

- [ ] Add failing isolated-import and host-injection tests, including rejection of existing `sys.modules.get("minions.agents.tools")` coupling.
- [ ] Run them and confirm failure on direct imports/module literals.
- [ ] Implement typed hosts, split hook ownership, configure hosts in app, and remove all plugins-to-agents/app/loop plus agents-to-app imports.
- [ ] Run plugin, ACP, hook, app integration, and architecture tests.

### Task 7: Finish Domain and Channel Boundaries

**Files:**
- Move: `src/minions/app/channels/**` -> `src/minions/channels/**` except the specified app-only handler/facades.
- Move: `src/minions/app/console_push_store.py` -> channel ownership.
- Modify: `src/minions/governance/generalize.py`
- Modify: `src/minions/governance/tool_adapter.py`
- Modify: `src/minions/loop/**`
- Modify: `src/minions/modes/**`
- Create/modify: five `src/minions/app/channels` compatibility facade modules.

**Interfaces:**
- Channels expose low-level `register_channel()`/registry APIs and own their proto/resources.
- Governance consumes injected model/approval interfaces and never imports agents/app.
- Domain direction is `agents -> modes -> (governance, loop)`.

- [ ] Add failing channel compatibility/resource, domain import-isolation, and injection tests.
- [ ] Verify failures on the current app channel location and upward imports.
- [ ] Move channel implementation, retain only the five specified app facades plus app-owned QR handler, and inject governance dependencies.
- [ ] Run channel/plugin/app/domain tests and architecture report.

### Task 8: Perform the Physical Monorepo Move

**Files:**
- Populate: `packages/minions-{core,runtime,providers,tool-calls,drivers,channels,plugins,loop,governance,modes,agents,app,cli}/`
- Modify: all component `pyproject.toml`
- Modify: root `pyproject.toml`
- Create: `requirements-workspace.txt`
- Regenerate: `uv.lock`
- Remove: root `src/` and obsolete `setup.py` after all moves.

**Interfaces:**
- Each implementation distribution is a buildable setuptools project at `0.1.0` with exact internal pins and direct third-party dependencies.
- Root `minions` distribution contains no Python source and depends on all thirteen components.

- [ ] Add failing namespace owner, version alignment, resource ownership, and meta-source tests before moving files.
- [ ] Move one dependency layer at a time with `git mv`, updating imports/tests and running the relevant layer suite after each move.
- [ ] Configure package discovery/data/licenses and root extras/workspace source mappings.
- [ ] Run compileall, namespace, architecture, version, and editable workspace tests.

### Task 9: Implement Build and Isolation Gates

**Files:**
- Create: `scripts/check_workspace_versions.py`
- Create: `scripts/check_wheel_ownership.py`
- Create: `scripts/build_workspace.py`
- Create: `scripts/install_built_wheels.py`
- Create: `scripts/check_component_installs.py`
- Modify: `.importlinter`
- Test: `tests/architecture/**`

**Interfaces:**
- Build produces exactly fourteen wheels and fourteen sdists.
- Ownership gate rejects overlaps/root namespace init/missing resources/meta source.
- Component installer creates isolated dependency closures and supports `--component`.

- [ ] Write failing tests using synthetic wheel/workspace fixtures for version drift, overlaps, missing assets, wrong wheel count, and incomplete component dependencies.
- [ ] Run each test and confirm the corresponding script/function is missing or rejects incorrectly.
- [ ] Implement scripts and exact import-linter bands from the specification.
- [ ] Build all artifacts, run ownership/version checks, and run thirteen isolated component installs with `pip check`.

### Task 10: Update CI, Docker, Install, Release, and Runtime Verification

**Files:**
- Modify: `.github/workflows/**`
- Modify: `deploy/**`
- Modify: `scripts/install.sh`
- Modify: `scripts/wheel_build.sh`
- Modify: `scripts/wheel_build.ps1`
- Modify: `Makefile`
- Modify: coverage configuration and hard-coded resource paths.

**Interfaces:**
- All automation installs/builds the workspace and consumes local fourteen-wheel output without shell-glob assumptions.
- Release uploads components before meta and keeps frontend workflow behavior unchanged.

- [ ] Add/adjust contract tests or script assertions that fail on remaining `src/minions`, old coverage, old console/docs/version paths, and single-wheel install flows.
- [ ] Update CI/Docker/install/release paths and resource lookup.
- [ ] Run static gates, unit/contract/integration/full tests, build/clean-install checks, CLI/API runtime smoke, and resource/namespace uninstall smoke exactly as specification section 5 requires.
- [ ] Record all skipped external-service tests and their reasons without converting ordinary failures to skips.

## Completion Evidence

- Final report includes HEAD/dirty state, fourteen distributions and versions, dependency graph with SCC=0, exact verification commands/results, and every unexecuted external-service item.
- Completion requires all gates in `C:/MyProject/REFACTOR_PLAN_1.md` section 5; directory scaffolding or partial tests are not completion.
