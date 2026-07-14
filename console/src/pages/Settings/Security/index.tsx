import { Button, Tabs } from "@agentscope-ai/design";
import { useSecurityPage } from "./useSecurityPage";
import {
  ToolGuardTab,
  RuleModal,
  PreviewModal,
  SkillScannerSection,
  FileGuardSection,
  AllowNoAuthHostsTab,
} from "./components";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

function SecurityPage() {

  const {
    activeTab,
    setActiveTab,
    form,
    config,
    enabled,
    setEnabled,
    toolOptions,
    saving,
    handleSave,
    handleReset,
    mergedRules,
    builtinRules,
    customRules,
    toggleRule,
    toggleAutoDeny,
    deleteCustomRule,
    openAddRule,
    openEditRule,
    shellEvasionChecks,
    toggleShellEvasionCheck,
    editModal,
    setEditModal,
    editingRule,
    editForm,
    handleEditSave,
    previewRule,
    setPreviewRule,
    fileGuardHandlers,
    onFileGuardHandlersReady,
    allowNoAuthHostsHandlers,
    onAllowNoAuthHostsHandlersReady,
    loading,
    error,
    fetchAll,
  } = useSecurityPage();

  // Loading state
  if (loading) {
    return (
      <div className={styles.securityPage}>
        <div className={styles.centerState}>
          <span className={styles.stateText}>{"加载中..."}</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={styles.securityPage}>
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={fetchAll} style={{ marginTop: 12 }}>
            {"重试"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.securityPage}>
      <PageHeader
        parent={"设置"}
        current={"安全"}
      />

      <div className={styles.content}>
        <Tabs
          className={styles.mainTabs}
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: "toolGuard",
              label: (
                <span className={styles.tabLabel}>
                  {"工具防护"}
                </span>
              ),
              children: (
                <ToolGuardTab
                  form={form}
                  config={config}
                  enabled={enabled}
                  setEnabled={setEnabled}
                  toolOptions={toolOptions}
                  mergedRules={mergedRules}
                  toggleRule={toggleRule}
                  toggleAutoDeny={toggleAutoDeny}
                  onPreviewRule={setPreviewRule}
                  onEditRule={openEditRule}
                  onDeleteRule={deleteCustomRule}
                  openAddRule={openAddRule}
                  shellEvasionChecks={shellEvasionChecks}
                  toggleShellEvasionCheck={toggleShellEvasionCheck}
                />
              ),
            },
            {
              key: "fileGuard",
              label: (
                <span className={styles.tabLabel}>
                  {"文件防护"}
                </span>
              ),
              children: (
                <div className={styles.tabContent}>
                  <div className={styles.sectionFileGuardContainer}>
                    <p className={styles.tabDescription}>
                      {"保护敏感文件和目录，防止被 Agent 工具访问。添加的路径将在所有工具调用中被拦截。"}
                    </p>
                    <FileGuardSection onSave={onFileGuardHandlersReady} />
                  </div>
                </div>
              ),
            },
            {
              key: "skillScanner",
              label: (
                <span className={styles.tabLabel}>
                  {"技能扫描器"}
                </span>
              ),
              children: (
                <div className={styles.tabContent}>
                  <div className={styles.sectionSkillScannerContainer}>
                    <p className={styles.tabDescription}>
                      {"在启用或安装技能前，自动扫描安全威胁。不安全的技能可以被拦截或加入白名单。"}
                    </p>
                    <SkillScannerSection />
                  </div>
                </div>
              ),
            },
            {
              key: "allowNoAuthHosts",
              label: (
                <span className={styles.tabLabel}>
                  {"免认证主机白名单"}
                </span>
              ),
              children: (
                <AllowNoAuthHostsTab onSave={onAllowNoAuthHostsHandlersReady} />
              ),
            },
          ]}
        />
      </div>

      {activeTab === "toolGuard" && (
        <div className={styles.footerButtons}>
          <Button
            onClick={handleReset}
            disabled={saving}
            style={{ marginRight: 8 }}
          >
            {"重置"}
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            {"保存"}
          </Button>
        </div>
      )}

      {activeTab === "fileGuard" && fileGuardHandlers && (
        <div className={styles.footerButtons}>
          <Button
            onClick={fileGuardHandlers.reset}
            disabled={fileGuardHandlers.saving}
            style={{ marginRight: 8 }}
          >
            {"重置"}
          </Button>
          <Button
            type="primary"
            onClick={fileGuardHandlers.save}
            loading={fileGuardHandlers.saving}
          >
            {"保存"}
          </Button>
        </div>
      )}

      {activeTab === "allowNoAuthHosts" && allowNoAuthHostsHandlers && (
        <div className={styles.footerButtons}>
          <Button
            onClick={allowNoAuthHostsHandlers.reset}
            disabled={allowNoAuthHostsHandlers.saving}
            style={{ marginRight: 8 }}
          >
            {"重置"}
          </Button>
          <Button
            type="primary"
            onClick={allowNoAuthHostsHandlers.save}
            loading={allowNoAuthHostsHandlers.saving}
          >
            {"保存"}
          </Button>
        </div>
      )}

      <RuleModal
        open={editModal}
        editingRule={editingRule}
        existingRuleIds={[
          ...builtinRules.map((r) => r.id),
          ...customRules.map((r) => r.id),
        ]}
        onOk={handleEditSave}
        onCancel={() => setEditModal(false)}
        form={editForm}
      />

      <PreviewModal rule={previewRule} onClose={() => setPreviewRule(null)} />
    </div>
  );
}

export default SecurityPage;
