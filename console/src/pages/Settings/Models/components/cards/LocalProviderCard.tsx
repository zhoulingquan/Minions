import React from "react";
import type { ProviderInfo } from "../../../../../api/types";
import styles from "../../index.module.less";
import { ProviderIcon } from "../ProviderIconComponent";

interface LocalProviderCardProps {
  provider: ProviderInfo;
  onOpenModels: (provider: ProviderInfo) => void;
}

export const LocalProviderCard = React.memo(function LocalProviderCard({
  provider,
  onOpenModels,
}: LocalProviderCardProps) {

  const totalCount = provider.models.length + provider.extra_models.length;
  const statusReady = totalCount > 0;

  return (
    <div className={styles.groupCardGlass}>
      {/* Header - same layout as GroupCard */}
      <div className={styles.groupCardHeader}>
        <ProviderIcon providerId={provider.id} size={36} />
        <span className={styles.groupCardName}>{provider.name}</span>
        <span className={styles.localTag}>{"本地"}</span>
        {statusReady && (
          <div className={styles.groupCardLiveBadge}>
            <span className={styles.groupCardPulse} />
            {totalCount} Live
          </div>
        )}
      </div>

      {/* Content */}
      <div className={styles.groupCardContent}>
        <div className={styles.groupCardField}>
          <span className={styles.groupCardFieldLabel}>
            {"类型"}
          </span>
          <div className={styles.groupCardMono}>
            {"嵌入式（进程内）"}
          </div>
        </div>
        <div className={styles.groupCardField}>
          <span className={styles.groupCardFieldLabel}>Models</span>
          <span className={styles.groupCardFieldValue}>
            {totalCount > 0
              ? `${totalCount} 个模型`
              : "未启动模型服务"}
          </span>
        </div>
      </div>

      {/* Actions */}
      <div className={styles.groupCardActions}>
        <button
          className={styles.groupCardActBtn}
          onClick={() => onOpenModels(provider)}
        >
          {"模型"}
        </button>
      </div>
    </div>
  );
});
