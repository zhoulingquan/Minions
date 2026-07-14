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

Minions 是一个开源的**个人 AI 助理平台** — 这不是一个聊天机器人的壳子，而是一个从底层设计的智能体运行引擎。它管理上下文、调度模型、执行工具、守卫安全、沉淀记忆，所有能力都可被 Skills 和插件扩展。

---

## 一句话

**`pip install minions && minions init --defaults && minions app`** — 然后浏览器打开 `http://127.0.0.1:8088`，你的 AI 助理就上线了。

---

## 架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        渠道 / 接入层 (Channels)                    │
│  Web 控制台  │  TUI (终端)  │  钉钉  │  飞书  │  Discord  │  Telegram  │
│  WeChat / QQ / iMessage  │  REST API / SSE  │  ACP (Agent→Agent) │
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
│  │   Loop / Mode 系统                                       │    │
│  │   PlanLoop → BuildLoop → ReviewLoop (代码开发闭环)       │    │
│  │   AgentLoop (通用对话), CronLoop (定时), API (无状态)    │    │
│  │   Hook 系统: 所有阶段均可插拔拦截                          │    │
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
│  │   Sandbox (内核级隔离, cgroups / seccomp)                   │    │
│  │   Tool Guard (工具调用规则引擎 / 白名单联网策略)            │    │
│  │   File Guard (文件操作边界守卫, 多级权限策略)               │    │
│  │   Skill Scanner (安装前自动检测注入 / 权限 / 恶意模式)      │    │
│  │   Access Policy / Firewall (来源访问控制)                   │    │
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
│  │  OpenAI / Anthropic / DeepSeek / Qwen / Gemini / DashScope│    │
│  │  Ollama / vLLM / llama.cpp (本地) / 自定义 14+ 提供商     │    │
│  │  统一接口: /v1/chat/completions → 每个 go Provider        │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 核心特性详解

### 1. 三层记忆系统（不是向量检索）

传统 AI 助理用"摘要压缩"处理长对话 — 早期内容被压缩后信息永久丢失。Minions 不同：

| 层级 | 容量 | 机制 |
|------|------|------|
| **Working Context** | 当前轮次 | 活跃上下文，完整保留当前交互 |
| **Memory Scroll** | 知识蒸馏 | 重要事实/决策/用户偏好经提取后沉淀，非向量检索 |
| **Full History** | 完整逐字存储 | 早期轮次被逐出 Working Context 但完整保留，可随时精确召回 |

三层联动：Working Context 满了 → 历史轮次转入 Full History 存储 → 关键知识同步到 Memory Scroll → 需要时从 Full History 中精确检索，不压缩、不摘要、不丢失。

### 2. Scroll 上下文管理引擎

Runtime 核心不是简单的"消息数组"，而是 **Scroll** 系统：

- 每轮交互是一个 `MessageScroll`，包含完整的 `Message` 对象链
- 支持 Lazy Load、Streaming 追加、分页读取
- Scroll 可以在 Agent 间传递、持久化到磁盘、从磁盘恢复
- 所有模型调用 / 工具执行 / 输出处理都在 Scroll 上下文中完成

这让你可以随时 **resume** 任意历史会话，看到当时的完整上下文。

### 3. 多 Agent 引擎

Agent 不是单例，而是一个可管理、可生成、可协作的系统：

- **AgentManager**：创建、列出、销毁、切换 Agent；每个 Agent 拥有独立的 System Prompt、记忆 Scroll、工具集
- **子 Agent 委派**：运行中实时生成子 Agent，委托子任务（子文件搜索、子代码生成），结果返回主 Agent
- **ACP（Agent Communication Protocol）**：跨实例 Agent 通信协议，实现多个 Minions 实例之间的编排协作

### 4. Loop / Mode 系统 — 执行闭环

LLM 调用不是一次性的，而是在 **Loop** 中反复执行，直到满足终止条件：

- **AgentLoop**：通用对话 → 模型调用 → 工具执行 → 模型调用 → 终止
- **PlanLoop → BuildLoop → ReviewLoop**：代码开发的完整闭环（计划→构建→审查）
- **CronLoop**：定时触发执行（新闻摘要、报告生成、多频道广播）
- **Mode** 控制 Agent 的行为模式 — 代码模式、对话模式、自动执行模式等

每个 Loop 阶段都插入了 **Hook** 系统：前置钩子、后置钩子、工具钩子、授权钩子、流式钩子。

### 5. 安全闸门体系（非可选）

所有危险操作在执行前即被拦截，不需要用户主动开启：

- **Sandbox**：内核级隔离（cgroups / seccomp），代码在沙箱中执行，无法访问宿主机
- **Tool Guard**：工具调用前检查规则引擎，白名单联网策略
- **File Guard**：文件操作边界守卫（读/写/执行），多级权限策略
- **Skill Scanner**：安装 Skills 前自动扫描 — 检测注入、权限滥用、恶意模式
- **Governance**：审计日志 + 审批工作流，所有操作可追溯

### 6. Skills / MCP / 插件 — 三层扩展

| 扩展方式 | 用途 | 特点 |
|----------|------|------|
| **Skills** | 脚本化能力（文件爬虫、网页抓取、定时新闻） | 可安装、可共享，带自动 Scanner |
| **MCP 协议** | 模型直接调用外部工具 | 标准化协议，AI 生态兼容 |
| **插件** | Python 深度集成 | 访问内部 API、注册新频道/Provider |

### 7. 全频道接入

```
  Web 控制台   终端 TUI    钉钉    飞书    Discord
    Telegram   微信    QQ    iMessage    REST API    ACP
```

一个实例，所有渠道共享 Agent、记忆、Skills。控制台 / TUI 中看到的历史在钉钉上同样可访问。

### 8. 代码模式

内置三面板 Web IDE：
- **文件树**：浏览项目结构
- **Diff 预览**：每次修改前后对比
- **对话区**：与 Agent 交互

支持代码搜索、跳转定义、查找引用。PlanLoop → BuildLoop → ReviewLoop 完整闭环。

### 9. 定时任务（Cron）

- 自然语言描述任务（"每天早上 8 点抓取 Hacker News 前十条，发送到钉钉群"）
- 模型自动转化为 Cron 表达式
- 支持多频道广播
- 可编排为自动化工作流

### 10. SAGE 经验系统（企业版）

多租户业务经验沉淀引擎：
- 自动从交互中提取可复用的业务经验
- 经验可控成长（人工审核 + 自动学习）
- 团队级别的知识传承

---

## 模型支持

| 类型 | 提供商 |
|------|--------|
| 云端 | OpenAI、Anthropic、DeepSeek、通义千问、Gemini、DashScope、月之暗面、零一万物、智谱、MiniMax、百度千帆、SiliconFlow、Together AI 等 14+ |
| 本地 | llama.cpp（内置 Minions Local 运行时，零配置）、Ollama、vLLM、自定义 OpenAI-compatible |
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
| [频道配置](https://minions.agentscope.io/docs/channels) | 钉钉、飞书、微信、Discord 等 |
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
