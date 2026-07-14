<div align="center">

# Minions

[![GitHub 仓库](https://img.shields.io/badge/GitHub-仓库-black.svg?logo=github)](https://github.com/agentscope-ai/Minions)
[![PyPI](https://img.shields.io/pypi/v/minions?color=3775A9&label=PyPI&logo=pypi)](https://pypi.org/project/minions/)
[![文档](https://img.shields.io/badge/文档-在线-green.svg?logo=readthedocs&label=Docs)](https://minions.agentscope.io/)
[![Python 版本](https://img.shields.io/badge/python-3.11%20~%20%3C3.14-blue.svg?logo=python&label=Python)](https://www.python.org/downloads/)
[![许可证](https://img.shields.io/badge/license-Apache%202.0-red.svg?logo=apache&label=%E8%AE%B8%E5%8F%AF%E8%AF%81)](LICENSE)
[![GitHub Star](https://img.shields.io/github/stars/agentscope-ai/Minions?style=flat&logo=github&color=yellow&label=Star)](https://github.com/agentscope-ai/Minions/stargazers)
[![Discord](https://img.shields.io/badge/Discord-Join_Us-blueviolet.svg?logo=discord)](https://discord.gg/eYMpfnkG8h)
[![钉钉群](https://img.shields.io/badge/DingTalk-Join_Us-orange.svg)](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)

[[文档](https://minions.agentscope.io/)] [[English](README.md)]

**你的个人 AI 助理 — 随时随地，私有部署。**

> Minions 基于 [QwenPAW](https://github.com/zhoulingquan/qwenpaw)（Qwen Personal Agent Workstation）发展而来。

</div>

---

## Minions 是什么

**Minions 是一个开源的个人 AI 助理平台**。它不是套在 LLM 外层的聊天壳子，而是一个从底层设计的**智能体运行引擎** — 管理上下文、调度模型、执行工具、守卫安全、沉淀记忆，所有能力都可被 Skills 和插件扩展。

## 为什么选择 Minions（和其他 AI 助手的区别）

| 维度 | 普通 AI 助理 | Minions |
|------|------------|---------|
| **上下文** | 单一消息数组 / 向量检索 | 三层记忆系统（Working + Scroll + History）|
| **记忆** | 摘要压缩后永久丢失 | 早期对话完整逐字保留，可随时精确召回 |
| **执行** | 单轮调用 | StopGate 闭环引擎（迭代/死循环检测/预算控制）|
| **多 Agent** | 单实例单 Agent | AgentManager + ACP 跨实例编排 |
| **安全** | 用户自行把关 | Sandbox + Tool Guard + File Guard 默认开启 |
| **多租户** | 单用户 | 多租户控制面 + PostgreSQL RLS 隔离 |
| **频道** | 单一 Web/API | 7 个内置频道 + 插件自定义 |
| **部署** | 云端 SaaS | 本机私有部署，数据不离开你的机器 |

---

## 一句话上手

**`pip install minions && minions init --defaults && minions app`** — 然后浏览器打开 `http://127.0.0.1:8088`，你的 AI 助理就上线了。

---

## 架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        渠道 / 接入层 (Channels)                    │
│  Web 控制台  │  TUI (终端)  │  钉钉  │  飞书  │  QQ  │  企业微信  │
│  微信  │  腾讯元宝  │  REST API / SSE  │  ACP (Agent→Agent)  │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│                        会话管理层 (Runtime)                       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Scroll 上下文管理系统                                    │    │
│  │  ┌──────────┬──────────┬──────────────────────┐         │    │
│  │  │ Working  │ Memory   │  History (完整逐字)   │         │    │
│  │  │ Context  │ Scroll   │  支持 Lazy Load /    │         │    │
│  │  │ (当前轮) │ (知识蒸馏│  Streaming / 分页)    │         │    │
│  │  └──────────┴──────────┴──────────────────────┘         │    │
│  └──────────────────────────────────────────────────────────┘    │
│  模型调用 → 模型调用 → 输出拦截 → 工具执行 → 输出拦截 → 上下文更新  │
│  (完整的循环引擎: pre_process → call → post_process → 回写)      │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│                        Agent 引擎层                               │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │   Agent 管理器 (AgentManager)                             │    │
│  │   多智能体创建 / 调度 / 生命周期管理                        │    │
│  │   子 Agent 运行时生成 / 委派 / ACP 跨实例通信               │    │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │   StopGate / Mode 系统                                    │    │
│  │   IterationGate / DoomLoopGate / BudgetGate / RubricGate │    │
│  │   GoalMode / MissionMode (Mode 激活时才运行的 Hook)       │    │
│  │   Hook 系统: 8 阶段均可插拔拦截                             │    │
│  └──────────────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │   执行引擎 (executors / drivers)                          │    │
│  │   Shell Executor, MCP Driver, Plugin Driver              │    │
│  │   命令构建 → 安全拦截 → 沙箱执行 → 结果返回               │    │
│  └──────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│                        安全层 (Security)                          │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │   Sandbox (内核级隔离: Seatbelt / bwrap / Landlock)        │    │
│  │   Tool Guard (工具调用规则引擎 / 白名单联网策略)            │    │
│  │   File Guard (文件操作边界守卫, 多级权限策略)               │    │
│  │   Skill Scanner (安装前自动检测注入 / 权限 / 恶意模式)      │    │
│  │   Tenancy (多租户控制面 / PostgreSQL RLS 隔离)             │    │
│  │   Governance (审计日志 / 审批工作流)                        │    │
│  └──────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────┐
│                        扩展层                                     │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐       │
│  │  Skills  │  插件    │  MCP     │  Cron    │  SAGE    │       │
│  │  (脚本 / │ (Python) │ (模型→   │ (定时    │ (多租户  │       │
│  │  可安装) │          │  工具)   │  任务)   │  经验库) │       │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘       │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  模型提供商层 (Providers)                                 │    │
│  │  内置: DeepSeek / Minions Local (llama.cpp) / Ollama /   │    │
│  │        LM Studio                                         │    │
│  │  自定义: 任意 OpenAI-compatible 端点 (OpenAI / Anthropic  │    │
│  │         / Gemini / DashScope / vLLM / ...)               │    │
│  │  统一接口: /v1/chat/completions → 每个 go Provider        │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 核心特色详解

### 1. 三层记忆系统 — 不丢失任何细节

这是 Minions **最核心的技术差异**。传统 AI 助理用"摘要压缩"处理长对话 — 早期内容被压缩后信息永久丢失。Minions 不同：

| 层级 | 容量 | 机制 |
|------|------|------|
| **Working Context** | 当前轮次 | 活跃上下文，完整保留当前交互 |
| **Memory Scroll** | 知识蒸馏 | 重要事实/决策/用户偏好经提取后沉淀，非向量检索 |
| **Full History** | 完整逐字存储 | 早期轮次被逐出 Working Context 但完整保留，可随时精确召回 |

**联动机制**：Working Context 满了 → 历史轮次转入 Full History 存储 → 关键知识同步到 Memory Scroll → 需要时从 Full History 中精确检索，**不压缩、不摘要、不丢失**。

### 2. Scroll 上下文管理引擎

Runtime 核心不是简单的"消息数组"，而是 **Scroll** 系统：

- 每轮交互是一个 `MessageScroll`，包含完整的 `Message` 对象链
- 支持 Lazy Load、Streaming 追加、分页读取
- Scroll 可以在 Agent 间传递、持久化到磁盘、从磁盘恢复
- 所有模型调用 / 工具执行 / 输出处理都在 Scroll 上下文中完成

这意味着你可以随时 **resume** 任意历史会话，看到当时的完整上下文。

### 3. 多 Agent 引擎 + ACP 跨实例编排

Agent 不是单例，而是一个可管理、可生成、可协作的系统：

- **AgentManager**：创建、列出、销毁、切换 Agent；每个 Agent 拥有独立的 System Prompt、记忆 Scroll、工具集
- **子 Agent 委派**：运行中实时生成子 Agent，委托子任务（子文件搜索、子代码生成），结果返回主 Agent
- **ACP（Agent Communication Protocol）**：跨实例 Agent 通信协议，实现多个 Minions 实例之间的编排协作

### 4. StopGate / Mode 系统 — 执行闭环引擎

LLM 调用不是一次性的，而是在 ReAct Loop 中反复执行，由 **StopGate** 组合控制终止条件：

- **IterationGate**：硬性迭代上限，防止无限循环
- **DoomLoopGate**：滑动窗口相似度检测，两阶段（注入警告 → 强制终止），防止死循环
- **BudgetGate**：token 预算限制
- **FileLoopGate**：文件状态 + 迭代次数联合判定
- **RubricGate**：rubric 完成度评估

**Mode 系统**控制 Agent 行为模式，Mode 激活时才运行对应的 Hook 和 Gate：
- **GoalMode**：目标导向执行（含 GoalTurnGate / GoalBudgetGate / RubricGate）
- **MissionMode**：任务模式（含 MissionGate + 状态加载/保存 Hook）

**Cron 执行器**：定时触发执行（新闻摘要、报告生成、多频道广播），支持会话隔离和并发限流。

整个 Runtime 编排分 **8 个 Phase**（PRE_DISPATCH → POST_DISPATCH → PRE_AGENT_BUILD → POST_AGENT_BUILD → PRE_EXECUTE → POST_RESPONSE → ON_ERROR → FINALLY），每个 Phase 均可插入 Hook，按拓扑排序执行。

### 5. 安全闸门体系 — 默认开启，非可选

所有危险操作在执行前即被拦截，不需要用户主动开启：

- **Sandbox**：内核级隔离，按平台选择机制 — macOS 用 Seatbelt（`sandbox-exec`）、Linux 用 Bubblewrap（`bwrap` mount namespace）或 Landlock（LSM）、Windows 用 AppContainer。每次工具调用创建独立 sandbox
- **Tool Guard**：三层 Guardian 协调 — FilePathToolGuardian（敏感文件路径检测）+ RuleBasedToolGuardian（YAML 规则匹配）+ ShellEvasionGuardian（7 类 shell 混淆检测）
- **File Guard**：文件操作边界守卫，默认保护 `.env` / `.ssh` / `*.pem` / `*.key` / `.aws` / `.gnupg` 等
- **Skill Scanner**：安装 Skills 前自动扫描 — 8 类威胁签名（命令注入 / 数据外泄 / 硬编码密钥 / 混淆 / 提示注入 / 社工 / 供应链 / 未授权工具使用）
- **Governance**：三阶段策略评估（深度扫描 → 规则匹配 → fallback）+ 审计日志（SQLite WAL，100K 记录自动清理）+ 审批工作流（批准后动态添加 session 级 ALLOW 规则）

### 6. Skills / MCP / 插件 — 三层扩展机制

| 扩展方式 | 用途 | 特点 |
|----------|------|------|
| **Skills** | 脚本化能力（文件爬虫、网页抓取、定时新闻） | 可安装、可共享，带自动 Scanner |
| **MCP 协议** | 模型直接调用外部工具 | 标准化协议，AI 生态兼容 |
| **插件** | Python 深度集成 | 访问内部 API、注册新频道/Provider |

### 7. 多频道接入 — 一个实例，多个渠道

```
  Web 控制台   终端 TUI    钉钉    飞书    QQ
    企业微信   微信    腾讯元宝    REST API / SSE    ACP
```

内置 7 个频道（console + 6 个 IM），一个实例所有渠道共享 Agent、记忆、Skills。控制台 / TUI 中看到的历史在钉钉上同样可访问。插件系统可注册自定义频道。

### 8. 代码模式 — 内置三面板 Web IDE

- **文件树**：浏览项目结构
- **Diff 预览**：每次修改前后对比
- **对话区**：与 Agent 交互

支持代码搜索、跳转定义、查找引用。GoalMode / MissionMode 行为模式切换。

### 9. 定时任务（Cron）— 自然语言编排

- 自然语言描述任务（"每天早上 8 点抓取 Hacker News 前十条，发送到钉钉群"）
- 模型自动转化为 Cron 表达式
- 支持多频道广播
- 可编排为自动化工作流

### 10. SAGE 经验系统（企业版）— 知识沉淀引擎

跨会话业务经验生命周期系统，与多租户控制面共享同一份可信身份：

- **7 种 Scope**：TENANT / TEAM / USER / AGENT / PROJECT / CASE / SESSION，二维隔离（tenant_id + scope）
- **分层模型**：Trace → Case → KnowledgeItem → InsightDraft → Playbook
- **渐进式激活**：OFF / SHADOW / APPROVAL / AUTO，Insight 必须经过 GrowthCycle + PolicyCenter 审批才能 active
- **混合召回**：SemanticIndexer 基于 embeddings 的语义检索 + FTS 关键词搜索，按 RecallBudget 分配 prompt 预算
- **Fail-closed 存储**：production/tenant 模式必须用 PostgreSQL，SQLite fallback 被拒绝

### 11. 多租户系统（企业版）— 控制面隔离

完整的多租户控制面（tenancy 2.1），支持多团队协作和资源隔离：

- **5 级角色**：OWNER / ADMIN / OPERATOR / MEMBER / VIEWER，权限嵌套累加
- **Agent 授权**：每个 Agent 归属一个 tenant，支持 PRIVATE（仅 owner）和 TENANT（团队可见）两种访问级别
- **PostgreSQL RLS 双边界**：应用层 `ScopePolicy.require_tenant` + 数据库层 RLS（`app.tenant_id` / `sage.tenant_id` 两套独立上下文），RLS 是第二道防线
- **配额管理**：max_members / max_agents / max_concurrent_tasks / max_storage_mb，任务租约（10min TTL，60s 续约）防资源耗尽
- **可信身份**：`TenantPrincipal` 由认证层构造（不接受客户端 claim），单向流动到 SAGE 的 `TrustedSageIdentity`
- **Fail-closed**：tenant/production 模式拒绝 SQLite，PRIVATE Agent 对无权者返回 404（不泄露存在性）
- **多空间切换**：一个用户可加入多个 tenant，切换时撤销旧 session

---

## 模型支持

| 类型 | 提供商 |
|------|--------|
| 内置 | DeepSeek（云端）、Minions Local（本地，基于 llama.cpp，零配置）、Ollama、LM Studio |
| 自定义 | 任意 OpenAI-compatible 端点 — OpenAI、Anthropic、Gemini、DashScope、vLLM 等 |
| 嵌入 | 支持多种 Embedding 模型 |

所有模型通过统一的 `Provider` 接口调用 — `go` 方法接收 Messages + Tools，返回 Response。

---

## 快速开始

### pip 安装（推荐）

```bash
pip install minions
minions init --defaults
minions app
```

浏览器打开 **http://127.0.0.1:8088/** → 设置 → 模型 → 配置你的模型提供商，然后开始对话。

### Docker

```bash
docker pull agentscope/minions:latest
docker run -p 127.0.0.1:8088:8088 \
  -v minions-data:/app/working \
  -v minions-secrets:/app/working.secret \
  agentscope/minions:latest
```

### 从源码

```bash
git clone https://github.com/agentscope-ai/Minions.git
cd Minions
cd console && npm ci && npm run build && cd ..
pip install -e .
minions init --defaults
minions app
```

详细的安装选项（脚本安装、桌面应用、云部署等）请参阅[文档](https://minions.agentscope.io/docs/quickstart)。

---

## 终端 TUI

你可以在终端中直接与 Minions 对话：

```bash
minions              # 开启新会话
minions tui --resume <id>  # 恢复之前的会话
```

支持流式回复、斜杠命令、文件粘贴、行内授权提示。与控制台共用同一份记忆与技能。

---

## 文档

| 主题 | 说明 |
|------|------|
| [项目介绍](https://minions.agentscope.io/docs/intro) | Minions 是什么 |
| [模型配置](https://minions.agentscope.io/docs/models) | 云端 / 本地 / 自定义模型 |
| [频道配置](https://minions.agentscope.io/docs/channels) | 钉钉、飞书、QQ、企业微信、微信、腾讯元宝 |
| [Skills](https://minions.agentscope.io/docs/skills) | 扩展与自定义能力 |
| [MCP 与工具](https://minions.agentscope.io/docs/mcp) | 外部工具集成 |
| [定时任务](https://minions.agentscope.io/docs/cron) | 任务计划与自动化 |
| [安全](https://minions.agentscope.io/docs/security) | Sandbox、Tool Guard、File Guard 等 |
| [插件系统](https://minions.agentscope.io/docs/plugins) | 插件开发与使用 |
| [多智能体](https://minions.agentscope.io/docs/multi-agent) | Agent 编排与协作 |
| [SAGE](https://minions.agentscope.io/docs/sage) | 业务经验系统（企业版） |
| [ACP 集成](https://minions.agentscope.io/docs/acp-integration) | Agent Communication Protocol |
| [REST API](https://minions.agentscope.io/docs/api-tutorial) | HTTP API 集成 |
| [CLI](https://minions.agentscope.io/docs/cli) | 命令行工具 |

---

## 项目起源

Minions 源自 [QwenPAW](https://github.com/zhoulingquan/qwenpaw)（Qwen Personal Agent Workstation — 千问个人智能体工作台），在原项目基础上进行了重构与持续演进。

---

## 参与贡献

欢迎各种形式的参与！见 [CONTRIBUTING](CONTRIBUTING.md)。

- 横向拓展：新频道、模型提供商、Skills、MCP
- 功能完善：UI 优化、兼容性修复、文档改进

---

## 许可证

[Apache License 2.0](LICENSE)
