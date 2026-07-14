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

Minions 是一个开源的**个人 AI 助理**，一个智能体（Agent）运行平台。你可以把它部署在自己的服务器或电脑上，通过 Skills 和插件扩展它的能力，通过频道（钉钉、飞书、微信等）随时与它对话。

它不只是聊天机器人。它可以读写文件、搜索网页、运行定时任务、管理代码项目、调用外部 API。你给它装什么技能，它就有什么本事。

---

## 一句话

**`pip install minions && minions init --defaults && minions app`** — 然后浏览器打开 `http://127.0.0.1:8088`，你的 AI 助理就上线了。

---

## 核心特性

| | |
|---|---|
| **完整对话记忆** | 三层记忆架构（工作上下文 + 完整逐字历史 + 知识蒸馏）。早期轮次被逐出但可随时召回，不摘要压缩、不丢失信息。 |
| **多模型支持** | 内置 Minions Local 运行时（llama.cpp 后端），无需 API Key 即可运行。同时支持 OpenAI、Anthropic、DeepSeek、通义千问、Gemini 等 14+ 云端模型供应商。 |
| **隐私优先** | 本地部署，数据留在你的机器。无第三方托管，无数据上传。 |
| **能力扩展** | Skills 系统（定时任务、文档处理、浏览器、新闻等）+ 插件市场 + MCP 协议集成。 |
| **安全体系** | 内核级 Sandbox、Tool Guard、File Guard、Skill Scanner、Access Policy。危险命令在执行前即被拦截。 |
| **多智能体** | 创建拥有独立记忆与技能的 Agent；运行时生成子 Agent；通过 ACP 协议（Agent Communication Protocol）实现跨系统编排。 |
| **全频道连接** | 钉钉、飞书、微信、Discord、Telegram、iMessage、QQ — 一个实例，随处可达。同时提供 Web 控制台与终端 TUI。 |
| **代码模式** | 三面板 Web IDE（文件树 + Diff 预览 + 对话区），支持代码搜索、跳转定义与查找引用。 |
| **定时任务** | 按计划自动执行 — 新闻摘要、报告生成、多频道广播。 |
| **SAGE 经验系统** | 多租户业务经验沉淀，自动学习与可控成长（企业版）。 |
| **自动化工作流** | 组合 Skills、插件和定时任务，打造适合你的专属流程。 |

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
|---|---|
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

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    频道层                            │
│  控制台  │  TUI  │  钉钉  │  飞书  │  Discord  │ ... │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│                    Agent 层                         │
│  多智能体管理  │  运行时引擎  │  工具执行  │  ACP   │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│                  能力层                              │
│  Skills  │  插件  │  MCP  │  Cron  │  SAGE  │ 记忆 │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│                   安全层                             │
│  Sandbox  │  Tool Guard  │  File Guard  │  策略引擎 │
└─────────────────────────────────────────────────────┘
```

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
