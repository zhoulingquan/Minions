import { memo, useMemo } from "react";
import { Button, Tooltip } from "@agentscope-ai/design";
import { Download, Eye, Heart, Star } from "lucide-react";
import type { MarketResult } from "../../../../api/modules/market";
import { SkillIcon, sourceLabel } from "./SkillIcon";
import styles from "./ResultListItem.module.less";

interface ResultListItemProps {
  item: MarketResult;
  onInstall: () => void;
  onOpenDetail: () => void;
}

export const ResultListItem = memo(function ResultListItem({
  item,
  onInstall,
  onOpenDetail,
}: ResultListItemProps) {
  const stats = useMemo(() => {
    const source = item.stats ?? {};
    const values = [
      { Icon: Download, label: "下载量", value: source.downloads ?? source.installs },
      { Icon: Star, label: "星标", value: source.stars },
      { Icon: Heart, label: "点赞", value: source.likes },
      { Icon: Eye, label: "浏览量", value: source.views },
    ];
    return values.filter((stat) => stat.value != null).map((stat) => ({
      ...stat,
      value:
        typeof stat.value === "number"
          ? stat.value.toLocaleString()
          : String(stat.value),
    }));
  }, [item.stats]);

  return (
    <div
      className={styles.listItem}
      role="button"
      tabIndex={0}
      onClick={onOpenDetail}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpenDetail();
        }
      }}
    >
      <div className={styles.listItemLeft}>
        <SkillIcon url={item.icon_url} alt={item.name} source={item.source} />
        <div className={styles.listItemInfo}>
          <div className={styles.listItemHeader}>
            <Tooltip title={item.name}>
              <span className={styles.skillTitle}>{item.name}</span>
            </Tooltip>
            <span className={styles.sourceBadge}>{sourceLabel(item.source)}</span>
          </div>
          <p className={styles.description}>{item.description || "暂无描述"}</p>
          {stats.length > 0 && (
            <div className={styles.statsRow}>
              {stats.map(({ Icon, label, value }) => (
                <Tooltip key={label} title={label}>
                  <span className={styles.statItem}>
                    <Icon size={13} />
                    {value}
                  </span>
                </Tooltip>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className={styles.listItemRight} onClick={(event) => event.stopPropagation()}>
        <Button type="primary" size="small" onClick={onInstall}>
          保存
        </Button>
      </div>
    </div>
  );
});
