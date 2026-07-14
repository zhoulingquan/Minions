import { useState, useEffect, useCallback, useRef } from "react";
import { Modal } from "@agentscope-ai/design";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import type { SecurityScanErrorResponse } from "../../../api/modules/security";
import { invalidateSkillCache } from "../../../api/modules/skill";
import type { SkillSpec } from "../../../api/types";
import { useAgentStore } from "../../../stores/agentStore";
import { parseErrorDetail } from "../../../utils/error";
import {
  handleScanError,
  checkScanWarnings as checkScanWarningsShared,
  showScanErrorModal,
} from "../../../utils/scanError";

type SkillConflict = {
  skill_name?: string;
  suggested_name?: string;
  conflicts?: Array<{
    skill_name?: string;
    suggested_name?: string;
    [key: string]: unknown;
  }>;
  [key: string]: unknown;
};

type SkillActionResult =
  | { success: true; name?: string; imported?: string[] }
  | { success: false; conflict?: SkillConflict };

export function useSkills() {
    const { selectedAgent } = useAgentStore();
  const [skills, setSkills] = useState<SkillSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [importing, setImporting] = useState(false);
  const importTaskIdRef = useRef<string | null>(null);
  const importCancelReasonRef = useRef<"manual" | "timeout" | null>(null);
  const { message } = useAppMessage();

  const handleError = useCallback(
    (error: unknown, defaultMsg: string): boolean => {
      if (handleScanError(error)) return true;
      const msg =
        error instanceof Error && error.message ? error.message : defaultMsg;
      console.error(defaultMsg, error);
      message.error(msg);
      return false;
    },
    [message],
  );

  const checkScanWarnings = useCallback(
    (skillName: string) =>
      checkScanWarningsShared(
        skillName,
        api.getBlockedHistory,
        api.getSkillScanner,
      ),
    [],
  );

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listSkills(selectedAgent);
      setSkills(data || []);
    } catch (error) {
      console.error("加载技能失败", error);
      message.error("加载技能失败");
    } finally {
      setLoading(false);
    }
  }, [message, selectedAgent]);

  const hardRefresh = useCallback(async () => {
    setLoading(true);
    try {
      invalidateSkillCache({ agentId: selectedAgent });
      const data = await api.refreshSkills(selectedAgent);
      setSkills(data || []);
    } catch (error) {
      console.error("刷新技能失败", error);
      message.error("刷新技能失败");
    } finally {
      setLoading(false);
    }
  }, [message, selectedAgent]);

  // Invalidate cache when agent changes
  useEffect(() => {
    invalidateSkillCache({ agentId: selectedAgent });
    void fetchSkills();
  }, [selectedAgent, fetchSkills]);

  const createSkill = async (
    name: string,
    content: string,
    config?: Record<string, unknown>,
    enable?: boolean,
  ): Promise<SkillActionResult> => {
    try {
      const result = await api.createSkill(name, content, config, enable);
      message.success("创建成功");
      invalidateSkillCache({ agentId: selectedAgent }); // Clear cache after mutation
      await fetchSkills();
      await checkScanWarnings(result.name);
      return { success: true, name: result.name };
    } catch (error) {
      const detail = parseErrorDetail(error);
      if (detail?.suggested_name) {
        return { success: false, conflict: detail as SkillConflict };
      }
      handleError(error, "保存失败");
      return { success: false };
    }
  };

  const uploadSkill = async (
    file: File,
    targetName?: string,
    renameMap?: Record<string, string>,
  ): Promise<SkillActionResult> => {
    try {
      setUploading(true);
      const result = await api.uploadSkill(file, {
        enable: true,
        target_name: targetName,
        rename_map: renameMap,
      });
      if (result?.count > 0) {
        message.success(
          "技能上传成功" + `: ${result.imported.join(", ")}`,
        );
        invalidateSkillCache({ agentId: selectedAgent }); // Clear cache after mutation
        await fetchSkills();
        for (const name of result.imported) {
          await checkScanWarnings(name);
        }
      }
      if (!result?.count) {
        message.warning("没有导入新技能，可能已存在相同技能");
      }
      await fetchSkills();
      return { success: true, imported: result?.imported || [] };
    } catch (error) {
      const detail = parseErrorDetail(error);
      if (Array.isArray(detail?.conflicts) && detail.conflicts.length > 0) {
        return { success: false, conflict: detail as SkillConflict };
      }
      handleError(error, "技能上传失败");
      return { success: false };
    } finally {
      setUploading(false);
    }
  };

  const importFromHub = async (
    input: string,
    targetName?: string,
  ): Promise<SkillActionResult> => {
    const text = (input || "").trim();
    if (!text) {
      message.warning("请提供技能库 URL");
      return { success: false };
    }
    if (!text.startsWith("http://") && !text.startsWith("https://")) {
      message.warning("请输入以 http:// 或 https:// 开头的有效 URL");
      return { success: false };
    }
    const timeoutMs = 90_000;
    const pollMs = 1_000;
    const startedAt = Date.now();
    try {
      setImporting(true);
      importCancelReasonRef.current = null;
      const payload = {
        bundle_url: text,
        enable: true,
        target_name: targetName,
      };
      const task = await api.startHubSkillInstall(payload);
      importTaskIdRef.current = task.task_id;

      while (importTaskIdRef.current) {
        const status = await api.getHubSkillInstallStatus(task.task_id);

        if (status.status === "completed" && status.result?.installed) {
          message.success(
            `已导入技能：${status.result.name}`,
          );
          invalidateSkillCache({ agentId: selectedAgent }); // Clear cache after mutation
          await fetchSkills();
          if (status.result.name) {
            await checkScanWarnings(status.result.name);
          }
          return { success: true, name: String(status.result.name || "") };
        }

        if (status.status === "failed") {
          if (
            Array.isArray(status.result?.conflicts) &&
            status.result.conflicts.length > 0
          ) {
            return { success: false, conflict: status.result };
          }
          const hubResult = status.result as
            | SecurityScanErrorResponse
            | null
            | undefined;
          if (hubResult?.type === "security_scan_failed") {
            showScanErrorModal(hubResult);
            return { success: false };
          }
          throw new Error(status.error || "导入失败");
        }

        if (status.status === "cancelled") {
          message.warning(
            importCancelReasonRef.current === "timeout"
              ? "技能导入超时"
              : "技能导入已取消",
          );
          return { success: false };
        }

        if (Date.now() - startedAt >= timeoutMs) {
          importCancelReasonRef.current = "timeout";
          await api.cancelHubSkillInstall(task.task_id);
        }

        await new Promise((resolve) => window.setTimeout(resolve, pollMs));
      }

      return { success: false };
    } catch (error) {
      handleError(error, "导入失败");
      return { success: false };
    } finally {
      importTaskIdRef.current = null;
      importCancelReasonRef.current = null;
      setImporting(false);
    }
  };

  const cancelImport = useCallback(() => {
    if (!importing) return;
    importCancelReasonRef.current = "manual";
    const taskId = importTaskIdRef.current;
    if (!taskId) return;
    void api.cancelHubSkillInstall(taskId);
  }, [importing]);

  const toggleEnabled = async (skill: SkillSpec) => {
    try {
      if (skill.enabled) {
        await api.disableSkill(skill.name);
        setSkills((prev) =>
          prev.map((s) =>
            s.name === skill.name ? { ...s, enabled: false } : s,
          ),
        );
        message.success("已禁用");
      } else {
        await api.enableSkill(skill.name);
        setSkills((prev) =>
          prev.map((s) =>
            s.name === skill.name ? { ...s, enabled: true } : s,
          ),
        );
        message.success("已启用");
        await checkScanWarnings(skill.name);
      }
      invalidateSkillCache({ agentId: selectedAgent }); // Clear cache after mutation
      return true;
    } catch (error) {
      handleError(error, "操作失败");
      return false;
    }
  };

  const deleteSkill = async (skill: SkillSpec) => {
    const confirmed = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: "确认",
        content: "确定要删除此技能吗？",
        okText: "删除",
        okType: "danger",
        cancelText: "取消",
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      });
    });

    if (!confirmed) return false;

    try {
      const result = await api.deleteSkill(skill.name);
      if (result.deleted) {
        message.success("技能删除成功");
        invalidateSkillCache({ agentId: selectedAgent }); // Clear cache after mutation
        await fetchSkills();
        return true;
      }
    } catch (error) {
      console.error("技能删除失败", error);
      message.error("技能删除失败");
    }
    return false;
  };

  return {
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
    refreshSkills: fetchSkills,
    hardRefresh,
  };
}
