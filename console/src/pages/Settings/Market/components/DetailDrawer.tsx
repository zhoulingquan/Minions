import { memo, useMemo } from "react";
import { Button, Drawer } from "@agentscope-ai/design";
import type { MarketResult } from "../../../../api/modules/market";
import { SkillIcon, sourceLabel } from "./SkillIcon";
import styles from "./DetailDrawer.module.less";

interface DetailDrawerProps {
  item: MarketResult | null;
  onInstall: () => void;
  onClose: () => void;
}

const STAT_KEY_LABELS: Record<string, string> = {
  downloads: "下载量",
  installs: "安装量",
  stars: "星标",
  likes: "点赞",
  views: "浏览量",
  category: "分类",
  updated_at: "更新时间",
};

function formatStatValue(key: string, value: string | number): string {
  if (key === "updated_at" && typeof value === "string") {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return date.toLocaleDateString();
  }
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
}

export const DetailDrawer = memo(function DetailDrawer({
  item,
  onInstall,
  onClose,
}: DetailDrawerProps) {
    const open = !!item;
  const missing = "—";

  const rows = useMemo<Array<[string, React.ReactNode]>>(() => {
    if (!item) return [];
    const result: Array<[string, React.ReactNode]> = [
      ["作者", item.author || missing],
      ["版本", item.version || missing],
      [
        "安装地址",
        <code key="src" className={styles.mono}>
          {item.source_url}
        </code>,
      ],
      [
        "标识",
        <code key="slug" className={styles.mono}>
          {item.slug}
        </code>,
      ],
    ];
    if (item.stats) {
      for (const [key, value] of Object.entries(item.stats)) {
        const labelKey = STAT_KEY_LABELS[key];
        const label = labelKey || key;
        result.push([label, formatStatValue(key, value)]);
      }
    }
    return result;
  }, [item, missing]);

  return (
    <Drawer
      width={520}
      placement="right"
      title={"技能详情"}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={
        item ? (
          <div className={styles.drawerFooter}>
            <Button type="primary" onClick={onInstall}>
              {"保存"}
            </Button>
          </div>
        ) : null
      }
    >
      {item && (
        <>
          <div className={styles.detailHeader}>
            <SkillIcon
              url={item.icon_url}
              alt={item.name}
              source={item.source}
            />
            <div className={styles.detailHeaderText}>
              <h3 className={styles.detailTitle}>{item.name}</h3>
              <div className={styles.detailMeta}>
                <span className={styles.sourceBadge}>
                  {sourceLabel(item.source)}
                </span>
              </div>
            </div>
          </div>

          <div className={styles.detailDescription}>
            {item.description || "暂无描述"}
          </div>

          <dl className={styles.detailRows}>
            {rows.map(([key, value]) => (
              <div className={styles.detailRow} key={key}>
                <dt className={styles.detailKey}>{key}</dt>
                <dd className={styles.detailValue}>{value}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </Drawer>
  );
});
