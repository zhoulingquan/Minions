import { useCallback, useEffect, useState } from "react";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import type { ToolInfo } from "../../../api/modules/tools";
import { customToolsApi } from "../../../api/modules/customTools";
import { useTranslation } from "react-i18next";
import { useAgentStore } from "../../../stores/agentStore";

/** Hook for managing custom tools on the dedicated CustomTools page. */
export function useCustomTools() {
  const { t } = useTranslation();
  const { selectedAgent } = useAgentStore();
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [customToolNames, setCustomToolNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const { message } = useAppMessage();

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [allTools, customFiles] = await Promise.all([
        api.listTools(),
        customToolsApi.list(),
      ]);
      const names = customFiles.map((f) => f.name);
      setCustomToolNames(names);
      // Only show tools that are custom
      setTools(allTools.filter((tool) => names.includes(tool.name)));
    } catch (error) {
      console.error("Failed to load custom tools:", error);
      message.error(t("tools.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t, message]);

  useEffect(() => {
    loadAll();
  }, [loadAll, selectedAgent]);

  const toggleEnabled = useCallback(
    async (tool: ToolInfo) => {
      setTools((prev) =>
        prev.map((t) =>
          t.name === tool.name ? { ...t, enabled: !t.enabled } : t,
        ),
      );
      try {
        const result = await api.toggleTool(tool.name);
        message.success(
          tool.enabled ? t("tools.disableSuccess") : t("tools.enableSuccess"),
        );
        setTools((prev) =>
          prev.map((t) => (t.name === result.name ? { ...t, ...result } : t)),
        );
      } catch (error) {
        setTools((prev) =>
          prev.map((t) =>
            t.name === tool.name ? { ...t, enabled: tool.enabled } : t,
          ),
        );
        message.error(t("tools.toggleError"));
      }
    },
    [t, message],
  );

  const createCustomTool = useCallback(
    async (name: string, content: string) => {
      try {
        await customToolsApi.create(name, content);
        message.success(t("tools.createSuccess"));
        await loadAll();
      } catch (error) {
        console.error("Failed to create custom tool:", error);
        message.error(t("tools.createFailed"));
        throw error;
      }
    },
    [t, message, loadAll],
  );

  const getCustomTool = useCallback(async (name: string) => {
    return customToolsApi.get(name);
  }, []);

  const updateCustomTool = useCallback(
    async (name: string, content: string) => {
      try {
        await customToolsApi.update(name, content);
        message.success(t("tools.updateSuccess"));
      } catch (error) {
        console.error("Failed to update custom tool:", error);
        message.error(t("tools.createFailed"));
        throw error;
      }
    },
    [t, message],
  );

  const deleteCustomTool = useCallback(
    async (name: string) => {
      try {
        await customToolsApi.delete(name);
        message.success(t("tools.deleteSuccess"));
        await loadAll();
      } catch (error) {
        console.error("Failed to delete custom tool:", error);
        message.error(t("tools.createFailed"));
        throw error;
      }
    },
    [t, message, loadAll],
  );

  const reloadCustomTool = useCallback(
    async (name: string) => {
      try {
        await customToolsApi.reload(name);
        message.success(t("tools.reloadSuccess"));
      } catch (error) {
        console.error("Failed to reload custom tool:", error);
        message.error(t("tools.createFailed"));
        throw error;
      }
    },
    [t, message],
  );

  return {
    tools,
    loading,
    customToolNames,
    loadAll,
    toggleEnabled,
    createCustomTool,
    getCustomTool,
    updateCustomTool,
    deleteCustomTool,
    reloadCustomTool,
  };
}
