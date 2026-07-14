import { Card, Button, Modal, Tooltip, Input } from "@agentscope-ai/design";
import type { MCPAccessPolicy, MCPClientInfo } from "../../../../api/types";
import React, { useState } from "react";
import { useTheme } from "../../../../contexts/ThemeContext";
import {
  EyeOutlined,
  EyeInvisibleOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { ShieldCheck, ShieldAlert, ShieldX, KeyRound } from "lucide-react";
import { MCPAccessModal } from "./MCPAccessModal";
import { MCPOAuthSection } from "./MCPOAuthSection";
import styles from "../index.module.less";

interface MCPClientUpdate {
  name?: string;
  description?: string;
  command?: string;
  enabled?: boolean;
  transport?: "stdio" | "streamable_http" | "sse";
  url?: string;
  headers?: Record<string, string>;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
}

interface MCPClientCardProps {
  client: MCPClientInfo;
  onToggle: (client: MCPClientInfo, e: React.MouseEvent) => void;
  onDelete: (client: MCPClientInfo, e: React.MouseEvent) => void;
  onUpdate: (key: string, updates: MCPClientUpdate) => Promise<boolean>;
  onUpdatePolicy: (key: string, policy: MCPAccessPolicy) => Promise<boolean>;
  onRefresh?: () => Promise<void>;
}

export const MCPClientCard = React.memo(function MCPClientCard({
  client,
  onToggle,
  onDelete,
  onUpdate,
  onUpdatePolicy,
  onRefresh,
}: MCPClientCardProps) {
    const { isDark } = useTheme();
  const [isHovered, setIsHovered] = useState(false);
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [accessModalOpen, setAccessModalOpen] = useState(false);
  const [editedJson, setEditedJson] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [oauthModalOpen, setOauthModalOpen] = useState(false);
  const [oauthClientId, setOauthClientId] = useState("");
  const [oauthScope, setOauthScope] = useState(
    client.oauth_status?.scope || "",
  );
  const [oauthAuthEndpoint, setOauthAuthEndpoint] = useState("");
  const [oauthTokenEndpoint, setOauthTokenEndpoint] = useState("");

  // Determine if MCP client is remote or local based on command
  const isRemote =
    client.transport === "streamable_http" || client.transport === "sse";
  const clientType = isRemote ? "Remote" : "Local";

  const oauthStatus = client.oauth_status;
  const now = Date.now() / 1000;
  const isOauthAuthorized =
    !!oauthStatus?.authorized && oauthStatus.expires_at > now;
  const isOauthExpired =
    !!oauthStatus?.authorized && oauthStatus.expires_at <= now;
  const hasOauth = !!oauthStatus;

  const handleToggleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggle(client, e);
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    setDeleteModalOpen(false);
    onDelete(client, null as unknown as React.MouseEvent);
  };

  const handleCardClick = () => {
    const jsonStr = JSON.stringify(client, null, 2);
    setEditedJson(jsonStr);
    setIsEditing(false);
    setJsonModalOpen(true);
  };

  const handleSaveJson = async () => {
    try {
      const parsed = JSON.parse(editedJson) as MCPClientUpdate & {
        key?: unknown;
      };
      const updates = { ...parsed };
      delete updates.key;

      // Send all updates directly to backend, let backend handle env masking check
      const success = await onUpdate(client.key, updates);
      if (success) {
        setJsonModalOpen(false);
        setIsEditing(false);
      }
    } catch {
      alert("Invalid JSON format");
    }
  };

  const clientJson = JSON.stringify(client, null, 2);

  return (
    <>
      <Card
        hoverable
        onClick={handleCardClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        className={`${styles.mcpCard} ${
          client.enabled ? styles.enabledCard : ""
        } ${isHovered ? styles.hover : styles.normal}`}
      >
        <div className={styles.cardHeader}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              minWidth: 0,
            }}
          >
            <Tooltip title={client.name}>
              <h3 className={styles.mcpTitle}>{client.name}</h3>
            </Tooltip>
            <span
              className={`${styles.typeBadge} ${
                isRemote ? styles.remote : styles.local
              }`}
            >
              {clientType}
            </span>
            {hasOauth && isOauthExpired && (
              <Tooltip title={"授权已过期"}>
                <ShieldAlert
                  size={13}
                  style={{ color: "#e67e22", flexShrink: 0 }}
                />
              </Tooltip>
            )}
            {hasOauth && isOauthAuthorized && (
              <Tooltip title={"已授权"}>
                <ShieldCheck
                  size={13}
                  style={{ color: "#27ae60", flexShrink: 0 }}
                />
              </Tooltip>
            )}
            {hasOauth && !isOauthAuthorized && !isOauthExpired && (
              <Tooltip title={"未授权"}>
                <ShieldX
                  size={13}
                  style={{ color: "#7f8c8d", flexShrink: 0 }}
                />
              </Tooltip>
            )}
          </div>
          <div className={styles.statusContainer}>
            <span className={styles.statusDot} />
            <span className={styles.statusText}>
              {client.enabled ? "已启用" : "已禁用"}
            </span>
          </div>
        </div>

        <p className={styles.mcpDescription}>{client.description || "-"}</p>

        <div className={styles.cardFooter}>
          <Button
            className={styles.toolsButton}
            onClick={(e) => {
              e.stopPropagation();
              setAccessModalOpen(true);
            }}
            icon={<ToolOutlined />}
          >
            {"工具&权限"}
          </Button>
          <div
            className={`${styles.cardSecondaryActions} ${
              isRemote
                ? styles.cardSecondaryActionsThree
                : styles.cardSecondaryActionsTwo
            }`}
          >
            {isRemote && (
              <Button
                className={styles.toggleButton}
                onClick={(e) => {
                  e.stopPropagation();
                  setOauthModalOpen(true);
                }}
                style={
                  isOauthAuthorized
                    ? {
                        color: "#27ae60",
                        borderColor: "#27ae60",
                        background: "rgba(39,174,96,0.06)",
                      }
                    : isOauthExpired
                    ? {
                        color: "#e67e22",
                        borderColor: "#e67e22",
                        background: "rgba(230,126,34,0.06)",
                      }
                    : undefined
                }
              >
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  {isOauthAuthorized ? (
                    <ShieldCheck size={13} />
                  ) : isOauthExpired ? (
                    <ShieldAlert size={13} />
                  ) : (
                    <KeyRound size={13} />
                  )}
                  {isOauthAuthorized
                    ? "已授权"
                    : isOauthExpired
                    ? "授权已过期"
                    : "点击授权"}
                </span>
              </Button>
            )}
            <Button
              className={styles.toggleButton}
              onClick={(e) => {
                e.stopPropagation();
                handleToggleClick(e);
              }}
              icon={client.enabled ? <EyeInvisibleOutlined /> : <EyeOutlined />}
            >
              {client.enabled ? "禁用" : "启用"}
            </Button>
            <Button
              className={styles.deleteButton}
              danger
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteClick(e);
              }}
            >
              {"删除"}
            </Button>
          </div>
        </div>
      </Card>

      <Modal
        title={"确认"}
        open={deleteModalOpen}
        onOk={confirmDelete}
        onCancel={() => setDeleteModalOpen(false)}
        okText={"确认"}
        cancelText={"取消"}
        okButtonProps={{ danger: true }}
      >
        <p>{"确定要删除此 MCP 客户端吗？"}</p>
      </Modal>

      <Modal
        title={`${client.name} - Configuration`}
        open={jsonModalOpen}
        onCancel={() => setJsonModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => setJsonModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {"取消"}
            </Button>
            {isEditing ? (
              <Button type="primary" onClick={handleSaveJson}>
                {"保存"}
              </Button>
            ) : (
              <Button type="primary" onClick={() => setIsEditing(true)}>
                {"编辑"}
              </Button>
            )}
          </div>
        }
        width={700}
      >
        <div className={styles.maskedFieldHint}>{"敏感字段已用 *** 遮掩，不支持在遮掩值上直接编辑，如需修改请替换为完整新值。"}</div>
        {isEditing ? (
          <Input.TextArea
            value={editedJson}
            onChange={(e) => setEditedJson(e.target.value)}
            autoSize={{ minRows: 15, maxRows: 25 }}
            style={{
              fontFamily: "Monaco, Courier New, monospace",
              fontSize: 13,
            }}
          />
        ) : (
          <pre
            style={{
              backgroundColor: isDark ? "#1f1f1f" : "#f5f5f5",
              color: isDark ? "rgba(255,255,255,0.85)" : "rgba(0,0,0,0.88)",
              padding: 16,
              borderRadius: 8,
              maxHeight: 400,
              overflow: "auto",
            }}
          >
            {clientJson}
          </pre>
        )}
      </Modal>

      <MCPAccessModal
        client={client}
        open={accessModalOpen}
        onClose={() => setAccessModalOpen(false)}
        onSave={(policy) => onUpdatePolicy(client.key, policy)}
      />

      {/* Dedicated OAuth modal — opened only via the Authorize button */}
      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {isOauthAuthorized ? (
              <ShieldCheck size={16} style={{ color: "#27ae60" }} />
            ) : isOauthExpired ? (
              <ShieldAlert size={16} style={{ color: "#e67e22" }} />
            ) : (
              <ShieldX size={16} style={{ color: "#7f8c8d" }} />
            )}
            {`${client.name} — ${"OAuth 授权"}`}
          </div>
        }
        open={oauthModalOpen}
        onCancel={() => setOauthModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button onClick={() => setOauthModalOpen(false)}>
              {"关闭"}
            </Button>
          </div>
        }
        width={560}
      >
        <MCPOAuthSection
          url={client.url}
          clientKey={client.key}
          oauthEnabled
          currentOAuthStatus={oauthStatus}
          clientId={oauthClientId}
          scope={oauthScope}
          authEndpoint={oauthAuthEndpoint}
          tokenEndpoint={oauthTokenEndpoint}
          onClientIdChange={setOauthClientId}
          onScopeChange={setOauthScope}
          onAuthEndpointChange={setOauthAuthEndpoint}
          onTokenEndpointChange={setOauthTokenEndpoint}
          onAuthChanged={() => {
            onRefresh?.();
          }}
        />
      </Modal>
    </>
  );
});
