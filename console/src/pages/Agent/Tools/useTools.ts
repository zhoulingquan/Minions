import { useCallback, useEffect, useState } from "react";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import type { ToolInfo } from "../../../api/modules/tools";
import { customToolsApi } from "../../../api/modules/customTools";
import { useAgentStore } from "../../../stores/agentStore";

export function useTools() {
  const { selectedAgent } = useAgentStore();
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [customToolNames, setCustomToolNames] = useState<string[]>([]);
  const { message } = useAppMessage();

  const loadTools = useCallback(async () => {
    setLoading(true);
    try {
      const [toolsResult, customFilesResult] = await Promise.allSettled([
        api.listTools(),
        customToolsApi.list(),
      ]);
      if (toolsResult.status === "rejected") {
        throw toolsResult.reason;
      }
      setTools(toolsResult.value);
      if (customFilesResult.status === "fulfilled") {
        setCustomToolNames(customFilesResult.value.map((file) => file.name));
      } else {
        console.error(
          "Failed to load custom tools:",
          customFilesResult.reason,
        );
      }
    } catch (error) {
      console.error("Failed to load tools:", error);
      message.error("加载工具失败");
    } finally {
      setLoading(false);
    }
  }, [message]);

  const loadCustomTools = useCallback(async () => {
    try {
      const files = await customToolsApi.list();
      setCustomToolNames(files.map((f) => f.name));
    } catch (error) {
      console.error("Failed to load custom tools:", error);
    }
  }, []);

  useEffect(() => {
    loadTools();
  }, [loadTools, selectedAgent]);

  const toggleEnabled = useCallback(
    async (tool: ToolInfo) => {
      // Optimistic update
      setTools((prev) =>
        prev.map((t) =>
          t.name === tool.name ? { ...t, enabled: !t.enabled } : t,
        ),
      );

      try {
        const result = await api.toggleTool(tool.name);
        message.success(
          tool.enabled ? "工具禁用成功" : "工具启用成功",
        );
        // Merge rather than replace to preserve any local state not returned
        // by the server (e.g. UI-only fields added in future expansions).
        setTools((prev) =>
          prev.map((t) => (t.name === result.name ? { ...t, ...result } : t)),
        );
      } catch {
        // Revert optimistic update on error
        setTools((prev) =>
          prev.map((t) =>
            t.name === tool.name ? { ...t, enabled: tool.enabled } : t,
          ),
        );
        message.error("切换工具状态失败");
      }
    },
    [message],
  );

  const toggleAsyncExecution = useCallback(
    async (tool: ToolInfo) => {
      // Optimistic update
      setTools((prev) =>
        prev.map((t) =>
          t.name === tool.name
            ? { ...t, async_execution: !t.async_execution }
            : t,
        ),
      );

      try {
        const result = await api.updateAsyncExecution(
          tool.name,
          !tool.async_execution,
        );
        message.success(
          result.async_execution
            ? "异步执行已启用"
            : "异步执行已禁用",
        );
        // Merge server response to preserve static metadata.
        setTools((prev) =>
          prev.map((t) => (t.name === result.name ? { ...t, ...result } : t)),
        );
      } catch {
        // Revert optimistic update on error
        setTools((prev) =>
          prev.map((t) =>
            t.name === tool.name
              ? { ...t, async_execution: tool.async_execution }
              : t,
          ),
        );
        message.error("切换工具状态失败");
      }
    },
    [message],
  );

  const enableAll = useCallback(async () => {
    const disabledTools = tools.filter((tool) => !tool.enabled);
    if (disabledTools.length === 0) {
      message.info("所有工具已处于启用状态");
      return;
    }

    // Optimistic update - preserve async_execution state
    setTools((prev) => prev.map((t) => ({ ...t, enabled: true })));

    setBatchLoading(true);
    try {
      const results = await Promise.all(
        disabledTools.map((tool) => api.toggleTool(tool.name)),
      );
      message.success("全部工具已启用");
      // Merge server responses, preserving all static metadata.
      setTools((prev) =>
        prev.map((t) => {
          const result = results.find((r) => r.name === t.name);
          return result ? { ...t, ...result } : t;
        }),
      );
    } catch {
      message.error("切换工具状态失败");
      // Reload on error to sync with server
      await loadTools();
    } finally {
      setBatchLoading(false);
    }
  }, [tools, loadTools, message]);

  const disableAll = useCallback(async () => {
    const enabledTools = tools.filter((tool) => tool.enabled);
    if (enabledTools.length === 0) {
      message.info("所有工具已处于禁用状态");
      return;
    }

    // Optimistic update - preserve async_execution state
    setTools((prev) => prev.map((t) => ({ ...t, enabled: false })));

    setBatchLoading(true);
    try {
      const results = await Promise.all(
        enabledTools.map((tool) => api.toggleTool(tool.name)),
      );
      message.success("全部工具已禁用");
      // Merge server responses, preserving all static metadata.
      setTools((prev) =>
        prev.map((t) => {
          const result = results.find((r) => r.name === t.name);
          return result ? { ...t, ...result } : t;
        }),
      );
    } catch {
      message.error("切换工具状态失败");
      // Reload on error to sync with server
      await loadTools();
    } finally {
      setBatchLoading(false);
    }
  }, [tools, loadTools, message]);

  const saveToolConfig = useCallback(
    async (toolName: string, config: Record<string, unknown>) => {
      try {
        await api.updateToolConfig(toolName, config);
        message.success("配置已保存");
      } catch (error) {
        console.error("Failed to save tool config:", error);
        message.error("配置保存失败");
        throw error;
      }
    },
    [message],
  );

  const createCustomTool = useCallback(
    async (name: string, content: string) => {
      try {
        await customToolsApi.create(name, content);
        message.success("工具创建成功");
        await loadCustomTools();
        await loadTools();
      } catch (error) {
        console.error("Failed to create custom tool:", error);
        message.error("工具创建失败");
        throw error;
      }
    },
    [loadCustomTools, loadTools, message],
  );

  const getCustomTool = useCallback(async (name: string) => {
    return customToolsApi.get(name);
  }, []);

  const updateCustomTool = useCallback(
    async (name: string, content: string) => {
      try {
        await customToolsApi.update(name, content);
        message.success("工具更新成功");
      } catch (error) {
        console.error("Failed to update custom tool:", error);
        message.error("工具更新失败");
        throw error;
      }
    },
    [message],
  );

  const deleteCustomTool = useCallback(
    async (name: string) => {
      try {
        await customToolsApi.delete(name);
        message.success("工具删除成功");
        await loadCustomTools();
        await loadTools();
      } catch (error) {
        console.error("Failed to delete custom tool:", error);
        message.error("工具删除失败");
        throw error;
      }
    },
    [loadCustomTools, loadTools, message],
  );

  const reloadCustomTool = useCallback(
    async (name: string) => {
      try {
        await customToolsApi.reload(name);
        message.success("工具已重新加载");
      } catch (error) {
        console.error("Failed to reload custom tool:", error);
        message.error("工具重新加载失败");
        throw error;
      }
    },
    [message],
  );

  return {
    tools,
    loading,
    batchLoading,
    customToolNames,
    toggleEnabled,
    toggleAsyncExecution,
    enableAll,
    disableAll,
    loadTools,
    saveToolConfig,
    createCustomTool,
    getCustomTool,
    updateCustomTool,
    deleteCustomTool,
    reloadCustomTool,
  };
}
