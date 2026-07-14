import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Dropdown, Tag, Tooltip } from "antd";
import type { MenuProps } from "antd";
import { Shield, Ban, AlertTriangle, CheckCircle } from "lucide-react";
import { DownOutlined } from "@ant-design/icons";

export type ToolExecutionLevel = "STRICT" | "SMART" | "AUTO" | "OFF";

const LEVELS: readonly ToolExecutionLevel[] = [
  "STRICT",
  "SMART",
  "AUTO",
  "OFF",
];

const LEVEL_META: Record<
  ToolExecutionLevel,
  { color: string; icon: React.ReactNode }
> = {
  STRICT: { color: "#ff4d4f", icon: <Ban size={12} /> },
  SMART: { color: "#faad14", icon: <AlertTriangle size={12} /> },
  AUTO: { color: "#1890ff", icon: <Shield size={12} /> },
  OFF: { color: "#52c41a", icon: <CheckCircle size={12} /> },
};

function storageKey(chatId: string): string {
  return `approval_level-${chatId}`;
}

function normalizeLevel(raw: string | undefined): ToolExecutionLevel {
  const upper = (raw || "AUTO").toUpperCase();
  return LEVELS.includes(upper as ToolExecutionLevel)
    ? (upper as ToolExecutionLevel)
    : "AUTO";
}

interface ApprovalLevelToggleProps {
  /** Use queueSessionId (chatId ?? "new") for consistent storage key */
  sessionId: string;
  /** Default level from GET /workspace/running-config */
  runningConfigApprovalLevel: ToolExecutionLevel;
  /** null = no session override, backend uses running-config */
  onChange?: (sessionOverride: ToolExecutionLevel | null) => void;
}

const ApprovalLevelToggle: React.FC<ApprovalLevelToggleProps> = ({
  sessionId,
  runningConfigApprovalLevel,
  onChange,
}) => {
    const [sessionLevel, setSessionLevel] = useState<ToolExecutionLevel | null>(
    null,
  );
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const prevSessionIdRef = useRef<string>(sessionId);

  useEffect(() => {
    const prevSessionId = prevSessionIdRef.current;

    // Migrate from temporary sessionId (including "new" or localId) to real backend chatId
    // This happens when:
    // 1. "new" -> real UUID (first message sent)
    // 2. localId (timestamp-random) -> real UUID (session resolved)
    if (prevSessionId !== sessionId) {
      const isLocalId = (id: string) =>
        id === "new" || /^\d{13}-[a-z0-9]{7}$/.test(id);
      const isRealId = (id: string) => id.length === 36 && id.includes("-");

      // Migrate if transitioning from local/temp to real
      if (isLocalId(prevSessionId) && isRealId(sessionId)) {
        const prevLevel = localStorage.getItem(storageKey(prevSessionId));
        if (prevLevel && LEVELS.includes(prevLevel as ToolExecutionLevel)) {
          localStorage.setItem(storageKey(sessionId), prevLevel);
          localStorage.removeItem(storageKey(prevSessionId));
        }
      }
    }

    prevSessionIdRef.current = sessionId;

    const saved = localStorage.getItem(storageKey(sessionId));
    if (saved && LEVELS.includes(saved as ToolExecutionLevel)) {
      setSessionLevel(saved as ToolExecutionLevel);
    } else {
      setSessionLevel(null);
    }
  }, [sessionId]);

  const effectiveLevel = sessionLevel ?? runningConfigApprovalLevel;
  const meta = LEVEL_META[effectiveLevel];

  useEffect(() => {
    onChangeRef.current?.(sessionLevel);
  }, [sessionLevel]);

  const handleSelect = useCallback(
    (level: ToolExecutionLevel) => {
      setSessionLevel(level);
      localStorage.setItem(storageKey(sessionId), level);
      onChangeRef.current?.(level);
    },
    [sessionId],
  );

  const menuItems: MenuProps["items"] = useMemo(() => {
    const items: MenuProps["items"] = [];

    for (const lv of LEVELS) {
      const m = LEVEL_META[lv];
      const name = lv === "STRICT" ? "严格模式" : lv === "SMART" ? "智能模式" : lv === "AUTO" ? "自动模式" : "关闭模式";
      const desc = lv === "STRICT" ? "所有工具调用都需要审批，最高安全级别" : lv === "SMART" ? "低风险工具自动放行，中高风险工具需要审批" : lv === "AUTO" ? "仅被明确标记为需要审批的工具才会要求审批（默认）" : "关闭所有工具审批，所有工具自动执行";
      items.push({
        key: lv,
        label: (
          <div>
            <div>{name}</div>
            {desc && (
              <div style={{ fontSize: 12, color: "#999", marginTop: 2 }}>
                {desc}
              </div>
            )}
          </div>
        ),
        icon: React.cloneElement(m.icon as React.ReactElement, {
          style: { color: m.color, marginTop: desc ? 4 : 0 },
        }),
        onClick: () => handleSelect(lv),
      });
    }

    return items;
  }, [handleSelect]);

  return (
    <Tooltip title={"工具执行安全"}>
      <Dropdown
        menu={{ items: menuItems, selectedKeys: [effectiveLevel] }}
        trigger={["click"]}
      >
        <Tag
          style={{
            cursor: "pointer",
            userSelect: "none",
            borderColor: meta.color,
            color: meta.color,
            transition: "all 0.2s",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            lineHeight: "22px",
          }}
        >
          {meta.icon}
          {effectiveLevel === "STRICT" ? "严格模式" : effectiveLevel === "SMART" ? "智能模式" : effectiveLevel === "AUTO" ? "自动模式" : "关闭模式"}
          <DownOutlined style={{ fontSize: 10 }} />
        </Tag>
      </Dropdown>
    </Tooltip>
  );
};

export { normalizeLevel };
export default ApprovalLevelToggle;
