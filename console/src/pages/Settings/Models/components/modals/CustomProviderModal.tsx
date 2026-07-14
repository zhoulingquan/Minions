import { useState, useEffect } from "react";
import { Form, Input, Modal, Select } from "@agentscope-ai/design";
import api from "../../../../../api";
import { useAppMessage } from "../../../../../hooks/useAppMessage";

interface CustomProviderModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function CustomProviderModal({
  open,
  onClose,
  onSaved,
}: CustomProviderModalProps) {
    const { message } = useAppMessage();
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (open) {
      form.resetFields();
    }
  }, [open, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await api.createCustomProvider({
        id: values.id.trim(),
        name: values.name.trim(),
        default_base_url: values.default_base_url?.trim() || "",
        api_key_prefix: values.api_key_prefix?.trim() || "",
        chat_model: values.chat_model || "OpenAIChatModel",
      });
      message.success(
        `提供商 "${values.name.trim()}" 已创建`,
      );
      onSaved();
      onClose();
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error
          ? error.message
          : "创建提供商失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={"添加自定义提供商"}
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={saving}
      okText={"创建"}
      cancelText={"取消"}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        style={{ marginTop: 16 }}
        initialValues={{ chat_model: "OpenAIChatModel" }}
      >
        <Form.Item
          name="id"
          label={"提供商 ID"}
          extra={"小写字母、数字、连字符、下划线，创建后不可更改。"}
          rules={[
            { required: true, message: "提供商 ID" },
            {
              pattern: /^[a-z][a-z0-9_-]{0,63}$/,
              message: "小写字母、数字、连字符、下划线，创建后不可更改。",
            },
          ]}
        >
          <Input placeholder={"例如 openai, google, anthropic"} />
        </Form.Item>

        <Form.Item
          name="name"
          label={"显示名称"}
          rules={[{ required: true, message: "显示名称" }]}
        >
          <Input placeholder={"例如 OpenAI, Google Gemini"} />
        </Form.Item>

        <Form.Item
          name="default_base_url"
          label={"默认 Base URL"}
        >
          <Input placeholder={"例如 https://api.example.com"} />
        </Form.Item>

        <Form.Item
          name="chat_model"
          label={"协议"}
          rules={[
            {
              required: true,
              message: "请选择协议",
            },
          ]}
          extra={"为当前配置选择提供商 API 协议。"}
        >
          <Select
            options={[
              {
                value: "OpenAIChatModel",
                label: "OpenAI 兼容（Chat Completions）",
              },
              {
                value: "OpenAIResponseModel",
                label: "OpenAI 兼容（Response API）",
              },
              {
                value: "AnthropicChatModel",
                label: "Anthropic（Messages API）",
              },
            ]}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
