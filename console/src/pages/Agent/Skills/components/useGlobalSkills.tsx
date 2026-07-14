import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Modal, Form } from "@agentscope-ai/design";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import api from "../../../../api";
import { invalidateSkillCache } from "../../../../api/modules/skill";
import type {
  BuiltinImportSpec,
  BuiltinUpdateNotice,
  GlobalSkillSpec,
  WorkspaceSkillSummary,
} from "../../../../api/types";
import { parseErrorDetail } from "../../../../utils/error";
import { handleScanError, checkScanWarnings } from "../../../../utils/scanError";
import { getAgentDisplayName } from "../../../../utils/agentDisplayName";
import {
  parseFrontmatter,
  useConflictRenameModal,
} from "./";
import { useSkillFilter } from "../useSkillFilter";
import { useUploadLimitStore } from "../../../../stores/uploadLimitStore";

export type GlobalSkillMode = "config-to-agent" | "create" | "edit";

type BuiltinSkillLanguage = "en" | "zh";
interface BuiltinImportSelection {
  skill_name: string;
  language: BuiltinSkillLanguage;
}

type ConfigToAgentConflict =
  | {
      skill_name: string;
      workspace_id: string;
      workspace_name: string;
      reason: "conflict";
    }
  | {
      skill_name: string;
      workspace_id: string;
      workspace_name: string;
      reason: "builtin_upgrade";
      current_version_text: string;
      source_version_text: string;
    }
  | {
      skill_name: string;
      workspace_id: string;
      workspace_name: string;
      reason: "language_switch";
      source_language: string;
      current_language: string;
    };

const BUILTIN_NOTICE_ACK_STORAGE_KEY = "minions.global-skills.builtin-notice.ack";

function readBuiltinNoticeAcknowledgement(): string {
  if (typeof window === "undefined") return "";
  try {
    return localStorage.getItem(BUILTIN_NOTICE_ACK_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function writeBuiltinNoticeAcknowledgement(fingerprint: string): void {
  if (typeof window === "undefined" || !fingerprint) return;
  try {
    localStorage.setItem(BUILTIN_NOTICE_ACK_STORAGE_KEY, fingerprint);
  } catch {
    // Ignore storage failures and fall back to in-memory state.
  }
}

export function useGlobalSkills() {
    const [skills, setSkills] = useState<GlobalSkillSpec[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceSkillSummary[]>([]);
  const [builtinNotice, setBuiltinNotice] =
    useState<BuiltinUpdateNotice | null>(null);
  const [builtinNoticeAck, setBuiltinNoticeAck] = useState<string>(() =>
    readBuiltinNoticeAcknowledgement(),
  );
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<GlobalSkillMode | null>(null);
  const [activeSkill, setActiveSkill] = useState<GlobalSkillSpec | null>(null);
  const [configToAgentInitialNames, setConfigToAgentInitialNames] = useState<string[]>(
    [],
  );
  const [configText, setConfigText] = useState("{}");
  // Auto-update is staged in the edit drawer and applied on Save; the card
  // has a separate immediate quick-toggle.
  const [autoUpdateEnabled, setAutoUpdateEnabled] = useState(false);
  const [autoUpdateTargets, setAutoUpdateTargets] = useState<string[]>([]);
  const zipInputRef = useRef<HTMLInputElement>(null);
  const [importBuiltinModalOpen, setImportBuiltinModalOpen] = useState(false);
  const [builtinSources, setBuiltinSources] = useState<BuiltinImportSpec[]>([]);
  const [importBuiltinLoading, setImportBuiltinLoading] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const { showConflictRenameModal, conflictRenameModal } =
    useConflictRenameModal();
  const { message } = useAppMessage();
  const [selectedGlobalSkills, setSelectedGlobalSkills] = useState<Set<string>>(
    new Set(),
  );
  const [batchModeEnabled, setBatchModeEnabled] = useState(false);
  const [viewMode, setViewMode] = useState<"card" | "list">("card");
  const [filterOpen, setFilterOpen] = useState(false);
  const {
    searchQuery,
    setSearchQuery,
    filteredSkills,
  } = useSkillFilter(skills);

  const builtinLanguage: BuiltinSkillLanguage = "zh";

  const sortedSkills = useMemo(
    () => filteredSkills.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [filteredSkills],
  );
  const hasUnseenBuiltinNotice = useMemo(
    () =>
      Boolean(
        builtinNotice?.has_updates &&
          builtinNotice.fingerprint &&
          builtinNotice.fingerprint !== builtinNoticeAck,
      ),
    [builtinNotice, builtinNoticeAck],
  );
  const builtinNoticeTotal = builtinNotice?.total_changes || 0;

  const confirmOverwrite = useCallback(
    (title: string, content: ReactNode) =>
      new Promise<boolean>((resolve) => {
        Modal.confirm({
          title,
          content,
          okText: "确认",
          cancelText: "取消",
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      }),
    [],
  );

  const toggleGlobalSelect = (name: string) => {
    setSelectedGlobalSkills((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const clearGlobalSelection = () => {
    setSelectedGlobalSkills(new Set());
    setBatchModeEnabled(false);
  };

  const toggleBatchMode = () => {
    if (batchModeEnabled) {
      clearGlobalSelection();
    } else {
      setBatchModeEnabled(true);
    }
  };

  const selectAllGlobal = () =>
    setSelectedGlobalSkills(new Set(filteredSkills.map((s) => s.name)));

  // Form state for create/edit drawer
  const [form] = Form.useForm();
  const [drawerContent, setDrawerContent] = useState("");
  const [showMarkdown, setShowMarkdown] = useState(true);

  // Use ref to cache data and avoid unnecessary reloads
  const dataLoadedRef = useRef(false);

  const markBuiltinNoticeSeen = useCallback(
    (fingerprint?: string) => {
      const nextFingerprint = String(
        fingerprint || builtinNotice?.fingerprint || "",
      ).trim();
      if (!nextFingerprint) return;
      writeBuiltinNoticeAcknowledgement(nextFingerprint);
      setBuiltinNoticeAck(nextFingerprint);
    },
    [builtinNotice],
  );

  const loadData = useCallback(
    async (forceReload = false) => {
      if (dataLoadedRef.current && !forceReload) return;

      setLoading(true);
      try {
        const [globalSkillsData, workspaceSummaries, notice] = await Promise.all([
          api.listGlobalSkills(),
          api.listSkillWorkspaces(),
          api.getGlobalBuiltinNotice(),
        ]);
        setSkills(globalSkillsData);
        setWorkspaces(workspaceSummaries);
        setBuiltinNotice(notice);
        dataLoadedRef.current = true;
      } catch (error) {
        message.error(
          error instanceof Error ? error.message : "Failed to load global skills",
        );
      } finally {
        setLoading(false);
      }
    },
    [message],
  );

  const handleRefresh = useCallback(async () => {
    setLoading(true);
    try {
      invalidateSkillCache({ global: true, workspaces: true });
      const [globalSkillsData, workspaceSummaries, notice] = await Promise.all([
        api.refreshGlobalSkills(),
        api.listSkillWorkspaces(),
        api.getGlobalBuiltinNotice(),
      ]);
      setSkills(globalSkillsData);
      setWorkspaces(workspaceSummaries);
      setBuiltinNotice(notice);
      dataLoadedRef.current = true;
    } catch (error) {
      message.error(
        error instanceof Error ? error.message : "Failed to refresh",
      );
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const closeModal = () => {
    setMode(null);
    setConfigToAgentInitialNames([]);
    setConfigText("{}");
  };

  const openCreate = () => {
    setMode("create");
    setDrawerContent("");
    setConfigText("{}");
    setAutoUpdateEnabled(false);
    setAutoUpdateTargets([]);
    form.resetFields();
    form.setFieldsValue({
      name: "",
      content: "",
    });
  };

  const openConfigToAgent = (skill?: GlobalSkillSpec) => {
    setMode("config-to-agent");
    setConfigToAgentInitialNames(skill ? [skill.name] : []);
  };

  const openImportBuiltin = async () => {
    try {
      setImportBuiltinLoading(true);
      const [sources, notice] = await Promise.all([
        api.listGlobalBuiltinSources(),
        api.getGlobalBuiltinNotice(),
      ]);
      setBuiltinSources(sources);
      setBuiltinNotice(notice);
      setImportBuiltinModalOpen(true);
      if (notice.has_updates && notice.fingerprint) {
        markBuiltinNoticeSeen(notice.fingerprint);
      }
    } catch (error) {
      message.error(
        error instanceof Error
          ? error.message
          : "导入内置技能失败",
      );
    } finally {
      setImportBuiltinLoading(false);
    }
  };

  const closeImportBuiltin = () => {
    if (importBuiltinLoading) return;
    setImportBuiltinModalOpen(false);
  };

  const closeImportModal = () => {
    if (importing) return;
    setImportModalOpen(false);
  };

  const getBuiltinImportStatusLabel = useCallback(
    (status?: string, language?: string) => {
      switch (status) {
        case "outdated":
          return "版本落后";
        case "language_switch":
          return `将覆盖为${language === "zh" ? "中文" : "英文"}版本`;
        case "conflict":
          return "冲突";
        default:
          return "";
      }
    },
    [],
  );

  const openEdit = (skill: GlobalSkillSpec) => {
    setMode("edit");
    setActiveSkill(skill);
    setDrawerContent(skill.content);
    setConfigText(JSON.stringify(skill.config || {}, null, 2));
    setAutoUpdateEnabled(Boolean(skill.auto_update));
    setAutoUpdateTargets(skill.auto_update_targets ?? []);
    form.setFieldsValue({
      name: skill.name,
      content: skill.content,
    });
  };

  const closeDrawer = useCallback(() => {
    setMode(null);
    setActiveSkill(null);
  }, []);

  const handleDrawerContentChange = (content: string) => {
    setDrawerContent(content);
    form.setFieldsValue({ content });
  };

  const validateFrontmatter = useCallback(
    (_: unknown, value: string) => {
      const content = drawerContent || value;
      if (!content || !content.trim()) {
        return Promise.reject(new Error("请输入技能内容"));
      }
      const fm = parseFrontmatter(content);
      if (!fm) {
        return Promise.reject(new Error("Skills内容必须以 --- 开头和结尾"));
      }
      if (!fm.name) {
        return Promise.reject(new Error("Skills 中缺少必填字段：name"));
      }
      if (!fm.description) {
        return Promise.reject(
          new Error("Skills 中缺少必填字段：description"),
        );
      }
      return Promise.resolve();
    },
    [drawerContent],
  );

  const handleConfigToAgent = async (
    configToAgentSkillNames: string[],
    targetWorkspaceIds: string[],
  ) => {
    try {
      const conflicts: ConfigToAgentConflict[] = [];
      for (const skillName of configToAgentSkillNames) {
        try {
          await api.downloadGlobalSkill({
            skill_name: skillName,
            targets: targetWorkspaceIds.map((workspace_id) => ({
              workspace_id,
            })),
            preview_only: true,
          });
        } catch (error) {
          if (handleScanError(error)) return;
          const detail = parseErrorDetail(error);
          const returnedConflicts = Array.isArray(detail?.conflicts)
            ? detail.conflicts
            : [];
          if (!returnedConflicts.length) {
            throw error;
          }
          conflicts.push(
            ...returnedConflicts.map((conflict): ConfigToAgentConflict => {
              const base = {
                skill_name: conflict.skill_name || skillName,
                workspace_id: conflict.workspace_id || "",
                workspace_name:
                  conflict.workspace_name ||
                  getAgentDisplayName(
                    {
                      id: conflict.workspace_id || "",
                      name:
                        workspaces.find(
                          (workspace) =>
                            workspace.agent_id === conflict.workspace_id,
                        )?.agent_name ?? "",
                    },
                  ),
              };
              if (conflict.reason === "builtin_upgrade") {
                return {
                  ...base,
                  reason: "builtin_upgrade" as const,
                  current_version_text: conflict.current_version_text || "",
                  source_version_text: conflict.source_version_text || "",
                };
              }
              if (conflict.reason === "language_switch") {
                return {
                  ...base,
                  reason: "language_switch" as const,
                  source_language: conflict.source_language || "",
                  current_language: conflict.current_language || "",
                };
              }
              return { ...base, reason: "conflict" as const };
            }),
          );
        }
      }
      if (conflicts.length > 0) {
        const allBuiltinUpgrades = conflicts.every(
          (conflict) => conflict.reason === "builtin_upgrade",
        );
        const allLanguageSwitch = conflicts.every(
          (conflict) => conflict.reason === "language_switch",
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
          : "以下目标中已存在该技能，确认后将直接覆盖：";
        const confirmed = await confirmOverwrite(
          title,
          <div style={{ display: "grid", gap: 8 }}>
            <div>{subtitle}</div>
            {conflicts.map((conflict) => (
              <div
                key={`${conflict.skill_name}-${conflict.workspace_id || ""}`}
              >
                <strong>{conflict.skill_name}</strong>
                {"  "}
                <span>{conflict.workspace_name}</span>
                {conflict.reason === "builtin_upgrade" ? (
                  <>
                    {"  "}
                    {"当前版本"}:{" "}
                    {conflict.current_version_text || "-"}
                    {"  ->  "}
                    {"源码版本"}:{" "}
                    {conflict.source_version_text || "-"}
                  </>
                ) : null}
                {conflict.reason === "language_switch" ? (
                  <>
                    {"  "}
                    {conflict.current_language === "zh"
                      ? "中文"
                      : "英文"}
                    {"  →  "}
                    {conflict.source_language === "zh"
                      ? "中文"
                      : "英文"}
                  </>
                ) : null}
              </div>
            ))}
          </div>,
        );
        if (!confirmed) return;
      }
      for (const skillName of configToAgentSkillNames) {
        const overwriteTargetIds = new Set(
          conflicts
            .filter((conflict) => conflict.skill_name === skillName)
            .map((conflict) => conflict.workspace_id)
            .filter((workspaceId): workspaceId is string =>
              Boolean(workspaceId),
            ),
        );
        const cleanTargetIds = targetWorkspaceIds.filter(
          (workspaceId) => !overwriteTargetIds.has(workspaceId),
        );

        if (cleanTargetIds.length > 0) {
          await api.downloadGlobalSkill({
            skill_name: skillName,
            targets: cleanTargetIds.map((workspace_id) => ({
              workspace_id,
            })),
          });
        }

        if (overwriteTargetIds.size > 0) {
          await api.downloadGlobalSkill({
            skill_name: skillName,
            targets: Array.from(overwriteTargetIds).map((workspace_id) => ({
              workspace_id,
            })),
            overwrite: true,
          });
        }
      }
      message.success("配置完成");
      closeModal();
      invalidateSkillCache({ global: true, workspaces: true });
      await loadData(true);
      for (const skillName of configToAgentSkillNames) {
        await checkScanWarnings(
          skillName,
          api.getBlockedHistory,
          api.getSkillScanner,
        );
      }
    } catch (error) {
      if (!handleScanError(error)) {
        message.error(
          error instanceof Error
            ? error.message
            : "配置失败",
        );
      }
    }
  };

  const handleImportBuiltins = async (
    selections: BuiltinImportSelection[],
    overwriteConflicts: boolean = false,
  ) => {
    if (selections.length === 0) return;
    try {
      setImportBuiltinLoading(true);
      const result = await api.importSelectedGlobalBuiltins({
        imports: selections,
        overwrite_conflicts: overwriteConflicts,
      });
      const imported = Array.isArray(result.imported) ? result.imported : [];
      const updated = Array.isArray(result.updated) ? result.updated : [];
      const unchanged = Array.isArray(result.unchanged) ? result.unchanged : [];

      if (!imported.length && !updated.length && unchanged.length) {
        message.info("没有可导入的内置变更");
        closeImportBuiltin();
        return;
      }

      if (imported.length || updated.length) {
        message.success(
          `已导入内置技能：${[...imported, ...updated].join(", ")}`,
        );
      }
      closeImportBuiltin();
      invalidateSkillCache({ global: true });
      await loadData(true);
    } catch (error) {
      const detail = parseErrorDetail(error);
      const conflicts = Array.isArray(detail?.conflicts)
        ? detail.conflicts
        : [];
      if (conflicts.length && !overwriteConflicts) {
        Modal.confirm({
          title: "检测到内置技能冲突",
          content: (
            <div style={{ display: "grid", gap: 8 }}>
              <div>{"以下内置技能与当前池中副本不同。确认后将使用源码版本覆盖。"}</div>
              {conflicts.map((item) => (
                <div key={`${item.skill_name}-${item.language || "en"}`}>
                  <strong>{item.skill_name}</strong>
                  {"  "}
                  {getBuiltinImportStatusLabel(item.status, item.language)}
                  {item.status !== "language_switch" ? (
                    <>
                      {"  "}
                      {"当前版本"}:{" "}
                      {item.current_version_text || "-"}
                      {"  ->  "}
                      {"源码版本"}:{" "}
                      {item.source_version_text || "-"}
                    </>
                  ) : null}
                </div>
              ))}
            </div>
          ),
          okText: "确认",
          cancelText: "取消",
          onOk: async () => {
            await handleImportBuiltins(selections, true);
          },
        });
        return;
      }
      message.error(
        error instanceof Error
          ? error.message
          : "导入内置技能失败",
      );
    } finally {
      setImportBuiltinLoading(false);
    }
  };

  const handleBuiltinLanguageSwitch = useCallback(
    async (skill: GlobalSkillSpec, language: string) => {
      const normalized = language === "zh" ? "zh" : "en";
      if (skill.builtin_language === normalized) return;
      const confirmed = await confirmOverwrite(
        "切换内置技能语言？",
        `确认用 ${normalized === "zh" ? "中文" : "英文"} 版本的内置技能覆盖池中的“${skill.name}”？`,
      );
      if (!confirmed) return;
      try {
        await api.updateGlobalBuiltin(skill.name, normalized);
        message.success(
          `已将“${skill.name}”切换为 ${normalized === "zh" ? "中文" : "英文"}`,
        );
        closeDrawer();
        invalidateSkillCache({ global: true });
        await loadData(true);
      } catch (error) {
        message.error(
          error instanceof Error
            ? error.message
            : "切换内置技能语言失败",
        );
      }
    },
    [closeDrawer, confirmOverwrite, loadData, message],
  );

  const handleToggleAutoUpdate = useCallback(
    async (
      skill: GlobalSkillSpec,
      enabled: boolean,
      targets: string[] | null = null,
    ) => {
      try {
        await api.updateGlobalSkillAutoUpdate(skill.name, { enabled, targets });
        message.success(
          enabled
            ? `已为 ${skill.name} 开启自动同步`
            : `已为 ${skill.name} 关闭自动同步`,
        );
        invalidateSkillCache({ global: true, workspaces: true });
        // Silent refresh: update data without toggling loading state
        const [globalSkillsData, workspaceSummaries, notice] = await Promise.all([
          api.listGlobalSkills(),
          api.listSkillWorkspaces(),
          api.getGlobalBuiltinNotice(),
        ]);
        setSkills(globalSkillsData);
        setWorkspaces(workspaceSummaries);
        setBuiltinNotice(notice);
      } catch (error) {
        message.error(
          error instanceof Error
            ? error.message
            : "更新自动同步设置失败",
        );
      }
    },
    [message],
  );

  const handleSaveGlobalSkill = async () => {
    const values = await form.validateFields().catch(() => null);
    if (!values) return;

    const trimmedConfig = configText.trim();
    let parsedConfig: Record<string, unknown> = {};
    if (trimmedConfig && trimmedConfig !== "{}") {
      try {
        parsedConfig = JSON.parse(trimmedConfig);
      } catch {
        message.error("JSON 格式无效");
        return;
      }
    }

    const skillName = (values.name || "").trim();
    const skillContent = drawerContent || values.content;

    if (!skillName || !skillContent.trim()) return;

    // A rename counts as an update: for auto-update skills it migrates every
    // agent that has it.
    // Non-auto-update skills leave agent copies untouched, so no confirm.
    if (
      mode === "edit" &&
      activeSkill &&
      skillName !== activeSkill.name &&
      activeSkill.auto_update
    ) {
      const oldName = activeSkill.name;
      const pinned =
        Array.isArray(activeSkill.auto_update_targets) &&
        activeSkill.auto_update_targets.length
          ? new Set(activeSkill.auto_update_targets)
          : null;
      const affected = workspaces.filter(
        (ws) =>
          (ws.skills || []).some((s) => s.name === oldName) &&
          (!pinned || pinned.has(ws.agent_id)),
      );
      if (affected.length > 0) {
        const confirmed = await confirmOverwrite(
          "同时在智能体中重命名？",
          <div style={{ display: "grid", gap: 8 }}>
            <div>
              {`“${oldName}”已安装在 ${affected.length} 个智能体中。重命名为“${skillName}”`}
            </div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {affected.map((ws) => (
                <li key={ws.agent_id}>
                  {getAgentDisplayName(
                    { id: ws.agent_id, name: ws.agent_name ?? "" },
                  )}
                </li>
              ))}
            </ul>
          </div>,
        );
        if (!confirmed) return;
      }
    }

    const persistGlobalSkill = async (overwrite = false) => {
      const result =
        mode === "edit"
          ? await api.saveGlobalSkill({
              name: skillName,
              content: skillContent,
              source_name: activeSkill?.name,
              config: parsedConfig,
              overwrite,
            })
          : await api
              .createGlobalSkill({
                name: skillName,
                content: skillContent,
                config: parsedConfig,
              })
              .then((created) => ({
                success: true,
                mode: "edit" as const,
                name: created.name,
              }));
      const finalName = result.name || skillName;
      const prevAutoEnabled =
        mode === "edit" ? Boolean(activeSkill?.auto_update) : false;
      const prevAutoTargets =
        (mode === "edit" ? activeSkill?.auto_update_targets : []) ?? [];
      const autoUpdateChanged =
        autoUpdateEnabled !== prevAutoEnabled ||
        JSON.stringify(autoUpdateTargets) !== JSON.stringify(prevAutoTargets);
      if (autoUpdateChanged) {
        await api.updateGlobalSkillAutoUpdate(finalName, {
          enabled: autoUpdateEnabled,
          targets:
            autoUpdateEnabled && autoUpdateTargets.length
              ? autoUpdateTargets
              : null,
        });
      }
      if (result.mode === "noop" && !autoUpdateChanged) {
        closeDrawer();
        return;
      }
      const savedAsNew =
        mode === "edit" && activeSkill && result.name !== activeSkill.name;
      message.success(
        savedAsNew
          ? `${"创建"}: ${result.name}`
          : mode === "edit"
          ? "保存"
          : "创建",
      );
      closeDrawer();
      invalidateSkillCache({ global: true });
      await loadData(true);
      await checkScanWarnings(
        result.name || skillName,
        api.getBlockedHistory,
        api.getSkillScanner,
      );
    };

    try {
      await persistGlobalSkill();
    } catch (error) {
      if (handleScanError(error)) return;
      const detail = parseErrorDetail(error);
      if (mode === "edit" && detail?.reason === "conflict") {
        const confirmed = await confirmOverwrite(
          "覆盖已存在的技能？",
          <div style={{ display: "grid", gap: 8 }}>
            <div>{"以下技能已存在，确认后将直接覆盖："}</div>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li>{skillName}</li>
            </ul>
          </div>,
        );
        if (!confirmed) return;
        try {
          await persistGlobalSkill(true);
        } catch (retryError) {
          message.error(
            retryError instanceof Error
              ? retryError.message
              : "保存" + " failed",
          );
        }
        return;
      }
      if (detail?.suggested_name) {
        const renameMap = await showConflictRenameModal([
          {
            key: skillName,
            label: skillName,
            suggested_name: String(detail.suggested_name),
          },
        ]);
        if (renameMap) {
          const newName = Object.values(renameMap)[0];
          if (newName) {
            form.setFieldsValue({ name: newName });
            await handleSaveGlobalSkill();
          }
        }
        return;
      }
      message.error(
        error instanceof Error ? error.message : "保存" + " failed",
      );
    }
  };

  const handleDelete = async (skill: GlobalSkillSpec) => {
    Modal.confirm({
      title: `删除 ${skill.name}？`,
      content: skill.external
        ? `将从磁盘删除外部技能文件:${skill.external_path || skill.name}。`
        : skill.source === "builtin"
        ? "这会将内置技能从全局技能中删除。之后仍可从源码重新导入。"
        : "此操作将从共享本地全局技能中移除该技能。",
      okText: "删除",
      okType: "danger",
      onOk: async () => {
        await api.deleteGlobalSkill(skill.name);
        message.success("已从全局技能删除");
        invalidateSkillCache({ global: true });
        await loadData(true);
      },
    });
  };

  const handleZipImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
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
      try {
        const result = await api.uploadGlobalSkillZip(file, {
          rename_map: renameMap,
        });
        if (result.count > 0) {
          message.success(
            `已导入：${result.imported.join(", ")}`,
          );
        } else {
          message.info("无新技能导入");
        }
        invalidateSkillCache({ global: true });
        await loadData(true);
        if (result.count > 0 && Array.isArray(result.imported)) {
          for (const name of result.imported) {
            await checkScanWarnings(
              name,
              api.getBlockedHistory,
              api.getSkillScanner,
            );
          }
        }
        break;
      } catch (error) {
        const detail = parseErrorDetail(error);
        const conflicts = Array.isArray(detail?.conflicts)
          ? detail.conflicts
          : [];
        if (conflicts.length === 0) {
          if (handleScanError(error)) break;
          message.error(
            error instanceof Error
              ? error.message
              : "ZIP 导入失败",
          );
          break;
        }
        const newRenames = await showConflictRenameModal(
          conflicts.map(
            (c: { skill_name?: string; suggested_name?: string }) => ({
              key: c.skill_name || "",
              label: c.skill_name || "",
              suggested_name: c.suggested_name || "",
            }),
          ),
        );
        if (!newRenames) break;
        renameMap = { ...renameMap, ...newRenames };
      }
    }
  };

  const handleConfirmImport = async (url: string, targetName?: string) => {
    try {
      setImporting(true);
      const result = await api.importGlobalSkillFromHub({
        bundle_url: url,
        target_name: targetName,
      });
      message.success(`${"创建"}: ${result.name}`);
      closeImportModal();
      invalidateSkillCache({ global: true });
      await loadData(true);
      await checkScanWarnings(
        result.name,
        api.getBlockedHistory,
        api.getSkillScanner,
      );
    } catch (error) {
      if (handleScanError(error)) return;
      const detail = parseErrorDetail(error);
      if (detail?.suggested_name) {
        const skillName = String(detail?.skill_name || "");
        const renameMap = await showConflictRenameModal([
          {
            key: skillName,
            label: skillName,
            suggested_name: String(detail.suggested_name),
          },
        ]);
        if (renameMap) {
          const newName = Object.values(renameMap)[0];
          if (newName) {
            await handleConfirmImport(url, newName);
          }
        }
        return;
      }
      message.error(
        error instanceof Error ? error.message : "技能上传失败",
      );
    } finally {
      setImporting(false);
    }
  };

  const handleBatchDeleteGlobal = async () => {
    const names = Array.from(selectedGlobalSkills);
    if (names.length === 0) return;
    const hasExternal = skills.some(
      (s) => selectedGlobalSkills.has(s.name) && s.external,
    );
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: `删除 ${names.length} 个池技能？`,
        content: (
          <>
            <ul style={{ margin: "8px 0", paddingLeft: 20 }}>
              {names.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
            {hasExternal && (
              <div style={{ color: "var(--ant-color-error, #ff4d4f)" }}>
                {"所选的外部技能将从磁盘永久删除。"}
              </div>
            )}
          </>
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
      const { results } = await api.batchDeleteGlobalSkills(names);
      const failed = Object.entries(results).filter(([, r]) => !r.success);
      if (failed.length > 0) {
        message.warning(
          `${names.length - failed.length} 个已删除，${failed.length} 个失败`,
        );
      } else {
        message.success(
          `已删除 ${names.length} 个池技能`,
        );
      }
      clearGlobalSelection();
      invalidateSkillCache({ global: true });
      await loadData(true);
    } catch (error) {
      message.error(
        error instanceof Error
          ? error.message
          : "批量删除失败",
      );
    }
  };

  return {
    loading,
    skills,
    sortedSkills,
    workspaces,
    mode,
    activeSkill,
    configToAgentInitialNames,
    configText,
    zipInputRef,
    importBuiltinModalOpen,
    builtinSources,
    builtinLanguage,
    builtinNotice,
    builtinNoticeTotal,
    hasUnseenBuiltinNotice,
    importBuiltinLoading,
    importModalOpen,
    importing,
    selectedGlobalSkills,
    batchModeEnabled,
    viewMode,
    filterOpen,
    searchQuery,
    setSearchQuery,
    form,
    drawerContent,
    showMarkdown,
    conflictRenameModal,
    setImportModalOpen,
    setConfigText,
    autoUpdateEnabled,
    autoUpdateTargets,
    setAutoUpdateEnabled,
    setAutoUpdateTargets,
    setShowMarkdown,
    setFilterOpen,
    setViewMode,
    handleRefresh,
    closeModal,
    openCreate,
    openConfigToAgent,
    openImportBuiltin,
    closeImportBuiltin,
    closeImportModal,
    openEdit,
    closeDrawer,
    handleDrawerContentChange,
    validateFrontmatter,
    handleConfigToAgent,
    handleImportBuiltins,
    handleBuiltinLanguageSwitch,
    handleToggleAutoUpdate,
    handleSaveGlobalSkill,
    handleDelete,
    handleZipImport,
    handleConfirmImport,
    handleBatchDeleteGlobal,
    toggleGlobalSelect,
    toggleBatchMode,
    selectAllGlobal,
    clearGlobalSelection,
  };
}
