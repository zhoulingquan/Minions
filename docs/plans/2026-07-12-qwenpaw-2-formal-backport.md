# QwenPaw 2.0 Formal Backport Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 QwenPaw v2.0.0-beta.4 到 v2.0.0 正式版之间高价值的非前端改进安全移植到 Minions，同时保留 Minions 的品牌、精简频道、已删除 Coding Mode，以及当前全局技能体系改造。

**Architecture:** 以 Minions 当前 `2.0.0b4` 后端为基线，按上游提交的语义而不是整版合并进行移植。每组改动都保留 `minions` 命名和现有 API，Loop 等可能影响插件的改动增加向后兼容层；Web 工具在上游实现之外补充 SSRF、重定向和响应体限制。

**Tech Stack:** Python 3.11–3.13、AgentScope 2.0.4、FastAPI、Pydantic、Textual/ACP、pytest。

---

### Task 1: Security and session integrity

**Files:**
- Modify: `src/minions/security/tool_guard/guardians/rule_guardian.py`
- Modify: `src/minions/security/tool_guard/rules/dangerous_shell_commands.yaml`
- Modify: `src/minions/app/chats/manager.py`
- Modify: `src/minions/runtime/commands/control/stop_handler.py`
- Modify: `src/minions/agents/command_handler.py`
- Modify: `src/minions/agents/memory/reme_light_memory_manager.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/security/test_rm_bypass_fix_5090.py`
- Test: `tests/unit/app/chats/test_manager.py` or nearest existing chat-manager test

**Steps:**
1. Add failing regression tests for `${HOME}` removal, `${RM}` detection and `find -delete`.
2. Split destructive-command detection substitutions from target extraction substitutions.
3. Add `user_id` filtering to chat lookup and pass the requesting user from `/stop`.
4. Resolve memory session IDs from explicit argument, state, then request ContextVar; skip ReMe writes with an empty session.
5. Pin `mcp>=1.13.0,<2.0.0` beside AgentScope.
6. Run security, chat, stop-command and memory tests.

### Task 2: Loop gate lifecycle

**Files:**
- Modify: `src/minions/loop/gates/*.py`
- Modify: `src/minions/loop/react_gates.py`
- Modify: `src/minions/agents/react_agent.py`
- Modify: `src/minions/modes/goal/*.py`
- Modify: `src/minions/modes/mission/*.py`
- Test: `tests/unit/loop/test_*.py`

**Steps:**
1. Add tests proving a new user turn resets iteration and doom-loop state.
2. Introduce `BYPASS`, `INTERRUPT_AND_CONTINUE`, and `TERMINATE`, retaining legacy aliases for Minions plugins.
3. Add `reset()` and `build_continuation()` gate lifecycle methods.
4. Reset peer gates only when a continuation starts a fresh sub-turn.
5. Preserve pending continuation across tool-call iterations.
6. Update Goal/Mission gates and prompts to the new contract.
7. Run all Loop, Goal and Mission tests.

### Task 3: Provider and tool-message compatibility

**Files:**
- Modify: `src/minions/agents/model_factory.py`
- Modify: `src/minions/agents/utils/tool_message_utils.py`
- Modify: `src/minions/providers/capping_formatter.py`
- Modify: `src/minions/providers/openai_response_provider.py`
- Modify: `src/minions/providers/provider.py`
- Modify: `src/minions/providers/*_provider.py`
- Modify: `src/minions/providers/provider_manager.py`
- Test: `tests/unit/agents/test_cross_provider_normalization.py`
- Test: `tests/unit/agents/test_model_factory_message_normalization.py`
- Test: `tests/unit/agents/utils/test_tool_message_utils.py`

**Steps:**
1. Add failing tests for Responses function names, whitespace-prefixed tool JSON, unsupported block alignment and Responses media capping.
2. Preserve top-level function-call names in Responses items.
3. Make reasoning alignment predict every block the base formatter drops.
4. Add the Responses-specific capping formatter.
5. Rename `preserve_thinking` to `relay_reasoning` with a legacy configuration validator; default DashScope relay off.
6. Run provider and model-factory tests.

### Task 4: Scroll context and error protocol

**Files:**
- Modify: `src/minions/agents/context/scroll/eviction_index.py`
- Modify: `src/minions/agents/context/scroll/manager.py`
- Modify: `src/minions/agents/context/__init__.py`
- Modify: `src/minions/config/config.py`
- Create: `src/minions/utils/model_response.py`
- Modify: `src/minions/hooks/error/error_hook.py`
- Modify: `src/minions/runtime/envelope.py`
- Modify: `src/minions/runtime/runtime.py`
- Modify: `src/minions/app/chats/utils.py`
- Test: `tests/unit/agents/context/test_eviction_index.py`
- Test: `tests/unit/agents/context/test_scroll_manager.py`
- Test: `tests/unit/utils/test_model_response.py`

**Steps:**
1. Add the archived-index/live-turn seam banner regression test.
2. Add best-effort labels for un-headlined eviction spans with timeout and extractive fallback.
3. Centralize streamed/non-streamed model response extraction.
4. Carry ToolChunk state into API messages and emit structured `{code, message}` errors.
5. Run context, runtime-envelope and chat-conversion tests.

### Task 5: ACP/TUI and user-facing tools

**Files:**
- Create: `src/minions/agents/acp/meta.py`
- Modify: `src/minions/agents/acp/server.py`
- Modify: `src/minions/hooks/session/session_hook.py`
- Modify: `src/minions/cli/tui/**/*.py`
- Modify: `src/minions/agents/tools/file_search.py`
- Create: `src/minions/agents/tools/web_search.py`
- Modify: `src/minions/agents/tools/__init__.py`
- Modify: `src/minions/runtime/builder.py`
- Modify: `src/minions/governance/policy.py`
- Modify: `src/minions/governance/tool_registry.py`
- Modify: `src/minions/app/channels/dingtalk/channel.py`
- Test: relevant ACP, TUI, file-search, Web security and DingTalk tests

**Steps:**
1. Share Minions ACP metadata keys between client/server and prevent ephemeral warmup persistence.
2. Add approval expiration, cancellation and exact/pattern session scopes.
3. Add grep literal OR and grouped path output.
4. Add pluggable web search/fetch tools with private-network rejection, redirect revalidation, SSL verification, content-type and response-size limits.
5. Surface strict DingTalk delivery failures.
6. Run ACP/TUI/tool/channel tests.

### Task 6: Verification

**Steps:**
1. Run targeted tests after every task group.
2. Run formatting/lint checks on changed Python files.
3. Run the full unit test suite with the repository test runner.
4. Review `git diff` to ensure no Console, Tauri, Coding Mode, deleted channel, QwenPaw-brand or unrelated global-skill changes were introduced.
5. Report passed tests, remaining failures and any intentionally deferred optional capability.
