import { useCallback, useEffect, useState } from "react";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import type { MCPAccessPolicy, MCPClientInfo } from "../../../api/types";
import { useAgentStore } from "../../../stores/agentStore";

export function useMCP() {
    const { selectedAgent } = useAgentStore();
  const [clients, setClients] = useState<MCPClientInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const { message } = useAppMessage();

  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listMCPClients();
      setClients(data);
    } catch (error) {
      console.error("Failed to load MCP clients:", error);
      message.error("加载 MCP 客户端失败");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    loadClients();
  }, [loadClients, selectedAgent]);

  const createClient = useCallback(
    async (
      key: string,
      clientData: {
        name: string;
        description?: string;
        command: string;
        enabled?: boolean;
        transport?: "stdio" | "streamable_http" | "sse";
        url?: string;
        headers?: Record<string, string>;
        args?: string[];
        env?: Record<string, string>;
        cwd?: string;
      },
    ) => {
      try {
        await api.createMCPClient({
          client_key: key,
          client: clientData,
        });
        message.success("MCP 客户端创建成功");
        await loadClients();
        return true;
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : "MCP 客户端创建失败";
        message.error(errorMsg);
        return false;
      }
    },
    [message, loadClients],
  );

  const updateClient = useCallback(
    async (
      key: string,
      updates: {
        name?: string;
        description?: string;
        command?: string;
        enabled?: boolean;
        transport?: "stdio" | "streamable_http" | "sse";
        url?: string;
        headers?: Record<string, string>;
        args?: string[];
        env?: Record<string, string>;
        cwd?: string;
      },
    ) => {
      try {
        await api.updateMCPClient(key, updates);
        message.success("MCP 客户端更新成功");
        await loadClients();
        return true;
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : "MCP 客户端更新失败";
        message.error(errorMsg);
        return false;
      }
    },
    [message, loadClients],
  );

  const toggleEnabled = useCallback(
    async (client: MCPClientInfo) => {
      try {
        await api.toggleMCPClient(client.key);
        message.success(
          client.enabled ? "MCP 客户端禁用成功" : "MCP 客户端启用成功",
        );
        await loadClients();
      } catch {
        message.error("切换 MCP 客户端状态失败");
      }
    },
    [message, loadClients],
  );

  const deleteClient = useCallback(
    async (client: MCPClientInfo) => {
      try {
        await api.deleteMCPClient(client.key);
        message.success("MCP 客户端删除成功");
        await loadClients();
      } catch {
        message.error("MCP 客户端删除失败");
      }
    },
    [message, loadClients],
  );

  const updatePolicy = useCallback(
    async (clientKey: string, policy: MCPAccessPolicy) => {
      try {
        await api.updateMCPPolicy(clientKey, policy);
        message.success("MCP 访问策略已保存");
        await loadClients();
        return true;
      } catch (error) {
        const errorMsg =
          error instanceof Error ? error.message : "保存 MCP 访问策略失败";
        message.error(errorMsg);
        return false;
      }
    },
    [message, loadClients],
  );

  return {
    clients,
    loading,
    createClient,
    updateClient,
    updatePolicy,
    toggleEnabled,
    deleteClient,
    refreshClients: loadClients,
  };
}
