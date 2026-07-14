import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, Card, Tag, Typography, Space } from "antd";
import { Shield, Check, X, Clock, Copy, Info } from "lucide-react";
import { useAgentStore } from "../../stores/agentStore";
import { getAgentDisplayName } from "../../utils/agentDisplayName";
import styles from "./ApprovalCard.module.less";

const { Text } = Typography;

export interface ApprovalCardProps {
  requestId: string;
  toolName: string;
  toolSource?: string;
  severity: string;
  findingsCount: number;
  findingsSummary: string;
  toolParams: Record<string, unknown>;
  createdAt: number;
  timeoutSeconds: number;
  agentId: string;
  ownerAgentId?: string;
  showMsgAgentContext?: boolean;
  sessionId?: string;
  rootSessionId?: string;
  // Approval-scope choice (console-only). When true the card renders
  // Approve Pattern + Approve Exact; when false, a single Approve button.
  isGeneralized?: boolean;
  exactTarget?: string;
  similarTarget?: string;
  onApprove: (requestId: string, scope?: "exact" | "similar") => Promise<void>;
  onDeny: (requestId: string) => Promise<void>;
  onCancel?: () => void;
  onAcknowledge?: (requestId: string) => Promise<void>;
}

export function ApprovalCard({
  requestId,
  toolName,
  toolSource,
  severity,
  findingsCount,
  findingsSummary,
  toolParams,
  createdAt,
  timeoutSeconds,
  agentId,
  ownerAgentId,
  showMsgAgentContext = false,
  sessionId,
  rootSessionId,
  isGeneralized,
  exactTarget,
  similarTarget,
  onApprove,
  onDeny,
  onAcknowledge,
}: ApprovalCardProps) {
    const agents = useAgentStore((state) => state.agents);
  const agentsById = useMemo(
    () => new Map(agents.map((agent) => [agent.id, agent])),
    [agents],
  );
  const [loading, setLoading] = useState<
    "approve-pattern" | "approve-exact" | "deny" | "acknowledge" | null
  >(null);
  const [remaining, setRemaining] = useState<number>(timeoutSeconds);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleCopy = useCallback(async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 1500);
    } catch {
      /* clipboard not available */
    }
  }, []);

  // Check if this is a cross-session approval
  const isCrossSession =
    sessionId && rootSessionId && sessionId !== rootSessionId;
  const isTimedOut = showMsgAgentContext && remaining <= 0;
  const executionAgentDisplayName = useMemo(() => {
    const matched = agentsById.get(agentId);
    if (matched) return getAgentDisplayName(matched);
    return agentId || "Unknown";
  }, [agentsById, agentId]);
  const ownerAgentDisplayName = useMemo(() => {
    const ownerId = ownerAgentId || agentId;
    const matched = agentsById.get(ownerId);
    if (matched) return getAgentDisplayName(matched);
    return ownerId || "Unknown";
  }, [agentsById, ownerAgentId, agentId]);
  const shouldShowExecutionAgent =
    showMsgAgentContext && Boolean(isCrossSession);
  const displayToolSource =
    toolSource && toolSource !== "builtin"
      ? toolSource
      : "内置";

  useEffect(() => {
    const elapsed = Date.now() / 1000 - createdAt;
    const initialRemaining = Math.max(0, Math.floor(timeoutSeconds - elapsed));
    setRemaining(initialRemaining);

    const timer = setInterval(() => {
      const newElapsed = Date.now() / 1000 - createdAt;
      const newRemaining = Math.max(0, Math.floor(timeoutSeconds - newElapsed));
      setRemaining(newRemaining);

      if (newRemaining <= 0) {
        clearInterval(timer);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [createdAt, timeoutSeconds]);

  const handleApprove = async (scope?: "exact" | "similar") => {
    const loadingKey =
      scope === "similar" ? "approve-pattern" : "approve-exact";
    console.log(
      "[ApprovalCard] Approve button clicked:",
      requestId,
      "scope:",
      scope,
    );
    setLoading(loadingKey);
    try {
      await onApprove(requestId, scope);
      console.log("[ApprovalCard] onApprove completed");
    } catch (err) {
      console.error("[ApprovalCard] onApprove failed:", err);
    } finally {
      setLoading(null);
    }
  };

  const handleDeny = async () => {
    setLoading("deny");
    try {
      await onDeny(requestId);
    } finally {
      setLoading(null);
    }
  };

  const handleAcknowledge = async () => {
    if (!onAcknowledge) return;
    setLoading("acknowledge");
    try {
      await onAcknowledge(requestId);
    } finally {
      setLoading(null);
    }
  };

  const getSeverityColor = (sev: string) => {
    const s = sev.toLowerCase();
    if (s === "critical" || s === "high") return "error";
    if (s === "medium") return "warning";
    return "default";
  };

  return (
    <Card className={styles.approvalCard} bordered={false}>
      <div className={styles.header}>
        <Space size={8} align="center" className={styles.titleRow}>
          <Shield size={16} className={styles.icon} />
          <Text className={styles.title}>
            {"安全审批"}
          </Text>
        </Space>
        <Space size={6} align="center" className={styles.timer}>
          <Clock size={14} className={styles.timerIcon} />
          <Text className={styles.timerText}>
            {Math.floor(remaining / 60)}:
            {String(remaining % 60).padStart(2, "0")}
          </Text>
        </Space>
      </div>

      <div className={styles.content}>
        {showMsgAgentContext ? (
          <>
            <div className={styles.infoRow}>
              <Text className={styles.label}>
                {"归属Agent"}:
              </Text>
              <Tag color="success" className={styles.ownerAgentTag}>
                {ownerAgentDisplayName}
              </Tag>
            </div>
            {shouldShowExecutionAgent ? (
              <div className={styles.infoRow}>
                <Text className={styles.label}>
                  {"执行Agent"}:
                </Text>
                <Tag color="blue" className={styles.crossSessionTag}>
                  {executionAgentDisplayName}
                </Tag>
              </div>
            ) : null}
          </>
        ) : null}

        <div className={styles.infoRow}>
          <Text className={styles.label}>{"工具"}:</Text>
          <Text className={styles.value} code>
            {toolName}
          </Text>
        </div>

        <div className={styles.infoRow}>
          <Text className={styles.label}>
            {"来源"}:
          </Text>
          <Text className={styles.value} code>
            {displayToolSource}
          </Text>
        </div>

        <div className={styles.infoRow}>
          <Text className={styles.label}>
            {"严重性"}:
          </Text>
          <Tag
            color={getSeverityColor(severity)}
            className={styles.severityTag}
          >
            {severity.toUpperCase()}
          </Tag>
        </div>

        <div className={styles.infoRow}>
          <Text className={styles.label}>
            {"发现"}:
          </Text>
          <Text className={styles.value}>{findingsCount}</Text>
        </div>

        {isCrossSession && !showMsgAgentContext && (
          <div className={styles.infoRow}>
            <Text className={styles.label}>
              {"来源"}:
            </Text>
            <Tag color="blue" className={styles.crossSessionTag}>
              {"子Agent"} ({sessionId?.slice(0, 8)})
            </Tag>
          </div>
        )}

        {isGeneralized && (exactTarget || similarTarget) && (
          <div className={styles.scopeSection}>
            <Text className={styles.scopeLabel}>
              {"批准范围"}:
            </Text>
            <div className={styles.scopeItems}>
              <div className={styles.scopeItem}>
                <Text className={styles.scopeItemLabel}>
                  {"仅本次"}:
                </Text>
                <code className={styles.scopeCode}>{exactTarget}</code>
              </div>
              <div className={styles.scopeItem}>
                <Text className={styles.scopeItemLabel}>
                  {"总是允许"}:
                </Text>
                <code className={styles.scopeCode}>{similarTarget}</code>
              </div>
            </div>
          </div>
        )}

        {toolParams && Object.keys(toolParams).length > 0 && (
          <details className={styles.paramsDetails}>
            <summary className={styles.paramsSummary}>
              {"参数"}
            </summary>
            <div className={styles.paramsCodeWrapper}>
              <pre className={styles.paramsCode}>
                {JSON.stringify(toolParams, null, 2)}
              </pre>
              <button
                className={`${styles.copyButton} ${
                  copiedField === "params" ? styles.copied : ""
                }`}
                onClick={() =>
                  handleCopy(JSON.stringify(toolParams, null, 2), "params")
                }
                title={"复制"}
              >
                <Copy size={12} />
              </button>
            </div>
          </details>
        )}

        {findingsSummary && (
          <details className={styles.detailsSection}>
            <summary className={styles.detailsSummary}>
              <Info size={12} />
              {"详细信息"}
            </summary>
            <div className={styles.detailsContent}>
              <pre className={styles.detailsText}>{findingsSummary}</pre>
              <button
                className={`${styles.copyButton} ${
                  copiedField === "details" ? styles.copied : ""
                }`}
                onClick={() => handleCopy(findingsSummary, "details")}
                title={"复制"}
              >
                <Copy size={12} />
              </button>
            </div>
          </details>
        )}
      </div>

      <div className={styles.actions}>
        {isTimedOut ? (
          <>
            <Text className={styles.timeoutHint}>
              {"已超时，自动拒绝"}
            </Text>
            {onAcknowledge ? (
              <Button
                type="primary"
                onClick={handleAcknowledge}
                loading={loading === "acknowledge"}
                disabled={loading !== null}
              >
                {"我知道了"}
              </Button>
            ) : null}
          </>
        ) : (
          <>
            <Button
              danger
              icon={<X size={14} />}
              onClick={handleDeny}
              loading={loading === "deny"}
              disabled={loading !== null}
              className={styles.denyButton}
            >
              {"拒绝"}
            </Button>
            {isGeneralized ? (
              <>
                <Button
                  onClick={() => handleApprove("exact")}
                  loading={loading === "approve-exact"}
                  disabled={loading !== null}
                  className={styles.approveOnceButton}
                >
                  {"仅本次"}
                </Button>
                <Button
                  type="primary"
                  icon={<Check size={14} />}
                  onClick={() => handleApprove("similar")}
                  loading={loading === "approve-pattern"}
                  disabled={loading !== null}
                  className={styles.approveAlwaysButton}
                >
                  {"总是允许"}
                </Button>
              </>
            ) : (
              <Button
                type="primary"
                icon={<Check size={14} />}
                onClick={() => handleApprove()}
                loading={
                  loading === "approve-exact" || loading === "approve-pattern"
                }
                disabled={loading !== null}
                className={styles.approveAlwaysButton}
              >
                {"批准"}
              </Button>
            )}
          </>
        )}
      </div>
    </Card>
  );
}
