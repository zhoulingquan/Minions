import { useCallback, useState, useEffect } from "react";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { agentsApi } from "@/api/modules/agents";
import type { AgentSummary } from "@/api/types/agents";
import { useAgentStore } from "@/stores/agentStore";

interface UseAgentsReturn {
  agents: AgentSummary[];
  loading: boolean;
  error: Error | null;
  loadAgents: () => Promise<void>;
  deleteAgent: (agentId: string) => Promise<void>;
  toggleAgent: (agentId: string, enabled: boolean) => Promise<void>;
  setAgents: (agents: AgentSummary[]) => void;
}

export function useAgents(): UseAgentsReturn {
    const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const { setAgents: updateStoreAgents } = useAgentStore();
  const { message } = useAppMessage();

  const setAgentsState = useCallback(
    (nextAgents: AgentSummary[]) => {
      setAgents(nextAgents);
      updateStoreAgents(nextAgents);
    },
    [updateStoreAgents],
  );

  const loadAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await agentsApi.listAgents();
      setAgentsState(data.agents);
    } catch (err) {
      console.error("Failed to load agents:", err);
      const errorMsg =
        err instanceof Error ? err : new Error("加载智能体列表失败");
      setError(errorMsg);
      message.error("加载智能体列表失败");
    } finally {
      setLoading(false);
    }
  }, [message, setAgentsState]);

  const deleteAgent = async (agentId: string) => {
    try {
      await agentsApi.deleteAgent(agentId);
      message.success("智能体删除成功");
      await loadAgents();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "智能体删除失败");
      throw err;
    }
  };

  const toggleAgent = async (agentId: string, enabled: boolean) => {
    try {
      await agentsApi.toggleAgentEnabled(agentId, enabled);
      const successMsg = enabled
        ? "智能体已启用"
        : "智能体已禁用";
      message.success(successMsg);
      await loadAgents();
    } catch (err) {
      message.error(
        err instanceof Error ? err.message : "切换智能体状态失败",
      );
      throw err;
    }
  };

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  return {
    agents,
    loading,
    error,
    loadAgents,
    deleteAgent,
    toggleAgent,
    setAgents: setAgentsState,
  };
}
