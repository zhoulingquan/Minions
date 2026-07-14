import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Input, Select, Tooltip } from "@agentscope-ai/design";
import { AppstoreOutlined, UnorderedListOutlined } from "@ant-design/icons";
import { Check } from "lucide-react";
import { useAgentStore } from "../../../stores/agentStore";
import { useMarketSearch } from "./useMarketSearch";
import {
  useMarketInstall,
  type InstallTarget,
  type InstallQueueItem,
} from "./useMarketInstall";
import type { MarketResult } from "../../../api/modules/market";
import {
  ResultCard,
  ResultListItem,
  DetailDrawer,
  QueueItem,
  EmptyState,
} from "./components";
import styles from "./index.module.less";

function getCardKey(item: MarketResult) {
  return `${item.source}:${item.slug}`;
}

/** Memoized install queue panel — only re-renders when queue changes */
const InstallQueuePanel = memo(function InstallQueuePanel({
  queue,
  onClearCompleted,
  onCancel,
  onRetry,
}: {
  queue: InstallQueueItem[];
  onClearCompleted: () => void;
  onCancel: (id: string) => void;
  onRetry: (id: string) => void;
}) {
    return (
    <div className={styles.queueDrawer}>
      <div className={styles.queueHeader}>
        <span>{"安装队列"}</span>
        <Button size="small" onClick={onClearCompleted}>
          {"清空"}
        </Button>
      </div>
      <div className={styles.queueList}>
        {queue.map((q) => (
          <QueueItem
            key={q.id}
            item={q}
            onCancel={onCancel}
            onRetry={onRetry}
          />
        ))}
      </div>
    </div>
  );
});

/** Multi-select provider chips (first filter layer) */
const ProviderChips = memo(function ProviderChips({
  providers,
  selectedKeys,
  onToggle,
}: {
  providers: {
    key: string;
    label: string;
    available: boolean;
    reason?: string | null;
  }[];
  selectedKeys: Set<string>;
  onToggle: (key: string) => void;
}) {
    return (
    <div className={styles.providerChips}>
      {providers.map((p) => {
        const active = selectedKeys.has(p.key);
        const klass = [
          styles.chip,
          active ? styles.chipActive : "",
          !p.available ? styles.chipDisabled : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <Tooltip
            key={p.key}
            title={
              p.available
                ? undefined
                : p.reason ?? "数据源不可用"
            }
          >
            <span
              className={klass}
              onClick={p.available ? () => onToggle(p.key) : undefined}
              role="button"
              tabIndex={p.available ? 0 : -1}
              onKeyDown={(e) => {
                if (p.available && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  onToggle(p.key);
                }
              }}
              aria-pressed={active}
              aria-disabled={!p.available}
            >
              {active && <Check size={12} strokeWidth={3} />}
              {p.label}
            </span>
          </Tooltip>
        );
      })}
    </div>
  );
});

/**
 * Single-select category dropdown (second filter layer).
 * The leading "All" option clears the filter.
 */
const CategorySelect = memo(function CategorySelect({
  categories,
  active,
  onSelect,
}: {
  categories: { id: string; label: string }[];
  active: string;
  onSelect: (id: string) => void;
}) {
    const options = useMemo(
    () => [
      { value: "", label: "全部" },
      ...categories.map((c) => ({ value: c.id, label: c.label })),
    ],
    [categories],
  );
  return (
    <Select
      className={styles.categorySelect}
      value={active || undefined}
      onChange={(v) => onSelect(v ?? "")}
      options={options}
      placeholder={"搜索分类"}
      showSearch
      allowClear
      optionFilterProp="label"
      popupMatchSelectWidth={false}
      aria-label={"搜索分类"}
    />
  );
});

function LoadMoreSentinel({ onVisible }: { onVisible: () => void }) {
    const nodeRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = nodeRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) onVisible();
      },
      { rootMargin: "200px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [onVisible]);
  return (
    <div ref={nodeRef} className={styles.sentinel}>
      {"加载中..."}
    </div>
  );
}

/**
 * Embeddable market browser. The host page fixes the install destination:
 * Skills page saves into the current agent's workspace, Skill Pool page
 * imports into the pool.
 */
export function MarketPanel({
  installTarget,
}: {
  installTarget: InstallTarget;
}) {
    const selectedAgent = useAgentStore((s) => s.selectedAgent);
  const market = useMarketSearch();
  const [detailItem, setDetailItem] = useState<MarketResult | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const install = useMarketInstall({ selectedAgent });

  const onInstall = useCallback(
    (item: MarketResult) => {
      install.enqueue([item], installTarget);
    },
    [install, installTarget],
  );

  // Stable callbacks for DetailDrawer
  const detailItemRef = useRef(detailItem);
  detailItemRef.current = detailItem;

  const handleDetailInstall = useCallback(() => {
    const current = detailItemRef.current;
    if (current) {
      onInstall(current);
      setDetailItem(null);
    }
  }, [onInstall]);

  const handleDetailClose = useCallback(() => {
    setDetailItem(null);
  }, []);

  const browseHintLabel = useMemo(() => {
    if (market.query.trim() || market.category) return "";
    return market.providers
      .filter(
        (p) =>
          p.available &&
          !p.supports_browse &&
          market.selectedProviderKeys.has(p.key),
      )
      .map((p) => p.label)
      .join(", ");
  }, [
    market.query,
    market.category,
    market.providers,
    market.selectedProviderKeys,
  ]);

  return (
    <div className={styles.marketPage}>
      <div className={styles.content}>
        <div className={styles.toolbar}>
          <ProviderChips
            providers={market.providers}
            selectedKeys={market.selectedProviderKeys}
            onToggle={market.toggleProvider}
          />
          <div className={styles.filters}>
            <CategorySelect
              categories={market.categories}
              active={market.category}
              onSelect={market.setCategory}
            />
            <Input.Search
              className={styles.searchInput}
              placeholder={"在多平台中搜索技能"}
              allowClear
              value={market.query}
              onChange={(e) => market.setQuery(e.target.value)}
              aria-label={"在多平台中搜索技能"}
            />
            <div className={styles.viewToggle} aria-label="排列方式">
              <Tooltip title="列表排列">
                <button
                  className={`${styles.viewToggleButton} ${
                    viewMode === "list" ? styles.viewToggleButtonActive : ""
                  }`}
                  aria-label="列表排列"
                  aria-pressed={viewMode === "list"}
                  onClick={() => setViewMode("list")}
                >
                  <UnorderedListOutlined />
                </button>
              </Tooltip>
              <Tooltip title="网格排列">
                <button
                  className={`${styles.viewToggleButton} ${
                    viewMode === "grid" ? styles.viewToggleButtonActive : ""
                  }`}
                  aria-label="网格排列"
                  aria-pressed={viewMode === "grid"}
                  onClick={() => setViewMode("grid")}
                >
                  <AppstoreOutlined />
                </button>
              </Tooltip>
            </div>
          </div>
        </div>

        {market.query.trim() && !market.loading && !market.globalError && (
          <div className={styles.searchHint}>
            {`"${market.query.trim()}" 相关技能共搜索到 ${market.totalCount} 个结果`}
          </div>
        )}

        {browseHintLabel && (
          <div className={styles.browseHint}>
            {`选择分类或输入关键词以浏览 ${browseHintLabel} 中的技能`}
          </div>
        )}

        {market.globalError && (
          <div className={styles.errorRow}>{market.globalError}</div>
        )}
        {market.errors.map((err) => {
          const provider = market.providers.find((p) => p.key === err.provider);
          const label = provider?.label ?? err.provider;
          return (
            <div className={styles.errorRow} key={err.provider}>
              <strong>{label}</strong>: {err.message}
            </div>
          );
        })}

        {market.loading && market.results.length === 0 ? (
          <EmptyState text={"加载中..."} />
        ) : market.results.length === 0 &&
          (market.globalError || market.errors.length > 0) ? (
          <EmptyState text={"没有找到结果"}>
            <Button onClick={market.retry} loading={market.loading}>
              {"重试"}
            </Button>
          </EmptyState>
        ) : market.results.length === 0 ? (
          <EmptyState text={"没有找到结果"} />
        ) : (
          <>
            <div
              className={
                viewMode === "grid" ? styles.resultsGrid : styles.resultsList
              }
            >
              {market.results.map((item) =>
                viewMode === "grid" ? (
                  <ResultCard
                    key={getCardKey(item)}
                    item={item}
                    onInstall={() => onInstall(item)}
                    onOpenDetail={() => setDetailItem(item)}
                  />
                ) : (
                  <ResultListItem
                    key={getCardKey(item)}
                    item={item}
                    onInstall={() => onInstall(item)}
                    onOpenDetail={() => setDetailItem(item)}
                  />
                ),
              )}
            </div>
            <div className={styles.loadMoreRow}>
              {market.hasMore && market.autoLoadBlocked ? (
                <Button onClick={market.loadMore} loading={market.loading}>
                  {"加载更多"}
                </Button>
              ) : market.hasMore ? (
                <LoadMoreSentinel
                  key={market.results.length}
                  onVisible={market.autoLoadMore}
                />
              ) : (
                <span className={styles.noMoreText}>
                  {"没有更多了"}
                </span>
              )}
            </div>
          </>
        )}
      </div>

      {install.queue.length > 0 && (
        <InstallQueuePanel
          queue={install.queue}
          onClearCompleted={install.clearFinished}
          onCancel={install.cancel}
          onRetry={install.retry}
        />
      )}

      <DetailDrawer
        item={detailItem}
        onInstall={handleDetailInstall}
        onClose={handleDetailClose}
      />
    </div>
  );
}
