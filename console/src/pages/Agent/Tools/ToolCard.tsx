import React, { useState } from "react";
import { Card } from "@agentscope-ai/design";
import type { ToolInfo } from "../../../api/modules/tools";
import styles from "../../Control/Channels/index.module.less";

/** Stable background colours for the initial-letter fallback icon. */
const ICON_PALETTE = [
  "#f56a00",
  "#7265e6",
  "#ffbf00",
  "#00a2ae",
  "#87d068",
  "#1890ff",
  "#eb2f96",
  "#722ed1",
];

function hashStringToIndex(value: string, mod: number): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % mod;
}

function ToolIcon({ icon, name }: { icon: string; name: string }) {
  if (icon) {
    return <span>{icon}</span>;
  }
  const letter = name.charAt(0).toUpperCase();
  const backgroundColor =
    ICON_PALETTE[hashStringToIndex(name, ICON_PALETTE.length)];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 28,
        height: 28,
        borderRadius: 6,
        fontSize: 14,
        fontWeight: 600,
        color: "#fff",
        backgroundColor,
      }}
    >
      {letter}
    </span>
  );
}

interface ToolCardProps {
  tool: ToolInfo;
  isCustom: boolean;
  onClick: () => void;
}

export const ToolCard = React.memo(function ToolCard({
  tool,
  isCustom,
  onClick,
}: ToolCardProps) {
    const [isHover, setIsHover] = useState(false);
  const getCardClassNames = () => {
    if (isHover) return `${styles.channelCard} ${styles.hover}`;
    if (tool.enabled) return `${styles.channelCard} ${styles.enabled}`;
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
      <div className={styles.cardTopSection}>
        <div className={styles.channelIcon}>
          <ToolIcon icon={tool.icon || ""} name={tool.name} />
        </div>
        <div className={styles.statusIndicator}>
          <div
            className={`${styles.statusDot} ${
              tool.enabled ? styles.enabled : styles.disabled
            }`}
          />
          <span
            className={`${styles.statusText} ${
              tool.enabled ? styles.enabled : styles.disabled
            }`}
          >
            {tool.enabled ? "已启用" : "已禁用"}
          </span>
        </div>
      </div>

      <div className={styles.cardMiddleSection}>
        <div className={styles.cardTitle}>{tool.name}</div>
        {isCustom ? (
          <span className={styles.customTag}>{"自定义工具"}</span>
        ) : (
          <span className={styles.builtinTag}>{"内置工具"}</span>
        )}
      </div>

      <div className={styles.cardBottomSection}>
        <div className={styles.cardDescription}>
          {tool.description || "未设置"}
        </div>
      </div>
    </Card>
  );
});
