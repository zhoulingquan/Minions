import { useEffect, useState } from "react";
import { Spin } from "antd";
import {
  Drawer,
  Form,
  Input,
  InputNumber,
  Switch,
  Select,
  Button,
} from "@agentscope-ai/design";
import api from "../../../api";
import type { ToolInfo } from "../../../api/modules/tools";

/** Drawer for configuring a built-in tool's config_fields. */
export function ToolConfigDrawer({
  tool,
  open,
  onClose,
  onSave,
}: {
  tool: ToolInfo | null;
  open: boolean;
  onClose: () => void;
  onSave: (values: Record<string, unknown>) => Promise<void>;
}) {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(false);
  
  // Fetch latest config from backend whenever the drawer opens.
  // Cleanup cancels stale in-flight requests on rapid tool switches.
  useEffect(() => {
    if (!open || !tool) return;
    form.resetFields();
    setLoadingConfig(true);
    let cancelled = false;
    api
      .getToolConfig(tool.name)
      .then((config) => {
        if (!cancelled) form.setFieldsValue(config || {});
      })
      .catch(() => {
        // Leave form empty on error
      })
      .finally(() => {
        if (!cancelled) setLoadingConfig(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, tool, form]);

  const handleFinish = async (values: Record<string, unknown>) => {
    try {
      setSaving(true);
      await onSave(values);
      onClose();
    } catch (error) {
      console.error("Failed to save config:", error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Drawer
      title={tool ? `${"配置"} - ${tool.name}` : "配置"}
      open={open}
      onClose={onClose}
      width={520}
      footer={
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button onClick={onClose}>{"取消"}</Button>
          <Button
            type="primary"
            loading={saving || loadingConfig}
            disabled={loadingConfig}
            onClick={() => form.submit()}
          >
            {"保存"}
          </Button>
        </div>
      }
      destroyOnHidden
    >
      <Spin spinning={loadingConfig}>
        <Form form={form} layout="vertical" onFinish={handleFinish}>
          {tool?.config_fields?.map((field) => {
            // Render different input types based on field type
            const renderInput = () => {
              switch (field.type) {
                case "password":
                  return (
                    <Input.Password
                      placeholder={field.placeholder}
                      autoComplete="off"
                    />
                  );

                case "number":
                  return (
                    <InputNumber
                      placeholder={field.placeholder}
                      min={field.min}
                      max={field.max}
                      style={{ width: "100%" }}
                    />
                  );

                case "boolean":
                  return <Switch />;

                case "select":
                  return (
                    <Select placeholder={field.placeholder}>
                      {field.options?.map((option) => (
                        <Select.Option key={option} value={option}>
                          {option}
                        </Select.Option>
                      ))}
                    </Select>
                  );

                case "textarea":
                  return (
                    <Input.TextArea
                      placeholder={field.placeholder}
                      rows={4}
                      autoSize={{ minRows: 2, maxRows: 8 }}
                    />
                  );

                case "text":
                default:
                  return <Input placeholder={field.placeholder} />;
              }
            };

            return (
              <Form.Item
                key={field.name}
                name={field.name}
                label={field.label}
                rules={[
                  {
                    required: field.required,
                    message: `${field.label} is required`,
                  },
                ]}
                help={field.help}
                valuePropName={field.type === "boolean" ? "checked" : "value"}
              >
                {renderInput()}
              </Form.Item>
            );
          })}
        </Form>
      </Spin>
    </Drawer>
  );
}
