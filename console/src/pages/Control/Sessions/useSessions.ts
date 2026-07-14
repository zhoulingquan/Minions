import { useState, useEffect } from "react";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import type { ChatUpdateRequest } from "../../../api/types";
import type { Session } from "./components/constants";
import { useAgentStore } from "../../../stores/agentStore";

export function useSessions() {
    const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const { selectedAgent } = useAgentStore();
  const { message } = useAppMessage();

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await api.listSessions();
      if (data) {
        setSessions(data as Session[]);
      }
    } catch (error) {
      console.error("❌ Failed to load sessions:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    const loadSessions = async () => {
      await fetchSessions();
    };

    if (mounted) {
      loadSessions();
    }

    return () => {
      mounted = false;
    };
  }, [selectedAgent]);

  const updateSession = async (
    sessionId: string,
    values: ChatUpdateRequest,
  ) => {
    try {
      const result = await api.updateSession(sessionId, values);
      setSessions(sessions.map((s) => (s.id === sessionId ? result : s)));
      message.success("会话保存成功");
      return true;
    } catch (error) {
      console.error("❌ Failed to save session:", error);
      message.error("会话保存失败");
      return false;
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      await api.deleteSession(sessionId);
      setSessions(sessions.filter((s) => s.id !== sessionId));
      message.success("会话删除成功");
      return true;
    } catch (error) {
      console.error("❌ Failed to delete session:", error);
      message.error("会话删除失败");
      return false;
    }
  };

  const batchDeleteSessions = async (sessionIds: string[]) => {
    try {
      await api.batchDeleteSessions(sessionIds);
      setSessions(sessions.filter((s) => !sessionIds.includes(s.id)));
      message.success(
        `成功删除 ${sessionIds.length} 个会话`,
      );
      return true;
    } catch (error) {
      console.error("❌ Failed to batch delete sessions:", error);
      message.error("批量删除会话失败");
      return false;
    }
  };

  return {
    sessions,
    loading,
    updateSession,
    deleteSession,
    batchDeleteSessions,
  };
}
