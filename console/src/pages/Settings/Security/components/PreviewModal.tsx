import { Modal, Button, Tag } from "@agentscope-ai/design";
import type { ToolGuardRule } from "../../../../api/modules/security";
import { useTheme } from "../../../../contexts/ThemeContext";

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

interface PreviewModalProps {
  rule: ToolGuardRule | null;
  onClose: () => void;
}

export function PreviewModal({ rule, onClose }: PreviewModalProps) {
    const { isDark } = useTheme();

  if (!rule) return null;

  const preStyle: React.CSSProperties = {
    background: isDark ? "#1a1a1a" : "#f5f5f5",
    color: isDark ? "rgba(255,255,255,0.85)" : "#333",
    padding: 12,
    borderRadius: 6,
    fontSize: 13,
    border: isDark ? "1px solid rgba(255,255,255,0.12)" : "1px solid #e8e8e8",
  };

  return (
    <Modal
      title={"规则详情"}
      open={!!rule}
      onCancel={onClose}
      footer={<Button onClick={onClose}>{"关闭"}</Button>}
      width={640}
    >
      <div style={{ marginTop: 16 }}>
        <p>
          <strong>{"规则 ID"}:</strong> {rule.id}
        </p>
        <p>
          <strong>{"严重程度"}:</strong>{" "}
          <Tag color={SEVERITY_COLORS[rule.severity] ?? "default"}>
            {rule.severity}
          </Tag>
        </p>
        <p>
          <strong>{"目标工具"}:</strong>{" "}
          {rule.tools.length > 0
            ? rule.tools.join(", ")
            : "所有工具"}
        </p>
        <p>
          <strong>{"目标参数"}:</strong>{" "}
          {rule.params.length > 0
            ? rule.params.join(", ")
            : "所有参数"}
        </p>
        <p>
          <strong>{"触发行为"}:</strong>{" "}
          <Tag color="orange">{"等待审批"}</Tag>
        </p>
        <p style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          <strong>{"描述"}:</strong>{" "}
          {RULE_DESCRIPTIONS[rule.id] || rule.description}
        </p>
        <p>
          <strong>{"正则模式"}:</strong>
        </p>
        <pre style={preStyle}>{rule.patterns.join("\n")}</pre>
        {rule.exclude_patterns.length > 0 && (
          <>
            <p>
              <strong>{"排除模式"}:</strong>
            </p>
            <pre style={preStyle}>{rule.exclude_patterns.join("\n")}</pre>
          </>
        )}
      </div>
    </Modal>
  );
}
