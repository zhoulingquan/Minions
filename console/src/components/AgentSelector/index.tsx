import { Select, Tag, Tooltip } from "antd";
import { useCallback, useEffect, useState } from "react";
import { Bot, CheckCircle, EyeOff, ChevronRight } from "lucide-react";
import { SparkDownLine, SparkUpLine } from "@agentscope-ai/icons";
import { useAgentStore } from "../../stores/agentStore";
import { agentsApi } from "../../api/modules/agents";
import { getAgentDisplayName } from "../../utils/agentDisplayName";
import { useNavigate } from "react-router-dom";
import { useAppMessage } from "../../hooks/useAppMessage";
import styles from "./index.module.less";

interface AgentSelectorProps {
  collapsed?: boolean;
}

export default function AgentSelector({
  collapsed = false,
}: AgentSelectorProps) {
    const navigate = useNavigate();
  const { selectedAgent, agents, setSelectedAgent, setAgents } =
    useAgentStore();
  const { message } = useAppMessage();
  const [loading, setLoading] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const loadAgents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await agentsApi.listAgents();
      // Sort agents: enabled first, disabled last
      const sortedAgents = [...data.agents].sort((a, b) => {
        if (a.enabled === b.enabled) return 0;
        return a.enabled ? -1 : 1;
      });
      setAgents(sortedAgents);
    } catch (error) {
      console.error("Failed to load agents:", error);
      message.error("加载智能体列表失败");
    } finally {
      setLoading(false);
    }
  }, [message, setAgents]);

  useEffect(() => {
    void loadAgents();
  }, [loadAgents]);

  const handleChange = (value: string) => {
    const targetAgent = agents?.find((a) => a.id === value);

    // Prevent switching to disabled agent
    if (targetAgent && !targetAgent.enabled) {
      message.warning("该智能体已被禁用，请先在管理页面启用");
      return;
    }

    setSelectedAgent(value);
    message.success("智能体切换成功");
  };

  // Auto-switch to default if the selected agent was deleted or disabled
  useEffect(() => {
    if (!agents?.length || selectedAgent === "default") return;

    const currentAgent = agents.find((a) => a.id === selectedAgent);

    if (!currentAgent) {
      // Agent was deleted — no longer in the list
      setSelectedAgent("default");
      message.warning("当前智能体已被删除，已自动切换到默认智能体");
    } else if (!currentAgent.enabled) {
      // Agent exists but was disabled
      setSelectedAgent("default");
      message.warning("当前智能体已被禁用，已自动切换到默认智能体");
    }
  }, [agents, message, selectedAgent, setSelectedAgent]);

  // Count only enabled agents for badge
  const enabledCount = agents?.filter((a) => a.enabled).length ?? 0;
  const agentCount = enabledCount;

  const currentAgentInfo = agents?.find((a) => a.id === selectedAgent);

  // Collapsed: show just the Bot icon with Tooltip
  if (collapsed) {
    return (
      <Tooltip
        title={
          currentAgentInfo
            ? getAgentDisplayName(currentAgentInfo)
            : selectedAgent
        }
        placement="right"
        overlayInnerStyle={{ background: "rgba(0,0,0,0.75)", color: "#fff" }}
      >
        <div className={styles.agentSelectorCollapsed}>
          <Bot size={18} strokeWidth={2} />
        </div>
      </Tooltip>
    );
  }

  return (
    <div className={styles.agentSelectorWrapper}>
      <div className={styles.agentSelectorLabel}>
        <span>
          {"当前智能体"}
          {agentCount > 0 && (
            <span className={styles.agentCountBadge}> ({agentCount})</span>
          )}
        </span>
      </div>
      <Select
        value={selectedAgent}
        onChange={handleChange}
        loading={loading}
        className={styles.agentSelector}
        placeholder={"选择智能体"}
        optionLabelProp="label"
        popupClassName={styles.agentSelectorDropdown}
        onOpenChange={setDropdownOpen}
        suffixIcon={
          dropdownOpen ? <SparkUpLine size={20} /> : <SparkDownLine size={20} />
        }
        popupRender={(menu) => (
          <>
            <div className={styles.dropdownHeader}>
              <span className={styles.dropdownHeaderTitle}>
                {"当前智能体"}
              </span>
              <button
                className={styles.managementLink}
                onClick={() => navigate("/agents")}
              >
                {"智能体管理"}
                <ChevronRight size={12} strokeWidth={2.5} />
              </button>
            </div>
            {menu}
          </>
        )}
      >
        {agents?.map((agent) => (
          <Select.Option
            key={agent.id}
            value={agent.id}
            disabled={!agent.enabled}
            label={
              <div className={styles.selectedAgentLabel}>
                <Bot size={14} strokeWidth={2} />
                <span>{getAgentDisplayName(agent)}</span>
                {!agent.enabled && <EyeOff size={12} strokeWidth={2} />}
              </div>
            }
          >
            <div
              className={styles.agentOption}
              style={{ opacity: agent.enabled ? 1 : 0.5 }}
            >
              <div className={styles.agentOptionHeader}>
                <div className={styles.agentOptionIcon}>
                  <Bot size={16} strokeWidth={2} />
                </div>
                <div className={styles.agentOptionContent}>
                  <div className={styles.agentOptionName}>
                    <span className={styles.agentOptionNameText}>
                      {getAgentDisplayName(agent)}
                    </span>
                    {agent.id === selectedAgent && (
                      <CheckCircle
                        size={14}
                        strokeWidth={2}
                        className={styles.activeIndicator}
                      />
                    )}
                    {!agent.enabled && (
                      <Tag style={{ margin: 0 }}>{"已禁用"}</Tag>
                    )}
                  </div>
                  {agent.description && (
                    <div className={styles.agentOptionDescription}>
                      {agent.description}
                    </div>
                  )}
                </div>
              </div>
              <div className={styles.agentOptionId}>ID: {agent.id}</div>
            </div>
          </Select.Option>
        ))}
      </Select>
    </div>
  );
}
