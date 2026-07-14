import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Button, Form, Modal } from "@agentscope-ai/design";
import type { GlobalSkillSpec, SkillSpec } from "../../../api/types";
import type { SkillDrawerFormValues } from "./components";
import { useConflictRenameModal } from "./components";
import { useProgressiveRender } from "../../../hooks/useProgressiveRender";
import { useAgentStore } from "../../../stores/agentStore";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import { useUploadLimitStore } from "../../../stores/uploadLimitStore";
import { invalidateSkillCache } from "../../../api/modules/skill";
import type { SecurityScanErrorResponse } from "../../../api/modules/security";
import { parseErrorDetail } from "../../../utils/error";
import {
  checkScanWarnings as checkScanWarningsShared,
  showScanErrorModal,
} from "../../../utils/scanError";
import { useSkills } from "./useSkills";
import { useSkillFilter } from "./useSkillFilter";
import { getWorkspaceSyncAction } from "./components/skillSync";
import styles from "./index.module.less";

// ─── Types ──────────────────────────────────────────────────────────────────

export type DownloadConflict =
  | { skill_name: string; reason: "conflict" }
  | {
      skill_name: string;
      reason: "builtin_upgrade";
      current_version_text: string;
      source_version_text: string;
    }
  | {
      skill_name: string;
      reason: "language_switch";
      source_language: string;
      current_language: string;
    };

// ─── Hook ───────────────────────────────────────────────────────────────────

export function useSkillsPage() {
  const { message } = useAppMessage();
  const { selectedAgent } = useAgentStore();

  const {
    skills,
    loading,
    uploading,
    importing,
    createSkill,
    uploadSkill,
    importFromHub,
    cancelImport,
    toggleEnabled,
    deleteSkill,
    refreshSkills,
    hardRefresh,
  } = useSkills();

  const { searchQuery, setSearchQuery, filteredSkills } =
    useSkillFilter(skills);

  const { showConflictRenameModal, conflictRenameModal } =
    useConflictRenameModal();

  // ── Local state ─────────────────────────────────────────────────────────

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState<SkillSpec | null>(null);
  const [form] = Form.useForm<SkillDrawerFormValues>();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [globalSkillsData, setGlobalSkillsData] = useState<GlobalSkillSpec[]>(
    [],
  );
  const [globalModal, setGlobalModal] = useState<"upload" | "download" | null>(
    null,
  );
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set());
  const [batchModeEnabled, setBatchModeEnabled] = useState(false);
  const [viewMode, setViewMode] = useState<"card" | "list">("card");
  const [filterOpen, setFilterOpen] = useState(false);
  const [promotingSkillName, setPromotingSkillName] = useState<string | null>(
    null,
  );
  const [syncConflictSkill, setSyncConflictSkill] = useState<SkillSpec | null>(
    null,
  );

  // ── Derived ─────────────────────────────────────────────────────────────

  const sortedSkills = useMemo(
    () =>
      filteredSkills.slice().sort((a, b) => {
        if (a.enabled && !b.enabled) return -1;
        if (!a.enabled && b.enabled) return 1;
        return a.name.localeCompare(b.name);
      }),
    [filteredSkills],
  );

  const {
    visibleItems: visibleSkills,
    hasMore,
    sentinelRef,
  } = useProgressiveRender(sortedSkills);

  // ── Effects ─────────────────────────────────────────────────────────────

  useEffect(() => {
    if (globalModal === "upload" || globalModal === "download") {
      void api
        .listGlobalSkills()
        .then(setGlobalSkillsData)
        .catch(() => undefined);
    }
  }, [globalModal]);

  // ── Helpers ─────────────────────────────────────────────────────────────

  const confirmOverwrite = (title: string, content: ReactNode) =>
    new Promise<boolean>((resolve) => {
      Modal.confirm({
        title,
        content,
        okText: "确认",
        cancelText: "取消",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

  const checkScanWarnings = async (skillName: string) => {
    await checkScanWarningsShared(
      skillName,
      api.getBlockedHistory,
      api.getSkillScanner,
    );
  };

  const toggleSelect = (name: string) => {
    setSelectedSkills((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const clearSelection = () => setSelectedSkills(new Set());

  const selectAll = () =>
    setSelectedSkills(new Set(filteredSkills.map((s) => s.name)));

  const toggleBatchMode = () => {
    if (batchModeEnabled) {
      clearSelection();
      setBatchModeEnabled(false);
    } else {
      setBatchModeEnabled(true);
    }
  };

  const closeGlobalModal = () => setGlobalModal(null);

  const handleUploadClick = () => fileInputRef.current?.click();

  // ── File upload ─────────────────────────────────────────────────────────

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    if (!file.name.toLowerCase().endsWith(".zip")) {
      message.warning("仅支持上传 .zip 文件");
      return;
    }
    const sizeMB = file.size / (1024 * 1024);
    const uploadLimit = useUploadLimitStore.getState().uploadMaxSizeMb;
    if (uploadLimit !== null && sizeMB > uploadLimit) {
      message.warning(
        `文件大小超过 ${uploadLimit}MB 限制。当前文件：${sizeMB.toFixed(1)}MB`,
      );
      return;
    }
    let renameMap: Record<string, string> | undefined;
    while (true) {
      const result = await uploadSkill(file, undefined, renameMap);
      if (result.success || !result.conflict) break;
      const conflicts = Array.isArray(result.conflict.conflicts)
        ? result.conflict.conflicts
        : [];
      if (conflicts.length === 0) break;
      const newRenames = await showConflictRenameModal(
        conflicts.map((conflict) => ({
          key: String(conflict.skill_name || ""),
          label: String(conflict.skill_name || ""),
          suggested_name: String(conflict.suggested_name || ""),
        })),
      );
      if (!newRenames) break;
      renameMap = { ...renameMap, ...newRenames };
    }
  };

  // ── Create / Edit / Delete ──────────────────────────────────────────────

  const handleCreate = () => {
    setEditingSkill(null);
    form.resetFields();
    form.setFieldsValue({ enabled: false, channels: ["all"] });
    setDrawerOpen(true);
  };

  const closeImportModal = () => {
    if (importing) return;
    setImportModalOpen(false);
  };

  const handleConfirmImport = async (url: string, targetName?: string) => {
    const result = await importFromHub(url, targetName);
    if (result.success) {
      closeImportModal();
    } else if (result.conflict) {
      const detail = result.conflict;
      const suggested =
        detail?.suggested_name || detail?.conflicts?.[0]?.suggested_name;
      if (suggested) {
        const skillName =
          detail?.skill_name || detail?.conflicts?.[0]?.skill_name || "";
        const renameMap = await showConflictRenameModal([
          {
            key: skillName,
            label: skillName,
            suggested_name: String(suggested),
          },
        ]);
        if (renameMap) {
          const newName = Object.values(renameMap)[0];
          if (newName) await handleConfirmImport(url, newName);
        }
      }
    }
  };

  const handleEdit = (skill: SkillSpec) => {
    setEditingSkill(skill);
    form.setFieldsValue({
      name: skill.name,
      description: skill.description,
      content: skill.content,
      enabled: skill.enabled,
      channels: skill.channels,
    });
    setDrawerOpen(true);
  };

  const handleToggleEnabled = async (skill: SkillSpec) => {
    await toggleEnabled(skill);
    await refreshSkills();
  };

  const handleDelete = async (skill: SkillSpec, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await deleteSkill(skill);
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setEditingSkill(null);
  };

  // ── Drawer submit ───────────────────────────────────────────────────────

  const handleSubmit = async (values: SkillSpec) => {
    if (editingSkill) {
      const sourceName = editingSkill.name;
      const targetName = values.name;
      const saveEditedSkill = async (overwrite = false) => {
        const result = await api.saveSkill({
          name: targetName,
          content: values.content,
          source_name: sourceName !== targetName ? sourceName : undefined,
          config: values.config,
          overwrite,
        });
        const sideUpdates: Promise<unknown>[] = [];
        const newChannels = values.channels || ["all"];
        if (
          JSON.stringify(newChannels) !==
          JSON.stringify(editingSkill.channels || ["all"])
        ) {
          sideUpdates.push(api.updateSkillChannels(result.name, newChannels));
        }
        await Promise.all(sideUpdates);
        if (result.mode === "noop" && sideUpdates.length === 0) {
          setDrawerOpen(false);
          return;
        }
        if (result.mode !== "noop") {
          message.success(
            result.mode === "rename" ? `${"保存"}: ${result.name}` : "保存",
          );
        }
        setDrawerOpen(false);
        invalidateSkillCache({ agentId: selectedAgent });
        await refreshSkills();
      };
      try {
        await saveEditedSkill();
      } catch (error) {
        const detail = parseErrorDetail(error);
        if (detail?.reason === "conflict") {
          const confirmed = await confirmOverwrite(
            "覆盖已存在的技能？",
            <div style={{ display: "grid", gap: 8 }}>
              <div>{"以下技能已存在，确认后将直接覆盖："}</div>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>{targetName}</li>
              </ul>
            </div>,
          );
          if (!confirmed) return;
          try {
            await saveEditedSkill(true);
          } catch (retryError) {
            message.error(
              retryError instanceof Error ? retryError.message : "保存",
            );
          }
        } else {
          message.error(error instanceof Error ? error.message : "保存");
        }
      }
    } else {
      const submitName = values.name;
      const result = await createSkill(
        submitName,
        values.content,
        values.config,
        true,
      );
      if (result.success) {
        const actualName = result.name || submitName;
        await api.updateSkillChannels(actualName, values.channels || ["all"]);
        setDrawerOpen(false);
        invalidateSkillCache({ agentId: selectedAgent });
        await refreshSkills();
        return;
      }
      if (result.conflict?.suggested_name) {
        const renameMap = await showConflictRenameModal([
          {
            key: submitName,
            label: submitName,
            suggested_name: result.conflict!.suggested_name,
          },
        ]);
        if (renameMap) {
          const newName = Object.values(renameMap)[0];
          if (newName) await handleSubmit({ ...values, name: newName });
        }
      }
    }
  };

  const handlePromoteToGlobal = async (skill: SkillSpec) => {
    if (promotingSkillName) return;

    const isNewGlobalSkill = !skill.in_global;
    const needsConflictChoice =
      skill.sync_status === "conflict" ||
      (Boolean(skill.in_global) && !skill.last_synced_hash);

    if (!needsConflictChoice) {
      const confirmed = await confirmOverwrite(
        isNewGlobalSkill ? "发布为全局技能？" : "晋升为全局版本？",
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            {isNewGlobalSkill
              ? `将当前智能体中的“${skill.name}”发布到全局技能。`
              : `将当前智能体中调优后的“${skill.name}”设为新的全局版本。`}
          </div>
          <div style={{ color: "rgba(20, 20, 19, 0.58)" }}>
            这次操作不会自动覆盖其他智能体中的副本，也不会上传当前智能体的私有配置。
          </div>
        </div>,
      );
      if (!confirmed) return;
    }

    const promote = async (force: boolean, expectedGlobalHash?: string) =>
      api.promoteSkillToGlobal(
        skill.name,
        {
          force,
          expected_global_hash: expectedGlobalHash,
          include_config: false,
          propagate: false,
        },
        selectedAgent,
      );

    setPromotingSkillName(skill.name);
    try {
      let result: Awaited<ReturnType<typeof api.promoteSkillToGlobal>>;
      try {
        result = await promote(false, skill.global_hash);
      } catch (error) {
        const detail = parseErrorDetail(error);
        const forceable = [
          "conflict",
          "not_linked",
          "outdated_global",
          "stale_global",
        ].includes(String(detail?.reason || ""));
        if (!forceable) throw error;
        setSyncConflictSkill({
          ...skill,
          sync_status: "conflict",
          global_hash: String(detail?.global_hash || skill.global_hash || ""),
          agent_hash: String(detail?.agent_hash || skill.agent_hash || ""),
        });
        return;
      }

      message.success(
        result.mode === "noop"
          ? "当前智能体技能已与全局一致"
          : isNewGlobalSkill
          ? "已发布为全局技能"
          : "已晋升为新的全局版本",
      );
      invalidateSkillCache({
        agentId: selectedAgent,
        global: true,
        workspaces: true,
      });
      await refreshSkills();
    } catch (error) {
      message.error(
        error instanceof Error ? error.message : "同步到全局技能失败",
      );
    } finally {
      setPromotingSkillName(null);
    }
  };

  const refreshAfterSync = async () => {
    invalidateSkillCache({
      agentId: selectedAgent,
      global: true,
      workspaces: true,
    });
    await refreshSkills();
  };

  const handleResolveSkillSync = async (
    skill: SkillSpec,
    resolution: "keep_global" | "keep_agent",
  ) => {
    if (promotingSkillName) return;
    setPromotingSkillName(skill.name);
    try {
      await api.resolveSkillSync(skill.name, resolution, selectedAgent);
      setSyncConflictSkill(null);
      await refreshAfterSync();
      message.success(
        resolution === "keep_global"
          ? "已使用全局版本更新当前智能体"
          : "已将智能体版本同步到全局",
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "技能同步失败");
    } finally {
      setPromotingSkillName(null);
    }
  };

  const handleSyncSkill = async (skill: SkillSpec) => {
    const action = getWorkspaceSyncAction(skill);
    if (!action || promotingSkillName) return;

    if (action === "resolve") {
      setSyncConflictSkill(skill);
      return;
    }

    if (action === "pull") {
      const confirmed = await confirmOverwrite(
        "使用全局版本更新智能体？",
        <div style={{ display: "grid", gap: 8 }}>
          <div>将全局技能“{skill.name}”的最新内容更新到当前智能体。</div>
          <div style={{ color: "rgba(20, 20, 19, 0.58)" }}>
            当前状态表明智能体副本没有本地改动；运行配置和启用状态会保留。
          </div>
        </div>,
      );
      if (!confirmed) return;
      await handleResolveSkillSync(skill, "keep_global");
      return;
    }

    await handlePromoteToGlobal(skill);
  };

  // ── Pool transfer ───────────────────────────────────────────────────────

  const handleUploadToGlobal = async (workspaceSkillNames: string[]) => {
    if (workspaceSkillNames.length === 0) return;
    try {
      const conflictingNames: string[] = [];
      for (const skillName of workspaceSkillNames) {
        try {
          await api.uploadWorkspaceSkillToGlobal({
            workspace_id: selectedAgent,
            skill_name: skillName,
            preview_only: true,
          });
        } catch (error) {
          const detail = parseErrorDetail(error);
          if (detail?.reason === "conflict") {
            conflictingNames.push(skillName);
            continue;
          }
          throw error;
        }
      }
      if (conflictingNames.length > 0) {
        const confirmed = await confirmOverwrite(
          "覆盖已存在的技能？",
          <div style={{ display: "grid", gap: 8 }}>
            <div>{"以下技能已存在，确认后将直接覆盖："}</div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {conflictingNames.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          </div>,
        );
        if (!confirmed) return;
      }
      for (const skillName of workspaceSkillNames) {
        await api.uploadWorkspaceSkillToGlobal({
          workspace_id: selectedAgent,
          skill_name: skillName,
          overwrite: conflictingNames.includes(skillName),
        });
      }
      message.success("已上传至全局技能");
      closeGlobalModal();
      invalidateSkillCache({ agentId: selectedAgent, global: true });
      await refreshSkills();
      setGlobalSkillsData(await api.listGlobalSkills());
    } catch (error) {
      message.error(error instanceof Error ? error.message : "技能上传失败");
    }
  };

  const handleDownloadFromGlobal = async (poolSkillNames: string[]) => {
    if (poolSkillNames.length === 0) return;
    try {
      const conflicts: DownloadConflict[] = [];
      for (const skillName of poolSkillNames) {
        try {
          await api.downloadGlobalSkill({
            skill_name: skillName,
            targets: [{ workspace_id: selectedAgent }],
            preview_only: true,
          });
        } catch (error) {
          const detail = parseErrorDetail(error);
          const returnedConflicts = Array.isArray(detail?.conflicts)
            ? detail.conflicts
            : [];
          if (!returnedConflicts.length) throw error;
          conflicts.push(
            ...returnedConflicts.map((conflict): DownloadConflict => {
              if (conflict?.reason === "builtin_upgrade") {
                return {
                  skill_name: conflict.skill_name || skillName,
                  reason: "builtin_upgrade" as const,
                  current_version_text: conflict.current_version_text || "",
                  source_version_text: conflict.source_version_text || "",
                };
              }
              if (conflict?.reason === "language_switch") {
                return {
                  skill_name: conflict.skill_name || skillName,
                  reason: "language_switch" as const,
                  source_language: conflict.source_language || "",
                  current_language: conflict.current_language || "",
                };
              }
              return {
                skill_name: conflict?.skill_name || skillName,
                reason: "conflict" as const,
              };
            }),
          );
        }
      }
      if (conflicts.length > 0) {
        const allBuiltinUpgrades = conflicts.every(
          (c) => c.reason === "builtin_upgrade",
        );
        const allLanguageSwitch = conflicts.every(
          (c) => c.reason === "language_switch",
        );
        const title = allBuiltinUpgrades
          ? "升级内置技能"
          : allLanguageSwitch
          ? "切换技能语言"
          : "覆盖已存在的技能？";
        const subtitle = allBuiltinUpgrades
          ? "以下目标中的内置技能版本不同，确认后将直接覆盖："
          : allLanguageSwitch
          ? "以下技能在池中有不同的语言版本，确认后将覆盖："
          : "以下技能已存在，确认后将直接覆盖：";
        const confirmed = await confirmOverwrite(
          title,
          <div style={{ display: "grid", gap: 8 }}>
            <div>{subtitle}</div>
            {conflicts.map((conflict) => (
              <div key={conflict.skill_name}>
                <strong>{conflict.skill_name}</strong>
                {conflict.reason === "builtin_upgrade" ? (
                  <>
                    {"  "}
                    {"当前版本"}: {conflict.current_version_text || "-"}
                    {"  ->  "}
                    {"源码版本"}: {conflict.source_version_text || "-"}
                  </>
                ) : null}
                {conflict.reason === "language_switch" ? (
                  <>
                    {"  "}
                    {conflict.current_language === "zh" ? "中文" : "英文"}
                    {"  →  "}
                    {conflict.source_language === "zh" ? "中文" : "英文"}
                  </>
                ) : null}
              </div>
            ))}
          </div>,
        );
        if (!confirmed) return;
      }
      for (const skillName of poolSkillNames) {
        const shouldOverwrite = conflicts.some(
          (c) => c.skill_name === skillName,
        );
        await api.downloadGlobalSkill({
          skill_name: skillName,
          targets: [{ workspace_id: selectedAgent }],
          overwrite: shouldOverwrite,
        });
      }
      message.success("已下载至当前工作区");
      closeGlobalModal();
      invalidateSkillCache({ agentId: selectedAgent, global: true });
      await refreshSkills();
    } catch (error) {
      message.error(
        error instanceof Error ? error.message : "下载" + " failed",
      );
    }
  };

  // ── Batch enable / disable ───────────────────────────────────────────────

  const handleBatchEnable = async () => {
    const names = Array.from(selectedSkills);
    if (names.length === 0) return;
    try {
      const { results } = await api.batchEnableSkills(names);
      const entries = Object.entries(results);
      const succeeded = entries
        .filter(([, r]) => r.success)
        .map(([name]) => name);
      const failed = entries.filter(([, r]) => r.success === false);
      for (const [, result] of failed) {
        const detail = result.detail;
        if (result.reason !== "security_scan_failed" || !detail) continue;
        showScanErrorModal(detail as SecurityScanErrorResponse);
      }
      if (failed.length > 0) {
        message.warning(
          `${names.length - failed.length} 个已启用，${failed.length} 个失败`,
        );
      } else {
        message.success(`已启用 ${names.length} 个技能`);
      }
      clearSelection();
      invalidateSkillCache({ agentId: selectedAgent });
      await refreshSkills();
      for (const name of succeeded) {
        await checkScanWarnings(name);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : "批量启用失败");
    }
  };

  const handleBatchDisable = async () => {
    const names = Array.from(selectedSkills);
    if (names.length === 0) return;
    try {
      const { results } = await api.batchDisableSkills(names);
      const failed = Object.entries(results).filter(([, r]) => !r.success);
      if (failed.length > 0) {
        message.warning(
          `${names.length - failed.length} 个已禁用，${failed.length} 个失败`,
        );
      } else {
        message.success(`已禁用 ${names.length} 个技能`);
      }
      clearSelection();
      invalidateSkillCache({ agentId: selectedAgent });
      await refreshSkills();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "批量禁用失败");
    }
  };

  // ── Batch delete ────────────────────────────────────────────────────────

  const handleBatchDelete = async () => {
    const names = Array.from(selectedSkills);
    if (names.length === 0) return;
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: `删除 ${names.length} 个技能？`,
        content: (
          <ul style={{ margin: "8px 0", paddingLeft: 20 }}>
            {names.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ),
        okText: "删除",
        okType: "danger",
        cancelText: "取消",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });
    if (!confirmed) return;
    try {
      const { results } = await api.batchDeleteSkills(names);
      const failed = Object.entries(results).filter(([, r]) => !r.success);
      if (failed.length > 0) {
        message.warning(
          `${names.length - failed.length} 个已删除，${failed.length} 个失败`,
        );
      } else {
        message.success(`已删除 ${names.length} 个技能`);
      }
      clearSelection();
      invalidateSkillCache({ agentId: selectedAgent });
      await refreshSkills();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "批量删除失败");
    }
  };

  const syncConflictModal = (
    <Modal
      title={
        syncConflictSkill?.sync_status === "conflict"
          ? "解决技能同步冲突"
          : "选择要保留的技能版本"
      }
      open={Boolean(syncConflictSkill)}
      onCancel={() => {
        if (!promotingSkillName) setSyncConflictSkill(null);
      }}
      destroyOnClose
      footer={
        <div className={styles.syncConflictFooter}>
          <Button
            onClick={() => setSyncConflictSkill(null)}
            disabled={Boolean(promotingSkillName)}
          >
            取消
          </Button>
          <Button
            loading={Boolean(promotingSkillName)}
            onClick={() => {
              if (syncConflictSkill) {
                void handleResolveSkillSync(syncConflictSkill, "keep_global");
              }
            }}
          >
            使用全局版本
          </Button>
          <Button
            type="primary"
            danger={syncConflictSkill?.sync_status === "conflict"}
            loading={Boolean(promotingSkillName)}
            onClick={() => {
              if (syncConflictSkill) {
                void handleResolveSkillSync(syncConflictSkill, "keep_agent");
              }
            }}
          >
            使用智能体版本并同步到全局
          </Button>
        </div>
      }
    >
      {syncConflictSkill && (
        <div className={styles.syncConflictBody}>
          <div className={styles.syncConflictSkillName}>
            {syncConflictSkill.name}
          </div>
          <p>
            {syncConflictSkill.sync_status === "conflict"
              ? "智能体版本和全局版本都发生了变化，系统不会自动覆盖任何一方。"
              : "当前智能体和全局存在同名但内容不同的技能，尚未建立可验证的同步基线。"}
          </p>
          <p className={styles.syncConflictNotice}>
            选择智能体版本只会更新全局源，不会自动覆盖其他智能体中的副本。
          </p>
        </div>
      )}
    </Modal>
  );

  return {
    skills,
    sortedSkills,
    visibleSkills,
    hasMore,
    sentinelRef,
    globalSkillsData,
    filteredSkills,
    conflictRenameModal,
    syncConflictModal,
    loading,
    uploading,
    importing,
    drawerOpen,
    importModalOpen,
    setImportModalOpen,
    editingSkill,
    form,
    fileInputRef,
    globalModal,
    setGlobalModal,
    selectedSkills,
    batchModeEnabled,
    viewMode,
    setViewMode,
    filterOpen,
    setFilterOpen,
    promotingSkillName,
    searchQuery,
    setSearchQuery,
    handleCreate,
    handleEdit,
    handleToggleEnabled,
    handleDelete,
    handleDrawerClose,
    handleSubmit,
    handleSyncSkill,
    handleUploadToGlobal,
    handleDownloadFromGlobal,
    handleBatchEnable,
    handleBatchDisable,
    handleBatchDelete,
    handleUploadClick,
    handleFileChange,
    handleConfirmImport,
    closeImportModal,
    closeGlobalModal,
    toggleSelect,
    clearSelection,
    selectAll,
    toggleBatchMode,
    toggleEnabled,
    refreshSkills,
    hardRefresh,
    cancelImport,
  };
}
