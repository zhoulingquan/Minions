import { useState } from "react";
import {
  Alert,
  Button,
  Input,
  Modal,
  Pagination,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { Download, ExternalLink, Package, RefreshCw } from "lucide-react";
import type { MarketPluginEntry } from "@/api/modules/pluginMarket";
import { openExternalLink } from "@/utils/openExternalLink";
import { useMarketPlugins } from "../hooks/useMarketPlugins";
import styles from "./OfficialPluginList.module.less";
import marketStyles from "./MarketPluginList.module.less";

const { Text } = Typography;

const PLUGIN_CATEGORIES = [
  { code: "agent-tool", zh: "Agent 工具", en: "Agent Tool" },
  { code: "provider", zh: "模型接入", en: "Provider" },
  { code: "command", zh: "Slash 命令", en: "Slash Command" },
  { code: "hook", zh: "生命周期 Hook", en: "Lifecycle Hook" },
  { code: "frontend", zh: "UI 扩展", en: "UI Extension" },
  { code: "general", zh: "通用插件", en: "General" },
];

function pickLocalizedDescription(
  entry: MarketPluginEntry,
  language: string,
): string {
  const locales = entry.locales;
  if (!locales || Object.keys(locales).length === 0) return "";

  if (locales[language]) return locales[language].description;

  const prefix = language.split("-")[0].toLowerCase();
  for (const key of Object.keys(locales)) {
    if (key.toLowerCase().startsWith(prefix)) {
      return locales[key].description;
    }
  }

  if (locales.en) return locales.en.description;

  const first = Object.values(locales)[0];
  return first?.description ?? "";
}

interface MarketPluginListProps {
  onInstalled: () => void;
}

export function MarketPluginList({ onInstalled }: MarketPluginListProps) {
    const [searchInput, setSearchInput] = useState("");
  const [activeSearch, setActiveSearch] = useState("");

  const {
    loading,
    error,
    plugins,
    total,
    page,
    pageSize,
    category,
    installingId,
    minionsVersion,
    isCompatible,
    handleSearch,
    handleCategoryChange,
    handlePageChange,
    handleRefresh,
    handleInstall,
  } = useMarketPlugins({ onInstalled });

  const lang = "zh";

  const isSearchMode = !!activeSearch;

  const onSearch = (val: string) => {
    setActiveSearch(val);
    handleSearch(val);
    if (val) handleCategoryChange(undefined);
  };

  const onCategoryClick = (code: string | null) => {
    handleCategoryChange(code || undefined);
  };

  return (
    <div className={styles.catalogSection}>
      <div className={marketStyles.toolbar}>
        {!isSearchMode ? (
          <div className={marketStyles.categoryTabs}>
            <span
              className={`${marketStyles.categoryTab} ${
                !category ? marketStyles.categoryTabActive : ""
              }`}
              onClick={() => onCategoryClick(null)}
            >
              {"全部"}
            </span>
            {PLUGIN_CATEGORIES.map((cat) => (
              <span
                key={cat.code}
                className={`${marketStyles.categoryTab} ${
                  category === cat.code ? marketStyles.categoryTabActive : ""
                }`}
                onClick={() => onCategoryClick(cat.code)}
              >
                {lang === "zh" ? cat.zh : cat.en}
              </span>
            ))}
          </div>
        ) : (
          <div className={marketStyles.searchHint}>
            {!loading &&
              !error &&
              `"${activeSearch}" 相关插件共搜索到 ${total} 个结果`}
          </div>
        )}
        <div className={marketStyles.toolbarRight}>
          <Input.Search
            placeholder={"搜索插件..."}
            allowClear
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              if (!e.target.value) onSearch("");
            }}
            onSearch={onSearch}
            style={{ width: 220 }}
          />
          <Button
            type="default"
            size="small"
            icon={<RefreshCw size={14} />}
            onClick={handleRefresh}
            disabled={loading}
          >
            {"刷新"}
          </Button>
        </div>
      </div>

      {error && (
        <Alert
          type="warning"
          showIcon
          message={<span style={{ fontSize: 15 }}>{error}</span>}
          style={{ marginBottom: 12 }}
        />
      )}

      <Spin spinning={loading}>
        {!loading && plugins.length === 0 && !error && (
          <Text type="secondary">{"暂无市场插件"}</Text>
        )}
        <div className={styles.catalogList}>
          {plugins.map((entry) => (
            <div className={styles.catalogRow} key={entry.id}>
              <div className={styles.catalogIcon}>
                {entry.logo_url ? (
                  <img
                    src={entry.logo_url}
                    alt=""
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 4,
                      objectFit: "contain",
                    }}
                  />
                ) : (
                  <Package size={18} />
                )}
              </div>
              <div className={styles.catalogInfo}>
                <div className={styles.catalogNameRow}>
                  <Text strong>{entry.display_name}</Text>
                  {entry.locales?.[lang]?.category && (
                    <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>
                      {entry.locales[lang].category}
                    </Tag>
                  )}
                  {entry.minions_compat_labels &&
                    entry.minions_compat_labels.length > 0 && (
                      <Tag
                        color={isCompatible(entry) ? "green" : "orange"}
                        style={{ margin: 0, fontSize: 11 }}
                      >
                        {`Minions ${entry.minions_compat_labels.join(", ")}`}
                      </Tag>
                    )}
                </div>
                {entry.locales && (
                  <div className={styles.catalogDescription}>
                    {pickLocalizedDescription(entry, "zh")}
                  </div>
                )}
                <div className={styles.catalogMeta}>
                  v{entry.version}
                  {entry.developer
                    ? ` · ${"开发者"}: ${
                        entry.developer
                      }`
                    : ""}
                  {entry.downloads != null
                    ? ` · ${"下载量"}: ${
                        entry.downloads
                      }`
                    : ""}
                </div>
              </div>
              <div className={styles.catalogActions}>
                {entry.details_url && (
                  <Button
                    type="default"
                    size="small"
                    icon={<ExternalLink size={14} />}
                    onClick={() => openExternalLink(entry.details_url!)}
                  >
                    {"详情"}
                  </Button>
                )}
                <Tooltip
                  title={
                    !isCompatible(entry)
                      ? `This plugin is labeled for Minions ${
                          entry.minions_compat_labels?.join(", ") ?? "unknown"
                        }; compatibility with Minions ${
                          minionsVersion ?? "unknown"
                        } is unverified.`
                      : undefined
                  }
                >
                  <Button
                    type="primary"
                    size="small"
                    icon={<Download size={14} />}
                    loading={installingId === entry.id}
                    disabled={
                      installingId !== null && installingId !== entry.id
                    }
                    onClick={() => {
                      if (!isCompatible(entry)) {
                        Modal.confirm({
                          title: "兼容性警告",
                          content: `该插件标注适配 Minions ${
                            entry.minions_compat_labels?.join(", ") ?? "unknown"
                          }，而您当前的 Minions 版本为 ${
                            minionsVersion ?? "unknown"
                          }。安装后可能出现错误，是否确认继续？`,
                          okText: "仍然安装",
                          cancelText: "取消",
                          onOk: () => void handleInstall(entry),
                        });
                      } else {
                        void handleInstall(entry);
                      }
                    }}
                  >
                    {"安装"}
                  </Button>
                </Tooltip>
              </div>
            </div>
          ))}
        </div>

        {total > pageSize && (
          <div style={{ marginTop: 16, textAlign: "center" }}>
            <Pagination
              current={page}
              pageSize={pageSize}
              total={total}
              onChange={handlePageChange}
              showSizeChanger={false}
              size="small"
            />
          </div>
        )}
      </Spin>
    </div>
  );
}
