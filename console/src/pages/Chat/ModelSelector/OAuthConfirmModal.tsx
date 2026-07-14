import { useState, useEffect, useCallback, useRef } from "react";
import { Modal, Button } from "@agentscope-ai/design";
import { Loader2, ExternalLink } from "lucide-react";
import { providerApi } from "../../../api/modules/provider";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { openExternalLink } from "../../../utils/openExternalLink";

interface OAuthConfirmModalProps {
  open: boolean;
  providerId: string;
  providerName: string;
  onSuccess: () => void;
  onCancel: () => void;
}

export function OAuthConfirmModal({
  open,
  providerId,
  providerName,
  onSuccess,
  onCancel,
}: OAuthConfirmModalProps) {
    const { message } = useAppMessage();
  const [phase, setPhase] = useState<"confirm" | "waiting">("confirm");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) {
      setPhase("confirm");
      if (pollRef.current) clearInterval(pollRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    }
  }, [open]);

  const handleContinue = useCallback(async () => {
    try {
      const { authorize_url, state } = await providerApi.startOAuth(providerId);
      setPhase("waiting");

      openExternalLink(authorize_url, "_blank", "popup,width=600,height=700");

      // Poll backend status until completion (same pattern as MCP OAuth)
      pollRef.current = setInterval(async () => {
        try {
          const { status } = await providerApi.getOAuthStatus(
            providerId,
            state,
          );
          if (status === "completed") {
            if (pollRef.current) clearInterval(pollRef.current);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            message.success(
              `已成功连接 ${providerName}`,
            );
            onSuccess();
          } else if (status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            message.error("授权失败，请重试");
            onCancel();
          }
        } catch {
          // Ignore polling errors
        }
      }, 2000);

      // Timeout after 5 minutes
      timeoutRef.current = setTimeout(() => {
        if (pollRef.current) clearInterval(pollRef.current);
      }, 300000);
    } catch (err) {
      message.error(
        err instanceof Error ? err.message : "授权失败，请重试",
      );
      onCancel();
    }
  }, [providerId, providerName, onSuccess, onCancel, message]);

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      footer={null}
      closable={phase === "confirm"}
      maskClosable={phase === "confirm"}
      width={420}
    >
      {phase === "confirm" ? (
        <div style={{ textAlign: "center", padding: "16px 0" }}>
          <ExternalLink
            size={40}
            style={{ color: "#6366f1", marginBottom: 16 }}
          />
          <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 600 }}>
            {`连接 ${providerName}`}
          </h3>
          <p style={{ color: "var(--text-secondary)", margin: "0 0 24px" }}>
            {`将打开一个新的浏览器窗口以授权访问 ${providerName}，API 密钥将自动保存。`}
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
            <Button onClick={onCancel}>{"取消"}</Button>
            <Button type="primary" onClick={handleContinue}>
              {"继续"}
            </Button>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: "center", padding: "24px 0" }}>
          <Loader2
            size={32}
            style={{ color: "#6366f1", animation: "spin 1s linear infinite" }}
          />
          <h3 style={{ margin: "16px 0 8px", fontSize: 16, fontWeight: 600 }}>
            {"等待授权中..."}
          </h3>
          <p style={{ color: "var(--text-secondary)", margin: "0 0 24px" }}>
            {"请在浏览器窗口中完成授权。"}
          </p>
          <Button onClick={onCancel}>{"取消"}</Button>
        </div>
      )}
    </Modal>
  );
}
