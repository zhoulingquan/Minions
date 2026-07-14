---
name: QA_source_index
description: "将用户问题中的主题、关键词映射到 Minions 官方文档路径与常见源码入口，减少盲目搜索。适用于内置 QA Agent 在回答安装、配置、技能、MCP、多智能体、记忆、CLI 等问题时快速选定要读的文件。"
metadata:
  builtin_skill_version: "1.3"
  minions:
    emoji: "🗂️"
    requires: {}
---

# 文档与源码速查

回答 **安装、配置、行为原理** 类问题时，先 **按关键词归类**，再按下表 **打开 1～2 个最可能命中的路径** 阅读，避免长时间无目的遍历。

## 使用步骤

1. 从用户问题中提取主题（对照下表左列或同类词）。
2. 解析 **`$MINIONS_ROOT`**：以 `which minions` 得到可执行路径，若为 `…/.minions/bin/minions` 则源码根为其上三级目录（与 **guidance** skill 一致）；否则结合用户给出的安装路径判断。
3. 先解析 **`$DOCS_DIR`**（兼容多种安装方式）：执行 `python3 -c "from minions.constant import DOCS_DIR; print(DOCS_DIR or '')" 2>/dev/null`。若返回有效路径则直接使用；否则 fallback 到 `$MINIONS_ROOT/website/public/docs/`。
4. **先读文档** `$DOCS_DIR/<专题>.<语言>.md`（语言取与用户一致：`zh` / `en`），仍不足再读表中 **源码入口**。

## 主题 / 关键词 → 优先文档与源码

| 主题或关键词（示例） | 优先文档（`$DOCS_DIR/`） | 常见源码入口（相对 `$MINIONS_ROOT`） |
|---------------------|-----------------------------------|-----------------------------------|
| 安装、依赖、首次使用 | `quickstart`、`intro` | `src/minions/cli/`、`pyproject.toml` |
| 配置、config.json、环境变量 | `config` | `src/minions/config/config.py`、`src/minions/constant.py` |
| 技能、SKILL、skill_pool、内置技能 | `skills` | `src/minions/agents/skill_system/`、`src/minions/agents/skills/` |
| MCP、插件 | `mcp` | `src/minions/app/routers/`（按需 grep `mcp`） |
| 多智能体、工作区、agent、内置 QA | `multi-agent` | `src/minions/app/routers/agents.py`、`src/minions/app/migration.py`、`src/minions/constant.py`（`BUILTIN_QA_AGENT_ID` 等） |
| SAGE、业务经验、心得、召回 | `sage` | `src/minions/sage/`、`docs/sage-deployment.md` |
| 控制台、前端 | `console` | `console/` |
| 命令行、子命令、init | `cli` | `src/minions/cli/`（如 `init_cmd.py`） |
| 频道、会话 | `channels` | 在 `src/minions` 下按 `channels` 关键词检索 |
| 上下文、窗口 | `context` | `config` 文档 + `src/minions/agents/` 相关逻辑 |
| 模型、API Key | `models` | `src/minions/config/config.py` |
| 心跳、HEARTBEAT | `heartbeat` | 在 `src/minions` 下检索 `heartbeat` / `HEARTBEAT` |
| 桌面客户端 | `desktop` | `desktop/`（若仓库中存在） |
| 安全 | `security` | 先读 `security.<lang>.md` |
| 报错、常见问题 | `faq` | 先 `faq.<lang>.md`，再针对性看源码 |
| 命令与斜杠指令 | `commands` | `src/minions` 下与 CLI/命令注册相关的模块（按需检索） |

## 约定

- 文档完整路径：`$DOCS_DIR/<专题>.<语言>.md`（无对应语言时用 `.en.md` 兜底）。优先使用 `minions.constant` 中的 `DOCS_DIR`，失败时 fallback 到 `$MINIONS_ROOT/website/public/docs/`。
- 表中 **源码入口** 为起点；应用 `read_file` 或局部 `grep` 缩小到具体符号，不要一次性通读大目录 listing。

## 注意

- 本 skill **不替代** `read_file`：锁定候选路径后应立即读取并核对。
- 若某路径在本地不存在（例如未带源码的安装树），以 **已安装的文档包** 或用户提供的根目录为准，并明确告知依据路径。
