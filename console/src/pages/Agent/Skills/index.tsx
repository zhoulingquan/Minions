import { useState, useMemo, useCallback } from "react";
import { ReloadOutlined } from "@ant-design/icons";
import { Button } from "@agentscope-ai/design";
import { MarketPanel } from "../../Settings/Market/MarketPanel";
import {
  SkillCard,
  SkillDrawer,
  SkillsToolbar,
  SkillListItem,
} from "./components";
import type { SkillSpec } from "../../../api/types";
import { PageHeader } from "@/components/PageHeader";
import { useSkillsPage } from "./useSkillsPage";
import styles from "./index.module.less";
import { GlobalSkillsTab } from "./components/GlobalSkillsTab";
import channelsStyles from "../../Control/Channels/index.module.less";

function SkillsPage() {
  const {
    skills,
    visibleSkills,
    hasMore,
    sentinelRef,
    sortedSkills,
    conflictRenameModal,
    syncConflictModal,
    loading,
    drawerOpen,
    editingSkill,
    form,
    selectedSkills,
    batchModeEnabled,
    viewMode,
    setViewMode,
    searchQuery,
    setSearchQuery,
    handleToggleEnabled,
    handleDrawerClose,
    handleSubmit,
    handleEdit,
    handleSyncSkill,
    promotingSkillName,
    toggleSelect,
    toggleEnabled,
    refreshSkills,
    hardRefresh,
  } = useSkillsPage();

  const [activeTab, setActiveTab] = useState<"global" | "workspace" | "market">(
    "workspace",
  );

  // Split skills into enabled and disabled groups
  const { enabledSkills, disabledSkills } = useMemo(() => {
    const enabled = visibleSkills.filter((skill) => skill.enabled);
    const disabled = visibleSkills.filter((skill) => !skill.enabled);
    return { enabledSkills: enabled, disabledSkills: disabled };
  }, [visibleSkills]);

  // Shared renderer for SkillListItem (used by both enabled and disabled sections)
  const renderSkillListItem = useCallback(
    (skill: SkillSpec) => (
      <SkillListItem
        key={skill.name}
        skill={skill}
        batchModeEnabled={batchModeEnabled}
        isSelected={selectedSkills.has(skill.name)}
        onSelect={() => toggleSelect(skill.name)}
        onClick={() => handleEdit(skill)}
        onToggleEnabled={async () => {
          await toggleEnabled(skill);
          await refreshSkills();
        }}
        onSync={() => void handleSyncSkill(skill)}
        syncing={promotingSkillName === skill.name}
      />
    ),
    [
      batchModeEnabled,
      selectedSkills,
      toggleSelect,
      toggleEnabled,
      refreshSkills,
      handleEdit,
      handleSyncSkill,
      promotingSkillName,
    ],
  );

  return (
    <div className={styles.skillsPage}>
      <PageHeader
        items={[{ title: "工作区" }, { title: "技能" }]}
        center={
          <div className={channelsStyles.filterTabs}>
            <button
              className={`${channelsStyles.filterTab} ${
                activeTab === "global" ? channelsStyles.filterTabActive : ""
              }`}
              onClick={() => setActiveTab("global")}
            >
              {"全局技能"}
            </button>
            <button
              className={`${channelsStyles.filterTab} ${
                activeTab === "workspace" ? channelsStyles.filterTabActive : ""
              }`}
              onClick={() => setActiveTab("workspace")}
            >
              {"当前智能体技能"}
            </button>
            <button
              className={`${channelsStyles.filterTab} ${
                activeTab === "market" ? channelsStyles.filterTabActive : ""
              }`}
              onClick={() => setActiveTab("market")}
            >
              {"技能市场"}
            </button>
          </div>
        }
        extra={
          activeTab === "workspace" ? (
            <Button
              size="small"
              onClick={hardRefresh}
              loading={loading}
              icon={<ReloadOutlined />}
            />
          ) : undefined
        }
      />

      {activeTab === "workspace" ? (
        <>
          {!loading && skills.length > 0 && (
            <SkillsToolbar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              viewMode={viewMode}
              onViewModeChange={setViewMode}
            />
          )}

          {loading ? (
            <div className={styles.loading}>
              <span className={styles.loadingText}>{"加载中..."}</span>
            </div>
          ) : skills.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyStateBadge}>
                {"新工作区默认是空的"}
              </div>
              <h2 className={styles.emptyStateTitle}>
                {"这个智能体还没有可用技能"}
              </h2>
              <p className={styles.emptyStateText}>
                {
                  "这是正常状态。新建的工作区不会自动带上技能。请前往全局技能页，选择已有技能并添加到这个智能体。"
                }
              </p>
            </div>
          ) : sortedSkills.length === 0 ? (
            <div className={styles.noSearchResults}>
              <span className={styles.noSearchResultsIcon}>🔍</span>
              <span className={styles.noSearchResultsText}>
                {"未找到匹配的技能"}
              </span>
            </div>
          ) : (
            <>
              {/* Enabled Skills Section */}
              {enabledSkills.length > 0 && (
                <div className={styles.panelSection}>
                  <div className={styles.panelTitle}>
                    <span className={styles.panelDotGreen} />
                    {"已激活的技能"}
                    <span className={styles.panelCount}>
                      {enabledSkills.length} {"个激活"}
                    </span>
                  </div>

                  {viewMode === "card" ? (
                    <div className={styles.skillsGrid}>
                      {enabledSkills.map((skill) => (
                        <SkillCard
                          key={skill.name}
                          skill={skill}
                          selected={
                            batchModeEnabled
                              ? selectedSkills.has(skill.name)
                              : undefined
                          }
                          onSelect={() => toggleSelect(skill.name)}
                          onClick={() => handleEdit(skill)}
                          onMouseEnter={() => {}}
                          onMouseLeave={() => {}}
                          onToggleEnabled={() => handleToggleEnabled(skill)}
                          onSync={() => void handleSyncSkill(skill)}
                          syncing={promotingSkillName === skill.name}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className={styles.skillsList}>
                      {enabledSkills.map(renderSkillListItem)}
                    </div>
                  )}
                </div>
              )}

              {/* Disabled Skills Section */}
              {disabledSkills.length > 0 && (
                <div className={styles.panelSectionDashed}>
                  <div className={styles.panelTitle}>
                    <span className={styles.panelDotGray} />
                    {"未激活的技能"}
                  </div>
                  {viewMode === "card" ? (
                    <div className={styles.skillsGrid}>
                      {disabledSkills.map((skill) => (
                        <SkillCard
                          key={skill.name}
                          skill={skill}
                          selected={
                            batchModeEnabled
                              ? selectedSkills.has(skill.name)
                              : undefined
                          }
                          onSelect={() => toggleSelect(skill.name)}
                          onClick={() => handleEdit(skill)}
                          onToggleEnabled={() => handleToggleEnabled(skill)}
                          onSync={() => void handleSyncSkill(skill)}
                          syncing={promotingSkillName === skill.name}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className={styles.skillsList}>
                      {disabledSkills.map(renderSkillListItem)}
                    </div>
                  )}
                </div>
              )}

              {hasMore && <div ref={sentinelRef} style={{ height: 1 }} />}
            </>
          )}

          {conflictRenameModal}
          {syncConflictModal}

          <SkillDrawer
            open={drawerOpen}
            editingSkill={editingSkill}
            form={form}
            onClose={handleDrawerClose}
            onSubmit={handleSubmit}
          />
        </>
      ) : activeTab === "global" ? (
        <GlobalSkillsTab
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          onBrowseMarket={() => setActiveTab("market")}
        />
      ) : (
        <MarketPanel installTarget="global" />
      )}
    </div>
  );
}

export default SkillsPage;
