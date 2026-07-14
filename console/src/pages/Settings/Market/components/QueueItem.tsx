import { memo, useCallback } from "react";
import { Button } from "@agentscope-ai/design";
import type { InstallQueueItem } from "../useMarketInstall";
import { sourceLabel } from "./SkillIcon";
import styles from "./QueueItem.module.less";

interface QueueItemProps {
  item: InstallQueueItem;
  /** Accepts item id so parent can pass a stable reference */
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
}

export const QueueItem = memo(function QueueItem({
  item,
  onCancel,
  onRetry,
}: QueueItemProps) {

  const isTerminal =
    item.status === "completed" ||
    item.status === "failed" ||
    item.status === "cancelled";
  const canCancel =
    !isTerminal && !(item.target === "global" && item.status === "installing");
  const canRetry = item.status === "failed" || item.status === "cancelled";

  const handleCancel = useCallback(
    () => onCancel(item.id),
    [onCancel, item.id],
  );
  const handleRetry = useCallback(() => onRetry(item.id), [onRetry, item.id]);

  let displayMessage = "";
  if (item.message === "__TIMED_OUT__") {
    displayMessage = "安装超时";
  } else if (item.message) {
    displayMessage =
      item.status === "failed"
        ? `失败：${item.message}`
        : item.message;
  }

  return (
    <div className={styles.queueItem}>
      <div className={styles.queueItemTop}>
        <strong>{item.result.name}</strong>
        <span className={`${styles.statusTag} ${styles[item.status]}`}>
          {item.status === "queued" ? "排队中" : item.status === "installing" ? "安装中" : item.status === "completed" ? "已完成" : item.status === "failed" ? "失败" : "已取消"}
        </span>
      </div>
      <div className={styles.queueItemMeta}>
        {sourceLabel(item.result.source)}
      </div>
      {displayMessage && (
        <div className={styles.queueItemMessage}>{displayMessage}</div>
      )}
      <div className={styles.queueItemActions}>
        {canCancel && (
          <Button size="small" onClick={handleCancel}>
            {"取消"}
          </Button>
        )}
        {canRetry && (
          <Button size="small" type="primary" onClick={handleRetry}>
            {"重试"}
          </Button>
        )}
      </div>
    </div>
  );
});
