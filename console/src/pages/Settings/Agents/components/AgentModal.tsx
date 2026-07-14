import { useEffect, useState, useMemo } from "react";
import {
  Modal,
  Form,
  Input,
  Button,
  Select,
  Space,
  Typography,
  Empty,
  Spin,
} from "antd";
import { CheckOutlined } from "@ant-design/icons";
import type { AgentSummary } from "@/api/types/agents";
import type { ProviderInfo } from "@/api/types/provider";
import { getAgentDisplayName } from "@/utils/agentDisplayName";
import type { GlobalSkillSpec } from "@/api/types/skill";
import { skillApi } from "@/api/modules/skill";
import { providerApi } from "@/api/modules/provider";
import { providerIcon } from "../../Models/components/providerIcon";
import styles from "../index.module.less";

const { Text } = Typography;

interface EligibleProvider {
  id: string;
  name: string;
  models: Array<{ id: string; name: string }>;
}

interface AgentModalProps {
  open: boolean;
  editingAgent: AgentSummary | null;
  form: ReturnType<typeof Form.useForm>[0];
  selectedSkills: string[];
  onSelectedSkillsChange: (skills: string[]) => void;
  onInstalledSkillsLoaded: (skills: string[]) => void;
  onSave: () => Promise<void>;
  onCancel: () => void;
}

export function AgentModal({
  open,
  editingAgent,
  form,
  selectedSkills,
  onSelectedSkillsChange,
  onInstalledSkillsLoaded,
  onSave,
  onCancel,
}: AgentModalProps) {
    const [globalSkillsData, setGlobalSkillsData] = useState<GlobalSkillSpec[]>([]);
  const [installedSkills, setInstalledSkills] = useState<string[]>([]);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);

  const selectedProviderId = Form.useWatch("active_model_provider", form);
  const selectedModelId = Form.useWatch("active_model_model", form);

  const eligibleProviders: EligibleProvider[] = useMemo(() => {
    return providers
      .filter((p) => {
        const hasModels =
          (p.models?.length ?? 0) + (p.extra_models?.length ?? 0) > 0;
        if (!hasModels) return false;
        if (p.require_api_key === false) return !!p.base_url;
        if (p.is_custom) return !!p.base_url;
        if (p.require_api_key ?? true) return !!p.api_key;
        return true;
      })
      .map((p) => ({
        id: p.id,
        name: p.name,
        models: [...(p.models ?? []), ...(p.extra_models ?? [])],
      }));
  }, [providers]);

  const availableModels = useMemo(() => {
    if (!selectedProviderId) return [];
    const provider = eligibleProviders.find((p) => p.id === selectedProviderId);
    return provider?.models ?? [];
  }, [selectedProviderId, eligibleProviders]);

  useEffect(() => {
    if (!open) return;

    setLoadingProviders(true);
    providerApi
      .listProviders()
      .then((data) => {
        if (Array.isArray(data)) setProviders(data);
      })
      .catch((err) => console.error("Failed to load providers:", err))
      .finally(() => setLoadingProviders(false));

    setLoadingSkills(true);

    const fetchGlobalSkills = skillApi.listGlobalSkills();
    const fetchInstalled = editingAgent
      ? skillApi.listSkills(editingAgent.id)
      : Promise.resolve([]);

    Promise.all([fetchGlobalSkills, fetchInstalled])
      .then(([pool, workspaceSkills]) => {
        const globalSkillNames = new Set(pool.map((skill) => skill.name));
        const installedSkills = workspaceSkills
          .filter((skill) => globalSkillNames.has(skill.name))
          .map((skill) => skill.name);

        setGlobalSkillsData(pool);
        setInstalledSkills(installedSkills);
        onInstalledSkillsLoaded(installedSkills);
        if (editingAgent) {
          onSelectedSkillsChange(installedSkills);
        } else {
          onSelectedSkillsChange([]);
        }
      })
      .finally(() => setLoadingSkills(false));
  }, [editingAgent, onInstalledSkillsLoaded, onSelectedSkillsChange, open]);

  const handleProviderChange = (providerId: string) => {
    form.setFieldsValue({
      active_model_provider: providerId,
      active_model_model: undefined,
    });
  };

  const handleClearModel = () => {
    form.setFieldsValue({
      active_model_provider: undefined,
      active_model_model: undefined,
    });
  };

  const toggleSkill = (name: string) => {
    const isInstalled = editingAgent && installedSkills.includes(name);
    if (isInstalled) return;

    if (selectedSkills.includes(name)) {
      onSelectedSkillsChange(selectedSkills.filter((s) => s !== name));
    } else {
      onSelectedSkillsChange([...selectedSkills, name]);
    }
  };

  const handleSelectAll = () => {
    const allNames = globalSkillsData.map((s) => s.name);
    onSelectedSkillsChange(allNames);
  };

  const handleSelectBuiltin = () => {
    const builtinNames = globalSkillsData
      .filter((s) => s.source === "builtin")
      .map((s) => s.name);
    onSelectedSkillsChange(
      Array.from(new Set([...installedSkills, ...builtinNames])),
    );
  };

  const handleSelectNone = () => {
    onSelectedSkillsChange(editingAgent ? [...installedSkills] : []);
  };

  return (
    <Modal
      title={
        editingAgent
          ? `编辑智能体 - ${getAgentDisplayName(editingAgent)}`
          : "创建新智能体"
      }
      open={open}
      onOk={onSave}
      onCancel={onCancel}
      width={640}
      okText={"保存"}
      cancelText={"取消"}
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item name="active_model_provider" hidden>
          <Input />
        </Form.Item>
        <Form.Item name="active_model_model" hidden>
          <Input />
        </Form.Item>

        {editingAgent && (
          <Form.Item name="id" label={"ID"}>
            <Input disabled />
          </Form.Item>
        )}
        {!editingAgent && (
          <Form.Item
            name="id"
            label={"智能体 ID（可选）"}
            help={"留空则自动生成。仅允许字母、数字、连字符和下划线。"}
            rules={[
              {
                pattern: /^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$/,
                message: "ID只能包含字母、数字、下划线和连字符",
              },
            ]}
          >
            <Input placeholder={"例如：my-agent"} />
          </Form.Item>
        )}
        <Form.Item
          name="name"
          label={"名称"}
          rules={[{ required: true, message: "请输入智能体名称" }]}
        >
          <Input placeholder={"例如：我的智能体"} />
        </Form.Item>
        <Form.Item name="description" label={"描述"}>
          <Input.TextArea
            placeholder={"简要描述这个智能体的用途..."}
            rows={3}
          />
        </Form.Item>
        <Form.Item label={"模型"} help={"为此智能体指定特定的 LLM 模型。留空则使用全局默认模型。"}>
          <Space.Compact style={{ width: "100%" }}>
            <Select
              value={selectedProviderId || undefined}
              onChange={handleProviderChange}
              placeholder={"使用全局默认"}
              allowClear
              onClear={handleClearModel}
              loading={loadingProviders}
              style={{ width: "45%", gap: "8px" }}
              showSearch
              optionFilterProp="label"
              options={eligibleProviders.map((p) => ({
                value: p.id,
                label: p.name,
              }))}
              optionRender={({ value }) => {
                const p = eligibleProviders.find((ep) => ep.id === value);
                if (!p) return value;
                return (
                  <Space size={6}>
                    <img
                      src={providerIcon(p.id)}
                      alt=""
                      style={{ width: 16, height: 16 }}
                    />
                    <span>{p.name}</span>
                  </Space>
                );
              }}
              notFoundContent={
                loadingProviders ? (
                  <Spin size="small" />
                ) : (
                  "暂无已配置的模型"
                )
              }
            />
            <Select
              value={selectedModelId || undefined}
              onChange={(modelId) =>
                form.setFieldsValue({ active_model_model: modelId })
              }
              placeholder={
                selectedProviderId
                  ? "模型"
                  : "使用全局默认"
              }
              disabled={!selectedProviderId}
              style={{ width: "55%" }}
              showSearch
              optionFilterProp="label"
              options={availableModels.map((m) => ({
                value: m.id,
                label: m.name || m.id,
              }))}
            />
          </Space.Compact>
        </Form.Item>
        <Form.Item
          name="workspace_dir"
          label={"工作区路径"}
          help={!editingAgent ? "留空将自动生成在 ~/.minions/workspaces/<id> 目录" : undefined}
        >
          <Input
            placeholder="~/.minions/workspaces/my-agent"
            disabled={!!editingAgent}
          />
        </Form.Item>
      </Form>

      <div style={{ marginTop: 4 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 8,
          }}
        >
          <Text type="secondary" style={{ fontSize: 13 }}>
            {editingAgent
              ? "添加技能"
              : "初始技能"}
          </Text>
          <Space size={4}>
            <Button size="small" type="primary" onClick={handleSelectAll}>
              {"全选"}
            </Button>
            <Button size="small" type="default" onClick={handleSelectBuiltin}>
              {"内置"}
            </Button>
            <Button size="small" type="default" onClick={handleSelectNone}>
              {"清空"}
            </Button>
          </Space>
        </div>

        {loadingSkills ? (
          <div style={{ textAlign: "center", padding: "16px 0" }}>
            <Spin size="small" />
          </div>
        ) : globalSkillsData.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={"全局技能中暂无可用技能"}
          />
        ) : (
          <div className={styles.pickerGrid}>
            {globalSkillsData.map((skill) => {
              const selected = selectedSkills.includes(skill.name);
              const isInstalled =
                !!editingAgent && installedSkills.includes(skill.name);
              return (
                <div
                  key={skill.name}
                  className={`${styles.pickerCard} ${
                    selected ? styles.pickerCardSelected : ""
                  } ${isInstalled ? styles.pickerCardDisabled : ""}`}
                  onClick={() => toggleSkill(skill.name)}
                >
                  {selected && (
                    <span className={styles.pickerCheck}>
                      <CheckOutlined />
                    </span>
                  )}
                  <div className={styles.pickerCardTitle}>{skill.name}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Modal>
  );
}
