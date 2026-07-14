import { useEffect, useState, useMemo, useCallback } from "react";
import { Button, Input } from "@agentscope-ai/design";
import { Spin } from "antd";
import {
  AppstoreOutlined,
  CloseOutlined,
  DeleteOutlined,
  PlusOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import api from "../../../../api";
import type { GlobalSkillSpec, SkillSpec } from "../../../../api/types";
import { invalidateSkillCache } from "../../../../api/modules/skill";
import { useAgentStore } from "../../../../stores/agentStore";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { useProgressiveRender } from "../../../../hooks/useProgressiveRender";
import { useSkillFilter } from "../useSkillFilter";
import { GlobalSkillCard } from "./GlobalSkillCard";
import { GlobalSkillListItem } from "./GlobalSkillListItem";
import { GlobalSkillAddModal } from "./GlobalSkillAddModal";
import { ImportHubModal } from "./ImportHubModal";
import { ConfigToAgentModal, GlobalSkillDrawer, ImportBuiltinModal } from "./";
import { useGlobalSkills } from "./useGlobalSkills";
import { GlobalSkillToolbarActions } from "./GlobalSkillToolbarActions";
import styles from "../index.module.less";

interface GlobalSkillsTabProps {
  viewMode: "card" | "list";
  onViewModeChange: (mode: "card" | "list") => void;
  onBrowseMarket: () => void;
}

export function GlobalSkillsTab({
  viewMode,
  onViewModeChange,
  onBrowseMarket,
}: GlobalSkillsTabProps) {
  const { message } = useAppMessage();
  const { selectedAgent } = useAgentStore();
  const globalSkills = useGlobalSkills();

  // Agent skills (for the "已添加" indicator - exclusive to this tab)
  const [agentSkills, setAgentSkills] = useState<SkillSpec[]>([]);
  const [addingSkill, setAddingSkill] = useState<string | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);

  const agentSkillNames = useMemo(
    () => new Set(agentSkills.map((s) => s.name)),
    [agentSkills],
  );

  const { searchQuery, setSearchQuery, filteredSkills } = useSkillFilter(
    globalSkills.skills,
  );

  // Refresh agent skills whenever the global skills data reloads
  const refreshAgentSkills = useCallback(async () => {
    if (!selectedAgent) {
      setAgentSkills([]);
      return;
    }
    try {
      const agent = await api.listSkills(selectedAgent);
      setAgentSkills(Array.isArray(agent) ? agent : []);
    } catch {
      setAgentSkills([]);
    }
  }, [selectedAgent]);

  useEffect(() => {
    void refreshAgentSkills();
  }, [refreshAgentSkills, globalSkills.skills]);

  // Progressive rendering for large lists
  const {
    visibleItems: visibleSkills,
    hasMore,
    sentinelRef,
  } = useProgressiveRender(globalSkills.sortedSkills);

  const handleAddSkill = useCallback(
    async (skillName: string) => {
      if (!selectedAgent) {
        message.warning("请先选择一个智能体");
        return;
      }
      setAddingSkill(skillName);
      try {
        await api.downloadGlobalSkill({
          skill_name: skillName,
          targets: [{ workspace_id: selectedAgent }],
        });
        message.success(`已将 ${skillName} 添加到智能体`);
        invalidateSkillCache({ agentId: selectedAgent });
        await refreshAgentSkills();
      } catch (err) {
        console.error("Failed to add skill:", err);
        message.error(err instanceof Error ? err.message : "操作失败");
      } finally {
        setAddingSkill(null);
      }
    },
    [selectedAgent, message, refreshAgentSkills],
  );

  const handleSaveNewSkill = useCallback(async () => {
    await globalSkills.handleSaveGlobalSkill();
    await refreshAgentSkills();
  }, [refreshAgentSkills, globalSkills]);

  const handleZipImport = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      await globalSkills.handleZipImport(event);
      await refreshAgentSkills();
    },
    [refreshAgentSkills, globalSkills],
  );

  const handleHubImport = useCallback(
    async (url: string, targetName?: string) => {
      await globalSkills.handleConfirmImport(url, targetName);
      await refreshAgentSkills();
    },
    [refreshAgentSkills, globalSkills],
  );

  // After config-to-agent completes, refresh agent skills
  const handleConfigToAgentDone = useCallback(async () => {
    await refreshAgentSkills();
  }, [refreshAgentSkills]);

  const addSkillButton = (
    <Button
      type="primary"
      icon={<PlusOutlined />}
      onClick={() => setAddModalOpen(true)}
    >
      添加新技能
    </Button>
  );

  const skillDrawer = (
    <GlobalSkillDrawer
      presentation="floating"
      mode={globalSkills.mode}
      activeSkill={globalSkills.activeSkill}
      form={globalSkills.form}
      drawerContent={globalSkills.drawerContent}
      showMarkdown={globalSkills.showMarkdown}
      configText={globalSkills.configText}
      workspaces={globalSkills.workspaces}
      autoUpdateEnabled={globalSkills.autoUpdateEnabled}
      autoUpdateTargets={globalSkills.autoUpdateTargets}
      onClose={globalSkills.closeDrawer}
      onSave={handleSaveNewSkill}
      onContentChange={globalSkills.handleDrawerContentChange}
      onShowMarkdownChange={globalSkills.setShowMarkdown}
      onConfigTextChange={globalSkills.setConfigText}
      onChangeBuiltinLanguage={globalSkills.handleBuiltinLanguageSwitch}
      onAutoUpdateEnabledChange={globalSkills.setAutoUpdateEnabled}
      onAutoUpdateTargetsChange={globalSkills.setAutoUpdateTargets}
      validateFrontmatter={globalSkills.validateFrontmatter}
    />
  );

  const addMechanisms = (
    <>
      <input
        type="file"
        accept=".zip"
        ref={globalSkills.zipInputRef}
        onChange={(event) => void handleZipImport(event)}
        style={{ display: "none" }}
      />
      <GlobalSkillAddModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onCreate={globalSkills.openCreate}
        onUploadZip={() => globalSkills.zipInputRef.current?.click()}
        onImportUrl={() => globalSkills.setImportModalOpen(true)}
        onBrowseMarket={onBrowseMarket}
      />
      <ImportHubModal
        open={globalSkills.importModalOpen}
        importing={globalSkills.importing}
        onCancel={globalSkills.closeImportModal}
        onConfirm={handleHubImport}
        hint="外部 Hub 导入与全局技能独立管理。"
      />
      {globalSkills.conflictRenameModal}
    </>
  );

  if (globalSkills.loading) {
    return (
      <div className={styles.loading}>
        <Spin />
        <span className={styles.loadingText}>加载中...</span>
      </div>
    );
  }

  if (globalSkills.skills.length === 0) {
    return (
      <>
        <div className={styles.noSearchResults}>
          <span className={styles.noSearchResultsIcon}>📦</span>
          <span className={styles.noSearchResultsText}>
            共享全局技能暂无可用技能
          </span>
          {addSkillButton}
        </div>
        {skillDrawer}
        {addMechanisms}
      </>
    );
  }

  // Shared renderer for card view
  const renderCard = (skill: GlobalSkillSpec) => (
    <GlobalSkillCard
      key={skill.name}
      skill={skill}
      isAdded={agentSkillNames.has(skill.name)}
      adding={addingSkill === skill.name}
      onAdd={() => handleAddSkill(skill.name)}
      isSelected={
        globalSkills.batchModeEnabled
          ? globalSkills.selectedGlobalSkills.has(skill.name)
          : undefined
      }
      batchModeEnabled={globalSkills.batchModeEnabled}
      onToggleSelect={globalSkills.toggleGlobalSelect}
      onEdit={globalSkills.openEdit}
      onConfigToAgent={globalSkills.openConfigToAgent}
      onDelete={globalSkills.handleDelete}
      onToggleAutoUpdate={globalSkills.handleToggleAutoUpdate}
    />
  );

  // Shared renderer for list view
  const renderListItem = (skill: GlobalSkillSpec) => (
    <GlobalSkillListItem
      key={skill.name}
      skill={skill}
      isAdded={agentSkillNames.has(skill.name)}
      adding={addingSkill === skill.name}
      onAdd={() => handleAddSkill(skill.name)}
      isSelected={
        globalSkills.batchModeEnabled
          ? globalSkills.selectedGlobalSkills.has(skill.name)
          : undefined
      }
      batchModeEnabled={globalSkills.batchModeEnabled}
      onToggleSelect={globalSkills.toggleGlobalSelect}
      onEdit={globalSkills.openEdit}
      onConfigToAgent={globalSkills.openConfigToAgent}
      onDelete={globalSkills.handleDelete}
    />
  );

  return (
    <>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.searchContainer}>
          <Input
            className={styles.searchInput}
            placeholder="按名称筛选"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            allowClear
          />
        </div>
        <div className={styles.toolbarRight}>
          {globalSkills.batchModeEnabled ? (
            <>
              <span className={styles.batchCount}>
                {`已选 ${globalSkills.selectedGlobalSkills.size} 个`}
              </span>
              <Button onClick={globalSkills.selectAllGlobal}>{"全选"}</Button>
              <Button
                onClick={globalSkills.clearGlobalSelection}
                icon={<CloseOutlined />}
              >
                {"清除"}
              </Button>
              <Button
                danger
                icon={<DeleteOutlined />}
                onClick={globalSkills.handleBatchDeleteGlobal}
              >
                {"删除"} ({globalSkills.selectedGlobalSkills.size})
              </Button>
              <Button type="primary" onClick={globalSkills.toggleBatchMode}>
                {"退出批量"}
              </Button>
            </>
          ) : (
            <>
              <Button
                onClick={globalSkills.handleRefresh}
                disabled={globalSkills.loading}
                loading={globalSkills.loading}
              >
                {"扫描磁盘技能"}
              </Button>
              <Button onClick={() => globalSkills.openConfigToAgent()}>
                {"配置到智能体"}
              </Button>
              <GlobalSkillToolbarActions
                hasUpdates={Boolean(globalSkills.builtinNotice?.has_updates)}
                updateCount={globalSkills.builtinNoticeTotal}
                hasUnseenUpdate={globalSkills.hasUnseenBuiltinNotice}
                onAddSkill={() => setAddModalOpen(true)}
                onStartBatch={globalSkills.toggleBatchMode}
                onManageBuiltins={globalSkills.openImportBuiltin}
              />
            </>
          )}
          <div className={styles.viewToggle}>
            <button
              className={`${styles.viewToggleBtn} ${
                viewMode === "list" ? styles.viewToggleBtnActive : ""
              }`}
              onClick={() => onViewModeChange("list")}
              title="列表视图"
            >
              <UnorderedListOutlined />
            </button>
            <button
              className={`${styles.viewToggleBtn} ${
                viewMode === "card" ? styles.viewToggleBtnActive : ""
              }`}
              onClick={() => onViewModeChange("card")}
              title="卡片视图"
            >
              <AppstoreOutlined />
            </button>
          </div>
        </div>
      </div>

      {filteredSkills.length === 0 && (
        <div className={styles.noSearchResults}>
          <span className={styles.noSearchResultsIcon}>🔍</span>
          <span className={styles.noSearchResultsText}>未找到匹配的技能</span>
        </div>
      )}

      {viewMode === "card" ? (
        <div className={styles.skillsGrid}>
          {visibleSkills.map(renderCard)}
          {hasMore && <div ref={sentinelRef} style={{ height: 1 }} />}
        </div>
      ) : (
        <div className={styles.skillsList}>
          {visibleSkills.map(renderListItem)}
          {hasMore && <div ref={sentinelRef} style={{ height: 1 }} />}
        </div>
      )}

      {skillDrawer}
      {addMechanisms}

      <ConfigToAgentModal
        open={globalSkills.mode === "config-to-agent"}
        skills={globalSkills.skills}
        workspaces={globalSkills.workspaces}
        initialSkillNames={globalSkills.configToAgentInitialNames}
        onCancel={globalSkills.closeModal}
        onConfirm={async (skillNames, workspaceIds) => {
          await globalSkills.handleConfigToAgent(skillNames, workspaceIds);
          await handleConfigToAgentDone();
        }}
      />

      <ImportBuiltinModal
        open={globalSkills.importBuiltinModalOpen}
        loading={globalSkills.importBuiltinLoading}
        sources={globalSkills.builtinSources}
        notice={globalSkills.builtinNotice}
        defaultLanguage={globalSkills.builtinLanguage}
        defaultSelectedNames={
          globalSkills.builtinNotice?.actionable_skill_names
        }
        onCancel={globalSkills.closeImportBuiltin}
        onConfirm={globalSkills.handleImportBuiltins}
      />
    </>
  );
}
