import { useState, useEffect, useCallback, useRef } from "react";
import { Form, Modal } from "@agentscope-ai/design";
import api from "../../../api";
import type { AgentsRunningConfig } from "../../../api/types";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { useAgentStore } from "../../../stores/agentStore";
import {
  CONTEXT_MANAGER_BACKEND_MAPPINGS,
} from "../../../constants/backendMappings";
import type { ToolExecutionLevel } from "./components/ToolExecutionLevelCard";

export function useAgentConfig() {
    const { message } = useAppMessage();
  const { selectedAgent } = useAgentStore();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [language, setLanguage] = useState<string>("zh");
  const [savingLang, setSavingLang] = useState(false);
  const [timezone, setTimezone] = useState<string>("UTC");
  const [savingTimezone, setSavingTimezone] = useState(false);
  const [approvalLevel, setApprovalLevel] =
    useState<ToolExecutionLevel>("AUTO");
  const originalConfigRef = useRef<AgentsRunningConfig | null>(null);

  const fetchConfig = useCallback(async () => {
    // The request layer reads the selected agent from the shared store.
    void selectedAgent;
    setLoading(true);
    setError(null);
    try {
      const [config, langResp, tzResp] = await Promise.all([
        api.getAgentRunningConfig(),
        api.getAgentLanguage(),
        api.getUserTimezone(),
      ]);
      const loadedLevel = (
        config.approval_level || "AUTO"
      ).toUpperCase() as ToolExecutionLevel;
      setApprovalLevel(loadedLevel);
      const contextBackend =
        config.context_manager_backend in CONTEXT_MANAGER_BACKEND_MAPPINGS
          ? config.context_manager_backend
          : "light";
      form.setFieldsValue({
        shell_command_timeout: config.shell_command_timeout ?? 60.0,
        shell_command_executable: config.shell_command_executable ?? "",
        loop: {
          ...config.loop,
          iteration: {
            ...config.loop?.iteration,
            max_iterations:
              config.loop?.iteration?.max_iterations ?? config.max_iters ?? 100,
          },
        },
        llm_retry_enabled: config.llm_retry_enabled,
        llm_max_retries: config.llm_max_retries,
        llm_backoff_base: config.llm_backoff_base,
        llm_backoff_cap: config.llm_backoff_cap,
        llm_max_concurrent: config.llm_max_concurrent,
        llm_max_qpm: config.llm_max_qpm,
        llm_rate_limit_pause: config.llm_rate_limit_pause,
        llm_rate_limit_jitter: config.llm_rate_limit_jitter,
        llm_acquire_timeout: config.llm_acquire_timeout,
        history_max_length: config.history_max_length,
        context_manager_backend: contextBackend,
        light_context_config: config.light_context_config,
        auto_title_config: config.auto_title_config ?? {
          enabled: true,
          timeout_seconds: 30.0,
        },
      });

      // Store original config for complete save
      originalConfigRef.current = config;

      setLanguage(langResp.language);
      setTimezone(tzResp.timezone || "UTC");
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : "配置加载失败";
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  }, [form, selectedAgent]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      // Deep-merge nested config objects so that collapsed (unrendered)
      // Collapse panels don't lose their saved values.  Shallow spread
      // would overwrite the entire nested object with only the rendered
      // fields, dropping anything inside a collapsed panel.
      const original = originalConfigRef.current!;
      const formValues = values as AgentsRunningConfig;

      const isPlainObject = (
        value: unknown,
      ): value is Record<string, unknown> =>
        value !== null && typeof value === "object" && !Array.isArray(value);

      const deepMergeConfig = <T,>(
        base: T | undefined | null,
        override: T | undefined | null,
      ): T | undefined => {
        if (!isPlainObject(base)) return override ?? base ?? undefined;
        if (!isPlainObject(override)) return override ?? base;
        const result: Record<string, unknown> = { ...base };
        for (const [key, overrideVal] of Object.entries(override)) {
          const baseVal = result[key];
          if (isPlainObject(overrideVal) && isPlainObject(baseVal)) {
            result[key] = deepMergeConfig(baseVal, overrideVal);
          } else {
            result[key] = overrideVal;
          }
        }
        return result as T;
      };

      const configToSave: AgentsRunningConfig = {
        ...original,
        ...formValues,
        // Deep-merge nested config sections to preserve collapsed fields
        light_context_config: deepMergeConfig(
          original.light_context_config,
          formValues.light_context_config,
        ) as typeof original.light_context_config,
        auto_title_config: deepMergeConfig(
          original.auto_title_config,
          formValues.auto_title_config,
        ) as typeof original.auto_title_config,
        approval_level: approvalLevel,
      };

      await api.updateAgentRunningConfig(configToSave);

      // Update original config after successful save
      originalConfigRef.current = configToSave;
      message.success("配置保存成功");
    } catch (err) {
      if (err instanceof Error && "errorFields" in err) return;
      const errMsg =
        err instanceof Error ? err.message : "配置保存失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  }, [approvalLevel, form, message]);

  const handleLanguageChange = useCallback(
    (value: string): void => {
      if (value === language) return;
      Modal.confirm({
        title: "切换智能体语言",
        content: (
          <span style={{ whiteSpace: "pre-line" }}>
            {"切换语言将会覆盖以下文件为新语言的默认版本：\n\n  SOUL.md、AGENTS.md、PROFILE.md、BOOTSTRAP.md、HEARTBEAT.md\n\n如果您已对这些文件进行过自定义修改，请提前备份。您自行添加的其他文件不受影响。"}
          </span>
        ),
        okText: "切换语言",
        cancelText: "取消",
        onOk: async () => {
          setSavingLang(true);
          try {
            const resp = await api.updateAgentLanguage(value);
            setLanguage(resp.language);
            if (resp.copied_files && resp.copied_files.length > 0) {
              message.success(
                `语言已更新，已复制 ${resp.copied_files.length} 个 MD 文件`,
              );
            } else {
              message.success("语言更新成功");
            }
          } catch (err) {
            const errMsg =
              err instanceof Error
                ? err.message
                : "语言更新失败";
            message.error(errMsg);
          } finally {
            setSavingLang(false);
          }
        },
      });
    },
    [language, message],
  );

  const handleTimezoneChange = useCallback(
    async (value: string) => {
      if (value === timezone) return;
      setSavingTimezone(true);
      try {
        await api.updateUserTimezone(value);
        setTimezone(value);
        message.success("时区更新成功");
      } catch (err) {
        const errMsg =
          err instanceof Error
            ? err.message
            : "时区更新失败";
        message.error(errMsg);
      } finally {
        setSavingTimezone(false);
      }
    },
    [message, timezone],
  );

  return {
    form,
    loading,
    saving,
    error,
    language,
    savingLang,
    timezone,
    savingTimezone,
    approvalLevel,
    setApprovalLevel,
    fetchConfig,
    handleSave,
    handleLanguageChange,
    handleTimezoneChange,
  };
}
