/**
 * builtinMenu.ts — host's built-in sidebar menu entries as data.
 *
 * Importing this module self-registers all builtins into menuRegistry, so the
 * Sidebar's `useMenuItems()` snapshot returns them on first render. Plugins
 * register via `Minions.menu.add(...)` which lands in the same registry, so
 * Sidebar treats core + plugin items uniformly.
 *
 * ── Naming convention ──────────────────────────────────────────────────────
 *  Group ids: `core.<name>-group` (e.g. core.control-group)
 *  Item ids:  `core.<key>`        (e.g. core.workspace)
 *  Plugin items use their own prefix (e.g. cloudpaw.a2a) — no clash possible.
 *
 * ── Sticky chat button carve-out ───────────────────────────────────────────
 *  `core.chat` is NOT in this data. The sticky chat button lives outside the
 *  antd <Menu> (rendered next to AgentSelector with bespoke styling); see
 *  Sidebar.tsx. We don't model it as menu data because it has zero antd-Menu
 *  semantics in common with the rest of the sidebar entries.
 *
 * ── Order convention ───────────────────────────────────────────────────────
 *  Within each group, items use order = 10/20/30/… in their natural sequence
 *  so plugins can insert with order 15/25 without colliding.
 */
import {
  SparkAgentLine,
  SparkBarChartLine,
  SparkBookLine,
  SparkConfigLine,
  SparkDataLine,
  SparkDateLine,
  SparkDebugLine,
  SparkLocalFileLine,
  SparkLockLine,
  SparkMagicWandLine,
  SparkMcpMcpLine,
  SparkMessageLine,
  SparkMicLine,
  SparkModePlazaLine,
  SparkPluginLine,
  SparkSaveLine,
  SparkScanLine,
  SparkToolLine,
  SparkUserGroupLine,
  SparkVariableSettingLine,
  SparkVoiceChat01Line,
  SparkWifiLine,
} from "@agentscope-ai/icons";
import { menuRegistry } from "../../plugins/registry/store";
import type { MenuItem } from "../../plugins/registry/types";

// 中文导航标签映射
const NAV_LABELS: Record<string, string> = {
  "nav.msg": "消息",
  "nav.control": "控制",
  "nav.channels": "频道",
  "nav.sessions": "会话",
  "nav.cronJobs": "定时任务",
  "nav.heartbeat": "心跳",
  "nav.agent": "工作区",
  "nav.workspace": "文件",
  "nav.skills": "技能",
  "nav.tools": "工具",
  "nav.mcp": "MCP",
  "nav.acp": "ACP",
  "nav.agentConfig": "运行配置",
  "nav.agentStats": "智能体统计",
  "nav.sage": "经验成长",
  "nav.tenancy": "企业空间",
  "nav.settings": "设置",
  "nav.agents": "智能体管理",
  "nav.models": "模型",
  "nav.environments": "环境变量",
  "nav.security": "安全",
  "nav.tokenUsage": "Token 消耗",
  "nav.backups": "备份",
  "nav.voiceTranscription": "语音转写",
  "nav.debug": "调试",
  "nav.pluginManager": "插件管理",
};

// 更新 navLabel 函数以使用中文标签
const navLabelWithChinese =
  (_key: string, defaultValue?: string) => (): string =>
    defaultValue ?? NAV_LABELS[_key] ?? _key;

export const BUILTIN_MENU: MenuItem[] = [
  // ── Agent-scoped (Sidebar Menu #1) ───────────────────────────────────────
  {
    id: "core.msg",
    location: "primary.agentScoped",
    label: navLabelWithChinese("nav.msg"),
    icon: SparkMessageLine,
    route: "core.msg",
    order: 10,
  },

  // control-group
  {
    id: "core.control-group",
    location: "primary.agentScoped",
    label: navLabelWithChinese("nav.control"),
    isGroup: true,
    order: 20,
  },
  {
    id: "core.channels",
    location: "primary.agentScoped",
    parentId: "core.control-group",
    label: navLabelWithChinese("nav.channels"),
    icon: SparkWifiLine,
    route: "core.channels",
    order: 10,
  },
  {
    id: "core.sessions",
    location: "primary.agentScoped",
    parentId: "core.control-group",
    label: navLabelWithChinese("nav.sessions"),
    icon: SparkUserGroupLine,
    route: "core.sessions",
    order: 20,
  },
  {
    id: "core.cron-jobs",
    location: "primary.agentScoped",
    parentId: "core.control-group",
    label: navLabelWithChinese("nav.cronJobs"),
    icon: SparkDateLine,
    route: "core.cron-jobs",
    order: 30,
  },
  {
    id: "core.heartbeat",
    location: "primary.agentScoped",
    parentId: "core.control-group",
    label: navLabelWithChinese("nav.heartbeat"),
    icon: SparkVoiceChat01Line,
    route: "core.heartbeat",
    order: 40,
  },

  // agent-group
  {
    id: "core.agent-group",
    location: "primary.agentScoped",
    label: navLabelWithChinese("nav.agent"),
    isGroup: true,
    order: 30,
  },
  {
    id: "core.workspace",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.workspace"),
    icon: SparkLocalFileLine,
    route: "core.workspace",
    order: 10,
  },
  {
    id: "core.skills",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.skills"),
    icon: SparkMagicWandLine,
    route: "core.skills",
    order: 20,
  },
  {
    id: "core.tools",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.tools"),
    icon: SparkToolLine,
    route: "core.tools",
    order: 30,
  },
  {
    id: "core.mcp",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.mcp"),
    icon: SparkMcpMcpLine,
    route: "core.mcp",
    order: 40,
  },
  {
    id: "core.acp",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.acp"),
    icon: SparkScanLine,
    route: "core.acp",
    order: 50,
  },
  {
    id: "core.agent-config",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.agentConfig"),
    icon: SparkConfigLine,
    route: "core.agent-config",
    order: 60,
  },
  {
    id: "core.agent-stats",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.agentStats"),
    icon: SparkBarChartLine,
    route: "core.agent-stats",
    order: 70,
  },
  {
    id: "core.sage",
    location: "primary.agentScoped",
    parentId: "core.agent-group",
    label: navLabelWithChinese("nav.sage"),
    icon: SparkBookLine,
    route: "core.sage",
    order: 80,
  },

  // ── Settings (Sidebar Menu #2) ───────────────────────────────────────────
  {
    id: "core.settings-group",
    location: "primary.settings",
    label: navLabelWithChinese("nav.settings"),
    isGroup: true,
    order: 10,
  },
  {
    id: "core.agents",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.agents"),
    icon: SparkAgentLine,
    route: "core.agents",
    order: 10,
  },
  {
    id: "core.tenancy",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.tenancy"),
    icon: SparkUserGroupLine,
    route: "core.tenancy",
    order: 15,
  },
  {
    id: "core.models",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.models"),
    icon: SparkModePlazaLine,
    route: "core.models",
    order: 20,
  },
  {
    id: "core.environments",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.environments"),
    icon: SparkVariableSettingLine,
    route: "core.environments",
    order: 50,
  },
  {
    id: "core.security",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.security"),
    icon: SparkLockLine,
    route: "core.security",
    order: 60,
  },
  {
    id: "core.token-usage",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.tokenUsage"),
    icon: SparkDataLine,
    route: "core.token-usage",
    order: 70,
  },
  {
    id: "core.backups",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.backups"),
    icon: SparkSaveLine,
    route: "core.backups",
    order: 80,
  },
  {
    id: "core.voice-transcription",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.voiceTranscription"),
    icon: SparkMicLine,
    route: "core.voice-transcription",
    order: 90,
  },
  {
    id: "core.debug",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.debug", "调试"),
    icon: SparkDebugLine,
    route: "core.debug",
    order: 100,
  },
  {
    id: "core.plugin-manager",
    location: "primary.settings",
    parentId: "core.settings-group",
    label: navLabelWithChinese("nav.pluginManager", "插件管理"),
    icon: SparkPluginLine,
    route: "core.plugin-manager",
    order: 110,
  },
];

// Self-register at module load. main.tsx imports this file as a side-effect.
menuRegistry.addBuiltin(BUILTIN_MENU);
