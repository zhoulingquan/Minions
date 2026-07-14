import { useState, useCallback } from "react";
import { Button, Form, Input, Modal } from "@agentscope-ai/design";
import { PlusOutlined, ApiOutlined, CheckOutlined } from "@ant-design/icons";
import type { ModelInfo } from "../../../../api/types";
import api from "../../../../api";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import styles from "../index.module.less";

interface AddCloudModelProps {
  onSaved: () => void;
}

export function AddCloudModel({ onSaved }: AddCloudModelProps) {
    const { message } = useAppMessage();
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [form] = Form.useForm();
  const [discoveredModels, setDiscoveredModels] = useState<ModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [lastProviderId, setLastProviderId] = useState<string | null>(null);

  const handleOpen = useCallback(() => {
    form.resetFields();
    setDiscoveredModels([]);
    setSelectedModelId(null);
    setLastProviderId(null);
    setModalOpen(true);
  }, [form]);

  const handleClose = useCallback(() => {
    setModalOpen(false);
  }, []);

  const createProvider = async (values: Record<string, string>) => {
    const providerId = `custom-cloud-${Date.now()}`;
    const providerName = values.provider_name?.trim() || values.name?.trim() || values.model_id.trim() || "Cloud Model";

    await api.createCustomProvider({
      id: providerId,
      name: providerName,
      default_base_url: values.base_url.trim(),
      api_key_prefix: "",
      chat_model: "OpenAIChatModel",
    });

    await api.configureProvider(providerId, {
      api_key: values.api_key?.trim() || "",
      base_url: values.base_url.trim(),
    });

    return providerId;
  };

  const handleDiscover = async () => {
    try {
      const values = await form.validateFields(["base_url", "api_key"]);
      setDiscovering(true);
      setDiscoveredModels([]);
      setSelectedModelId(null);

      const allValues = form.getFieldsValue();
      const providerId = await createProvider({
        ...values,
        provider_name: allValues.provider_name || "",
        model_id: allValues.model_id || "",
        name: allValues.name || "",
      });
      setLastProviderId(providerId);

      const result = await api.discoverModels(providerId, undefined, false);

      if (result.success && result.models.length > 0) {
        setDiscoveredModels(result.models);
      } else if (result.success) {
        message.info("自动发现完成，未新增模型");
      } else {
        message.warning(result.message || "自动发现模型失败");
      }
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg = error instanceof Error ? error.message : "保存失败";
      message.error(errMsg);
    } finally {
      setDiscovering(false);
    }
  };

  const handleSelectModel = (model: ModelInfo) => {
    setSelectedModelId(model.id);
    form.setFieldsValue({
      model_id: model.id,
      name: model.name || model.id,
    });
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      let providerId = lastProviderId;
      if (!providerId) {
        providerId = await createProvider(values);
      }

      const modelId = values.model_id.trim();
      const modelName = values.name?.trim() || modelId;

      await api.addModel(providerId, {
        id: modelId,
        name: modelName,
      });

      message.success(`模型 "${modelName}" 已添加`);
      onSaved();
      setModalOpen(false);
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg = error instanceof Error ? error.message : "保存失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Button type="primary" icon={<PlusOutlined />} onClick={handleOpen}>
        {"添加自定义模型"}
      </Button>

      <Modal
        width={640}
        title={"添加自定义模型"}
        open={modalOpen}
        onCancel={handleClose}
        destroyOnHidden
        footer={
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button onClick={handleClose}>{"取消"}</Button>
            <Button
              icon={<ApiOutlined />}
              onClick={handleDiscover}
              loading={discovering}
            >
              {"获取模型列表"}
            </Button>
            <Button type="primary" loading={saving} onClick={handleSave}>
              {"保存"}
            </Button>
          </div>
        }
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="provider_name"
            label={"显示名称"}
            rules={[{ required: true, message: "显示名称" }]}
          >
            <Input placeholder={"例如 OpenAI, Google Gemini"} />
          </Form.Item>

          <Form.Item
            name="model_id"
            label={"模型 ID"}
            rules={[{ required: true, message: "请输入模型 ID" }]}
          >
            <Input placeholder={"例如 gpt-4o, gemini-2.0-flash"} />
          </Form.Item>

          <Form.Item name="name" label={"模型名称"}>
            <Input placeholder={"例如 GPT-4o, Gemini 2.0 Flash"} />
          </Form.Item>

          <Form.Item
            name="base_url"
            label={"基础 URL"}
            rules={[
              { required: true, message: "请输入 API 基础 URL" },
              {
                validator: (_: unknown, value: string) => {
                  if (!value || !value.trim()) return Promise.resolve();
                  try {
                    const url = new URL(value.trim());
                    if (!["http:", "https:"].includes(url.protocol)) {
                      return Promise.reject(new Error("请输入有效的 URL"));
                    }
                    return Promise.resolve();
                  } catch {
                    return Promise.reject(new Error("请输入有效的 URL"));
                  }
                },
              },
            ]}
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item name="api_key" label={"API 密钥"}>
            <Input.Password placeholder={"输入 API 密钥（可选）"} />
          </Form.Item>
        </Form>

        {discoveredModels.length > 0 && (
          <div className={styles.discoveredModelsSection}>
            <div className={styles.discoveredModelsTitle}>
              {"可用模型："} {discoveredModels.length} {"模型"}
            </div>
            <div className={styles.discoveredModelsList}>
              {discoveredModels.map((m) => (
                <div
                  key={m.id}
                  className={`${styles.discoveredModelItem}${selectedModelId === m.id ? ` ${styles.discoveredModelItemActive}` : ""}`}
                  onClick={() => handleSelectModel(m)}
                >
                  {selectedModelId === m.id && (
                    <CheckOutlined className={styles.discoveredModelCheck} />
                  )}
                  <span className={styles.discoveredModelId}>{m.id}</span>
                  {m.name && m.name !== m.id && (
                    <span className={styles.discoveredModelName}>{m.name}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
