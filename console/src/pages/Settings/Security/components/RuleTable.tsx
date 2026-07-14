import { useMemo } from "react";
import {
  Table,
  Tag,
  Switch,
  Button,
  Tooltip,
  Collapse,
} from "@agentscope-ai/design";
import { Space } from "antd";
import { Eye, Pencil, Trash2 } from "lucide-react";
import type { MergedRule } from "../useToolGuard";
import { useTheme } from "../../../../contexts/ThemeContext";
import styles from "../index.module.less";

const CATEGORY_LABELS: Record<string, string> = {
  command_injection: "命令注入",
  code_execution: "代码执行",
  data_exfiltration: "数据外泄",
  path_traversal: "路径穿越",
  sensitive_file_access: "敏感文件访问",
  network_abuse: "网络滥用",
  credential_exposure: "凭证泄露",
  resource_abuse: "资源滥用",
  privilege_escalation: "权限提升",
  prompt_injection: "提示注入",
  other: "其他",
};

const RULE_DESCRIPTIONS: Record<string, string> = {
  TOOL_CMD_DANGEROUS_RM: "检测可能导致数据丢失的 rm 命令",
  TOOL_CMD_DANGEROUS_MV: "检测可能意外移动或覆盖文件的 mv 命令",
  TOOL_CMD_FS_DESTRUCTION: "检测低级别磁盘格式化或擦除命令",
  TOOL_CMD_DOS_FORK_BOMB: "检测经典 Bash Fork 炸弹和批量进程终止",
  TOOL_CMD_PIPE_TO_SHELL: "检测通过 'curl | bash' 模式下载并立即执行远程载荷的行为",
  TOOL_CMD_REVERSE_SHELL: "检测建立反向 Shell 或未授权网络隧道的行为",
  TOOL_CMD_SYSTEM_TAMPERING: "检测对定时任务、SSH 密钥或 sudo 权限的访问（包括读取和修改）",
  TOOL_CMD_UNSAFE_PERMISSIONS: "检测全局权限降级（chmod 777）或设置不可变标志的操作",
  TOOL_CMD_OBFUSCATED_EXEC: "检测将 base64 编码字符串直接传递给 Shell 解释器执行的行为",
  TOOL_CMD_SYSTEM_REBOOT: "检测将终止主机系统的系统重启或关机命令",
  TOOL_CMD_SERVICE_RESTART: "检测可能中断系统服务的服务管理命令",
  TOOL_CMD_PROCESS_KILL: "检测可能终止关键进程的进程终止命令",
  TOOL_CMD_PRIVILEGE_ESCALATION: "检测使用 sudo、su、doas、pkexec 或 runas 的权限提升尝试",
};

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "red",
  HIGH: "orange",
  MEDIUM: "gold",
  LOW: "blue",
  INFO: "default",
};

interface RuleTableProps {
  rules: MergedRule[];
  enabled: boolean;
  onToggleRule: (ruleId: string, currentlyDisabled: boolean) => void;
  onToggleAutoDeny: (ruleId: string, currentlyAutoDeny: boolean) => void;
  onPreviewRule: (rule: MergedRule) => void;
  onEditRule: (rule: MergedRule) => void;
  onDeleteRule: (ruleId: string) => void;
}

function groupRulesByCategory(
  rules: MergedRule[],
): Record<string, MergedRule[]> {
  const groups: Record<string, MergedRule[]> = {};
  for (const rule of rules) {
    const category = rule.category || "other";
    if (!groups[category]) {
      groups[category] = [];
    }
    groups[category].push(rule);
  }
  return groups;
}

export function RuleTable({
  rules,
  enabled,
  onToggleRule,
  onToggleAutoDeny,
  onPreviewRule,
  onEditRule,
  onDeleteRule,
}: RuleTableProps) {
    const { isDark } = useTheme();
  const darkBtnStyle = isDark ? { color: "rgba(255,255,255,0.75)" } : undefined;

  const groupedRules = useMemo(() => groupRulesByCategory(rules), [rules]);

  const columns = [
    {
      title: "规则 ID",
      dataIndex: "id",
      key: "id",
      width: 280,
      render: (id: string, record: MergedRule) => (
        <span style={{ opacity: record.disabled ? 0.4 : 1 }}>{id}</span>
      ),
    },
    {
      title: "严重程度",
      dataIndex: "severity",
      key: "severity",
      width: 100,
      render: (sev: string, record: MergedRule) => (
        <Tag
          color={SEVERITY_COLORS[sev] ?? "default"}
          style={{ opacity: record.disabled ? 0.4 : 1 }}
        >
          {sev}
        </Tag>
      ),
    },
    {
      title: "描述",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (_text: string, record: MergedRule) => {
        const i18nKey = `security.rules.descriptions.${record.id}`;
        const translated = RULE_DESCRIPTIONS[i18nKey.replace("security.rules.descriptions.", "")] || "";
        const display = translated || record.description;
        return (
          <Tooltip title={display}>
            <span
              style={{
                opacity: record.disabled ? 0.4 : 1,
                display: "block",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {display}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 100,
      render: (source: string, record: MergedRule) => (
        <Tag
          color={source === "builtin" ? "rgba(142, 140, 153, 1)" : "green"}
          style={{ opacity: record.disabled ? 0.4 : 1 }}
        >
          {source === "builtin"
            ? "内置"
            : "自定义"}
        </Tag>
      ),
    },
    {
      title: (
        <Tooltip title={"启用后，匹配此规则的工具调用将被自动拒绝，无需人工审批"}>
          <span>{"自动拒绝"}</span>
        </Tooltip>
      ),
      key: "autoDeny",
      width: 100,
      render: (_: unknown, record: MergedRule) => (
        <Tooltip
          title={
            record.autoDeny
              ? "关闭此规则的自动拒绝"
              : "启用此规则的自动拒绝"
          }
        >
          <Switch
            size="small"
            checked={record.autoDeny}
            onChange={() => onToggleAutoDeny(record.id, record.autoDeny)}
            disabled={!enabled || record.disabled}
          />
        </Tooltip>
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 100,
      render: (_: unknown, record: MergedRule) => (
        <Space size="small">
          <Tooltip
            title={
              record.disabled
                ? "启用"
                : "禁用"
            }
          >
            <Switch
              size="small"
              checked={!record.disabled}
              onChange={() => onToggleRule(record.id, record.disabled)}
              disabled={!enabled}
            />
          </Tooltip>
          {record.source === "builtin" && (
            <Button
              type="text"
              size="small"
              onClick={() => onPreviewRule(record)}
              disabled={!enabled}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                ...darkBtnStyle,
              }}
            >
              <Eye size={16} />
            </Button>
          )}
          {record.source === "custom" && (
            <>
              <Tooltip title={"编辑"}>
                <Button
                  type="text"
                  size="small"
                  icon={<Pencil size={14} />}
                  onClick={() => onEditRule(record)}
                  disabled={!enabled}
                  style={darkBtnStyle}
                />
              </Tooltip>
              <Tooltip title={"删除"}>
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<Trash2 size={14} />}
                  onClick={() => onDeleteRule(record.id)}
                  disabled={!enabled}
                />
              </Tooltip>
            </>
          )}
        </Space>
      ),
    },
  ];

  const categoryKeys = Object.keys(groupedRules);

  const collapseItems = categoryKeys.map((category) => {
    const categoryRules = groupedRules[category];
    const enabledCount = categoryRules.filter((r) => !r.disabled).length;
    const totalCount = categoryRules.length;
    const categoryLabel =
      CATEGORY_LABELS[category] ||
      category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

    return {
      key: category,
      label: (
        <span className={styles.collapseCategoryLabel}>
          {categoryLabel}
          <Tag style={{ marginLeft: 8 }}>
            {enabledCount}/{totalCount}
          </Tag>
        </span>
      ),
      children: (
        <Table
          dataSource={categoryRules}
          columns={columns}
          rowKey="id"
          pagination={false}
          size="small"
          className={styles.ruleTable}
        />
      ),
    };
  });

  return (
    <Collapse
      defaultActiveKey={categoryKeys}
      items={collapseItems}
      className={styles.ruleCollapse}
    />
  );
}
