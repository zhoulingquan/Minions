import { Card } from "@agentscope-ai/design";
import React, { useState } from "react";
import { ChannelIcon } from "./ChannelIcon";
import { getChannelLabel, type ChannelKey } from "./constants";
import styles from "../index.module.less";

interface ChannelCardProps {
  channelKey: ChannelKey;
  config: Record<string, unknown>;
  onClick: () => void;
}

export const ChannelCard = React.memo(function ChannelCard({
  channelKey,
  config,
  onClick,
}: ChannelCardProps) {
    const [isHover, setIsHover] = useState(false);
  const enabled = Boolean(config.enabled);
  const isBuiltin = Boolean(config.isBuiltin);
  const label = getChannelLabel(channelKey);
  const getConfigString = (key: string) =>
    typeof config[key] === "string" ? config[key] : "";
  const botPrefix = getConfigString("bot_prefix");

  const getChannelIcon = () => (
    <ChannelIcon channelKey={channelKey} size={32} />
  );

  const getCardClassNames = () => {
    if (isHover) return `${styles.channelCard} ${styles.hover}`;
    if (enabled) return `${styles.channelCard} ${styles.enabled}`;
    return `${styles.channelCard} ${styles.normal}`;
  };

  return (
    <Card
      hoverable
      onClick={onClick}
      onMouseEnter={() => setIsHover(true)}
      onMouseLeave={() => setIsHover(false)}
      className={getCardClassNames()}
      bodyStyle={{ padding: 24 }}
    >
      {/* Top section: Icon and Status */}
      <div className={styles.cardTopSection}>
        <div className={styles.channelIcon}>{getChannelIcon()}</div>
        <div className={styles.statusIndicator}>
          <div
            className={`${styles.statusDot} ${
              enabled ? styles.enabled : styles.disabled
            }`}
          />
          <span
            className={`${styles.statusText} ${
              enabled ? styles.enabled : styles.disabled
            }`}
          >
            {enabled ? "已启用" : "已禁用"}
          </span>
        </div>
      </div>

      {/* Middle section: Name and Tag */}
      <div className={styles.cardMiddleSection}>
        <div className={styles.cardTitle}>{label}</div>
        {isBuiltin ? (
          <span className={styles.builtinTag}>{"内置"}</span>
        ) : (
          <span className={styles.customTag}>{"自定义"}</span>
        )}
      </div>

      {/* Bottom section: Bot Prefix */}
      <div className={styles.cardBottomSection}>
        <div className={styles.cardDescription}>
          {"机器人前缀"}: {botPrefix || "未设置"}
        </div>
      </div>
    </Card>
  );
});
