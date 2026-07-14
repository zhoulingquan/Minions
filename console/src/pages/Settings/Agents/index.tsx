import { useState, useRef, useCallback } from "react";
import { Card, Button, Form } from "antd";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { PlusOutlined } from "@ant-design/icons";
import { agentsApi } from "../../../api/modules/agents";
import { invalidateSkillCache, skillApi } from "../../../api/modules/skill";
import type { AgentSummary } from "../../../api/types/agents";
import { useAgentStore } from "../../../stores/agentStore";
import { useAgents } from "./useAgents";
import { AgentTable, AgentModal } from "./components";
import { PageHeader } from "@/components/PageHeader";
import { reorderAgents } from "./reorder";
import styles from "./index.module.less";

export default function AgentsPage() {
    const { agents, loading, deleteAgent, toggleAgent, loadAgents, setAgents } =
    useAgents();
  const { selectedAgent, setSelectedAgent } = useAgentStore();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentSummary | null>(null);
  const [reordering, setReordering] = useState(false);
  const [form] = Form.useForm();
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const installedSkillsRef = useRef<string[]>([]);
  const { message } = useAppMessage();

  const handleCreate = () => {
    setEditingAgent(null);
    form.resetFields();
    form.setFieldsValue({
      workspace_dir: "",
      active_model_provider: undefined,
      active_model_model: undefined,
    });
    setSelectedSkills([]);
    installedSkillsRef.current = [];
    setModalVisible(true);
  };

  const handleEdit = async (agent: AgentSummary) => {
    try {
      setSelectedSkills([]);
      installedSkillsRef.current = [];
      invalidateSkillCache({ agentId: agent.id });
      const config = await agentsApi.getAgent(agent.id);
      setEditingAgent(agent);
      form.setFieldsValue({
        ...config,
        active_model_provider: config.active_model?.provider_id || undefined,
        active_model_model: config.active_model?.model || undefined,
      });
      setModalVisible(true);
    } catch (error) {
      console.error("Failed to load agent config:", error);
      message.error("加载智能体配置失败");
    }
  };

  const handleDelete = async (agentId: string) => {
    try {
      await deleteAgent(agentId);

      if (selectedAgent === agentId) {
        setSelectedAgent("default");
        message.info("已自动切换到默认智能体");
      }
    } catch {
      message.error("智能体删除失败");
    }
  };

  const handleToggle = async (agentId: string, currentEnabled: boolean) => {
    const newEnabled = !currentEnabled;
    try {
      await toggleAgent(agentId, newEnabled);

      if (!newEnabled && selectedAgent === agentId) {
        setSelectedAgent("default");
        message.info("已自动切换到默认智能体");
      }
    } catch {
      // Error already handled in hook
    }
  };

  const handleInstalledSkillsLoaded = useCallback((skills: string[]) => {
    installedSkillsRef.current = skills;
  }, []);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const workspaceRaw = values.workspace_dir;
      const workspace_dir =
        typeof workspaceRaw === "string"
          ? workspaceRaw.trim() || undefined
          : workspaceRaw;

      const providerId = values.active_model_provider;
      const modelId = values.active_model_model;
      const active_model =
        providerId && modelId
          ? { provider_id: providerId, model: modelId }
          : null;

      const rest = { ...values };
      delete rest.active_model_provider;
      delete rest.active_model_model;
      const payload = { ...rest, workspace_dir, active_model };

      if (editingAgent) {
        const previousInstalledSkills = installedSkillsRef.current;
        const newSkills = selectedSkills.filter(
          (skill) => !previousInstalledSkills.includes(skill),
        );

        for (const skill of newSkills) {
          await skillApi.downloadGlobalSkill({
            skill_name: skill,
            targets: [{ workspace_id: editingAgent.id }],
          });
        }
        await agentsApi.updateAgent(editingAgent.id, payload);
        installedSkillsRef.current = [
          ...previousInstalledSkills,
          ...newSkills.filter(
            (skill) => !previousInstalledSkills.includes(skill),
          ),
        ];
        invalidateSkillCache({ agentId: editingAgent.id });
        message.success("智能体更新成功");
      } else {
        const result = await agentsApi.createAgent({
          ...payload,
          language: "zh",
          skill_names: selectedSkills,
        });
        message.success(`${"智能体创建成功"} (ID: ${result.id})`);
      }

      setModalVisible(false);
      await loadAgents();
    } catch (error) {
      console.error("Failed to save agent:", error);
      if (editingAgent) {
        invalidateSkillCache({ agentId: editingAgent.id });
      }
      message.error(
        error instanceof Error ? error.message : "保存智能体失败",
      );
    }
  };

  const handleReorder = async (activeId: string, overId: string) => {
    const nextAgents = reorderAgents(agents, activeId, overId);
    if (nextAgents === agents) {
      return;
    }

    const previousAgents = agents;
    setAgents(nextAgents);
    setReordering(true);

    try {
      await agentsApi.reorderAgents(nextAgents.map((agent) => agent.id));
      message.success("智能体顺序已保存");
    } catch (error) {
      console.error("Failed to reorder agents:", error);
      setAgents(previousAgents);
      message.error("保存智能体顺序失败");
    } finally {
      setReordering(false);
    }
  };

  return (
    <div className={styles.agentsPage}>
      <PageHeader
        parent={"设置"}
        current={"智能体"}
        extra={
          <div className={styles.headerRight}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              {"创建智能体"}
            </Button>
          </div>
        }
      />

      <Card className={styles.tableCard}>
        <AgentTable
          agents={agents}
          loading={loading || reordering}
          reordering={reordering}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onToggle={handleToggle}
          onReorder={handleReorder}
        />
      </Card>

      <AgentModal
        open={modalVisible}
        editingAgent={editingAgent}
        form={form}
        selectedSkills={selectedSkills}
        onSelectedSkillsChange={setSelectedSkills}
        onInstalledSkillsLoaded={handleInstalledSkillsLoaded}
        onSave={handleSubmit}
        onCancel={() => setModalVisible(false)}
      />
    </div>
  );
}
