---
name: QA_source_index
description: "Maps topics and keywords from user questions to Minions official documentation paths and common source code entry points, reducing blind searching. Intended for the built-in QA Agent to quickly identify which files to read when answering questions about installation, configuration, skills, MCP, multi-agent, memory, CLI, etc."
metadata:
  builtin_skill_version: "1.3"
  minions:
    emoji: "🗂️"
    requires: {}
---

# Documentation and Source Code Quick Reference

When answering questions about **installation, configuration, or behavioral principles**, first **classify by keyword**, then **open 1–2 paths most likely to contain the answer** from the table below, avoiding aimless directory traversal.

## Usage Steps

1. Extract the topic from the user's question (match against the left column or synonyms in the table below).
2. Resolve **`$MINIONS_ROOT`**: use `which minions` to get the executable path. If it is `…/.minions/bin/minions`, the source root is three levels up (consistent with the **guidance** skill); otherwise, determine it from the user-provided installation path.
3. Resolve **`$DOCS_DIR`** first (cross-install compatible): run `python3 -c "from minions.constant import DOCS_DIR; print(DOCS_DIR or '')" 2>/dev/null`. If it returns a valid path, use it directly. Otherwise, fallback to `$MINIONS_ROOT/website/public/docs/`.
4. **Read documentation first**: `$DOCS_DIR/<topic>.<language>.md` (use the same language as the user: `zh` / `en`.). If that is insufficient, read the **source entry points** listed in the table.

## Topic / Keywords → Preferred Documentation and Source Code

| Topic or Keywords (examples) | Preferred Documentation (`$DOCS_DIR/`) | Common Source Entry Points (relative to `$MINIONS_ROOT`) |
|---------------------|-----------------------------------|-----------------------------------|
| Installation, dependencies, getting started | `quickstart`, `intro` | `packages/minions-cli/src/minions/cli/`, `pyproject.toml` |
| Configuration, config.json, environment variables | `config` | `packages/minions-core/src/minions/config/config.py`, `packages/minions-core/src/minions/constant.py` |
| Skills, SKILL, skill_pool, built-in skills | `skills` | `packages/minions-agents/src/minions/agents/skill_system/`, `packages/minions-agents/src/minions/agents/skills/` |
| MCP, plugins | `mcp` | `packages/minions-app/src/minions/app/routers/` (grep `mcp` as needed) |
| Multi-agent, workspace, agent, built-in QA | `multi-agent` | `packages/minions-app/src/minions/app/routers/agents.py`, `packages/minions-app/src/minions/app/migration.py`, `packages/minions-core/src/minions/constant.py` (`BUILTIN_QA_AGENT_ID`, etc.) |
| SAGE, business experience, lessons, recall | `sage` | `packages/minions-agents/src/minions/sage/`, `docs/sage-deployment.md` |
| Console, frontend | `console` | `console/` |
| CLI, subcommands, init | `cli` | `packages/minions-cli/src/minions/cli/` (e.g., `init_cmd.py`) |
| Channels, sessions | `channels` | Search for `channels` keyword under `packages/*/src/minions` |
| Context, window | `context` | `config` docs + related logic in `packages/minions-agents/src/minions/agents/` |
| Models, API Key | `models` | `packages/minions-core/src/minions/config/config.py` |
| Heartbeat, HEARTBEAT | `heartbeat` | Search for `heartbeat` / `HEARTBEAT` under `packages/*/src/minions` |
| Desktop client | `desktop` | `desktop/` (if present in the repository) |
| Security | `security` | Read `security.<lang>.md` first |
| Errors, FAQ | `faq` | Read `faq.<lang>.md` first, then examine source code as needed |
| Commands and slash commands | `commands` | CLI/command registration modules under `packages/*/src/minions` (search as needed) |

## Conventions

- Full documentation path: `$DOCS_DIR/<topic>.<language>.md` (fall back to `.en.md` if the corresponding language file does not exist). Prefer `DOCS_DIR` from `minions.constant`; fallback to `$MINIONS_ROOT/website/public/docs/`.
- The **source entry points** in the table are starting points; use `read_file` or targeted `grep` to narrow down to specific symbols — do not read through an entire large directory listing at once.

## Notes

- This skill **does not replace** `read_file`: after identifying candidate paths, you should immediately read and verify the content.
- If a path does not exist locally (e.g., an installation tree without source code), use the **installed documentation package** or the root directory provided by the user, and clearly state which path you are relying on.
