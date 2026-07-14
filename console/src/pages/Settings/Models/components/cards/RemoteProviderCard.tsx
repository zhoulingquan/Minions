import React, { useState } from "react";
import { Button, Modal, Input } from "@agentscope-ai/design";
import type { ProviderInfo } from "../../../../../api/types";
import api from "../../../../../api";
import { providerApi } from "../../../../../api/modules/provider";
import { useAppMessage } from "../../../../../hooks/useAppMessage";
import { getIsConfigured } from "../../utils";
import styles from "../../index.module.less";
import { ProviderIcon } from "../ProviderIconComponent";
import { OAuthConfirmModal } from "../../../../Chat/ModelSelector/OAuthConfirmModal";

interface RemoteProviderCardProps {
  provider: ProviderInfo;
  onSaved: () => void;
  onOpenConfig: (provider: ProviderInfo) => void;
  onOpenModels: (provider: ProviderInfo) => void;
}

export const RemoteProviderCard = React.memo(function RemoteProviderCard({
  provider,
  onSaved,
  onOpenConfig,
  onOpenModels,
}: RemoteProviderCardProps) {
    const { message } = useAppMessage();
  const [oauthModalOpen, setOauthModalOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiKeySaving, setApiKeySaving] = useState(false);

  const needsOAuth =
    provider.supports_oauth && !provider.api_key && !provider.oauth_connected;

  const handleDeleteProvider = (e: React.MouseEvent) => {
    e.stopPropagation();
    Modal.confirm({
      title: "删除提供商",
      content: `确定删除自定义提供商 "${provider.name}" 及其所有模型？此操作不可撤销。`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.deleteCustomProvider(provider.id);
          message.success(`提供商 "${provider.name}" 已删除`);
          onSaved();
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : "删除提供商失败";
          message.error(errMsg);
        }
      },
    });
  };

  const totalCount = provider.models.length + provider.extra_models.length;
  const isConfigured = getIsConfigured(provider);
  const hasModels = totalCount > 0;
  const isAvailable = isConfigured && hasModels;

  const providerTag = provider.is_custom ? (
    <span className={styles.customTag}>{"自定义"}</span>
  ) : null;

  return (
    <div className={styles.groupCardGlass}>
      {/* Header - same layout as GroupCard */}
      <div className={styles.groupCardHeader}>
        <ProviderIcon providerId={provider.id} size={36} />
        <span className={styles.groupCardName}>{provider.name}</span>
        {providerTag}
        {provider.is_free_tier && <span className={styles.freeTag}>FREE</span>}
        {isAvailable && (
          <div className={styles.groupCardLiveBadge}>
            <span className={styles.groupCardPulse} />
            Live
          </div>
        )}
      </div>

      {/* Content - same layout as GroupCard */}
      <div className={styles.groupCardContent}>
        <div className={styles.groupCardField}>
          <span className={styles.groupCardFieldLabel}>Endpoint</span>
          <div className={styles.groupCardMono}>{provider.base_url || "—"}</div>
        </div>

        <div className={styles.groupCardField}>
          <span className={styles.groupCardFieldLabel}>API Key</span>
          {provider.api_key ? (
            <div className={styles.groupCardMono}>
              <span>{provider.api_key}</span>
              <span
                className={styles.groupCardChangeBtn}
                onClick={() => onOpenConfig(provider)}
              >
                {"修改"}
              </span>
            </div>
          ) : provider.require_api_key === false ? (
            <div className={styles.groupCardMono}>
              {"无需配置"}
            </div>
          ) : (
            <div className={styles.groupCardKeyInput}>
              <Input.Password
                size="small"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                placeholder={
                  provider.api_key_prefixes?.length
                    ? `${provider.api_key_prefixes.join(", ")}...`
                    : provider.api_key_prefix
                    ? `${provider.api_key_prefix}...`
                    : "sk-..."
                }
                style={{ flex: 1 }}
              />
              <Button
                type="primary"
                size="small"
                loading={apiKeySaving}
                disabled={!apiKeyInput.trim()}
                onClick={async (e) => {
                  e.stopPropagation();
                  setApiKeySaving(true);
                  try {
                    await providerApi.configureProvider(provider.id, {
                      api_key: apiKeyInput.trim(),
                    });
                    message.success("已保存");
                    setApiKeyInput("");
                    onSaved();
                  } catch (err) {
                    const msg =
                      err instanceof Error
                        ? err.message
                        : "保存失败";
                    message.error(msg);
                  } finally {
                    setApiKeySaving(false);
                  }
                }}
              >
                {"保存"}
              </Button>
            </div>
          )}
        </div>

        <div className={styles.groupCardField}>
          <span className={styles.groupCardFieldLabel}>Models</span>
          <span className={styles.groupCardFieldValue}>
            {totalCount > 0
              ? `${totalCount} 个模型`
              : "暂无模型"}
          </span>
        </div>
      </div>

      {/* Actions - same layout as GroupCard */}
      <div className={styles.groupCardActions}>
        {needsOAuth && (
          <button
            className={styles.groupCardActBtn}
            onClick={() => setOauthModalOpen(true)}
          >
            {"OAuth 认证"}
          </button>
        )}
        <button
          className={styles.groupCardActBtn}
          onClick={() => onOpenModels(provider)}
        >
          {"模型"}
        </button>
        <button
          className={styles.groupCardActBtn}
          onClick={() => onOpenConfig(provider)}
        >
          {"设置"}
        </button>
        {provider.is_custom ? (
          <button
            className={`${styles.groupCardActBtn} ${styles.groupCardActBtnDanger}`}
            onClick={handleDeleteProvider}
          >
            {"删除"}
          </button>
        ) : (
          isConfigured &&
          provider.require_api_key !== false && (
            <button
              className={`${styles.groupCardActBtn} ${styles.groupCardActBtnDanger}`}
              onClick={(e) => {
                e.stopPropagation();
                Modal.confirm({
                  title: "停用提供商",
                  content: `确定清除 "${provider.name}" 的 API Key？该提供商将变为未配置状态。`,
                  okText: "停用",
                  okButtonProps: { danger: true },
                  cancelText: "取消",
                  onOk: async () => {
                    try {
                      await providerApi.configureProvider(provider.id, {
                        api_key: "",
                      });
                      message.success(
                        `提供商 "${provider.name}" 已停用`,
                      );
                      onSaved();
                    } catch (err) {
                      const msg =
                        err instanceof Error
                          ? err.message
                          : "保存失败";
                      message.error(msg);
                    }
                  },
                });
              }}
            >
              {"停用"}
            </button>
          )
        )}
      </div>

      <OAuthConfirmModal
        open={oauthModalOpen}
        providerId={provider.id}
        providerName={provider.name}
        onSuccess={() => {
          setOauthModalOpen(false);
          onSaved();
        }}
        onCancel={() => setOauthModalOpen(false)}
      />
    </div>
  );
});
