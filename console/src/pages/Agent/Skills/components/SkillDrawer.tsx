import { useState, useEffect, useCallback, useRef } from "react";
import { Drawer, Form, Input, Button, Select } from "@agentscope-ai/design";
import { useAppMessage } from "../../../../hooks/useAppMessage";
import { ThunderboltOutlined, StopOutlined } from "@ant-design/icons";
import type { FormInstance } from "antd";
import type { SkillSpec } from "../../../../api/types";
import { MarkdownCopy } from "../../../../components/MarkdownCopy/MarkdownCopy";
import { api } from "../../../../api";
import { deriveInstalledFromLabel } from "../../../../utils/skill";

/** Parse YAML frontmatter from a `---`-delimited content string. */
export function parseFrontmatter(
  content: string,
): Record<string, string> | null {
  try {
    const trimmed = content.trim();
    if (!trimmed.startsWith("---")) return null;
    const endIndex = trimmed.indexOf("---", 3);
    if (endIndex === -1) return null;
    const frontmatterBlock = trimmed.slice(3, endIndex).trim();
    if (!frontmatterBlock) return null;
    const result: Record<string, string> = {};
    for (const line of frontmatterBlock.split("\n")) {
      const colonIndex = line.indexOf(":");
      if (colonIndex > 0) {
        const key = line.slice(0, colonIndex).trim();
        const value = line.slice(colonIndex + 1).trim();
        result[key] = value;
      }
    }
    return result;
  } catch {
    return null;
  }
}

const CHANNEL_OPTIONS = [
  { label: "all", value: "all" },
  { label: "console", value: "console" },
  { label: "discord", value: "discord" },
  { label: "telegram", value: "telegram" },
  { label: "dingtalk", value: "dingtalk" },
  { label: "feishu", value: "feishu" },
  { label: "imessage", value: "imessage" },
  { label: "qq", value: "qq" },
  { label: "mattermost", value: "mattermost" },
  { label: "wecom", value: "wecom" },
  { label: "mqtt", value: "mqtt" },
];

export interface SkillDrawerFormValues {
  name: string;
  description?: string;
  content: string;
  enabled?: boolean;
  channels?: string[];
  source?: string;
  config?: Record<string, unknown>;
}

interface SkillDrawerProps {
  open: boolean;
  editingSkill: SkillSpec | null;
  form: FormInstance<SkillDrawerFormValues>;
  onClose: () => void;
  onSubmit: (values: SkillSpec) => void;
  onContentChange?: (content: string) => void;
}

export function SkillDrawer({
  open,
  editingSkill,
  form,
  onClose,
  onSubmit,
  onContentChange,
}: SkillDrawerProps) {
  const [showMarkdown, setShowMarkdown] = useState(true);
  const [contentValue, setContentValue] = useState("");
  const [optimizing, setOptimizing] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [configText, setConfigText] = useState("{}");
  const [configError, setConfigError] = useState("");
  const { message } = useAppMessage();

  const validateFrontmatter = useCallback(
    (_: unknown, value: string) => {
      const content = contentValue || value;
      if (!content || !content.trim()) {
        return Promise.reject(new Error("请输入技能内容"));
      }
      const fm = parseFrontmatter(content);
      if (!fm) {
        return Promise.reject(new Error("Skills内容必须以 --- 开头和结尾"));
      }
      if (!fm.name) {
        return Promise.reject(new Error("Skills 中缺少必填字段：name"));
      }
      if (!fm.description) {
        return Promise.reject(new Error("Skills 中缺少必填字段：description"));
      }
      return Promise.resolve();
    },
    [contentValue],
  );

  useEffect(() => {
    if (editingSkill) {
      const channels = editingSkill.channels || ["all"];
      const fallbackConfigText = JSON.stringify(
        editingSkill.config || {},
        null,
        2,
      );
      setContentValue(editingSkill.content);
      setConfigText(fallbackConfigText);
      form.setFieldsValue({
        name: editingSkill.name,
        content: editingSkill.content,
        channels,
        source: editingSkill.source,
      });
      setConfigError("");
      let active = true;
      api
        .getSkillConfig(editingSkill.name)
        .then((res) => {
          if (!active) return;
          setConfigText(JSON.stringify(res.config || {}, null, 2));
        })
        .catch(() => {
          if (!active) return;
          setConfigText(fallbackConfigText);
        });
      return () => {
        active = false;
      };
    } else {
      setContentValue("");
      setConfigText("{}");
      setConfigError("");
      form.resetFields();
    }
  }, [editingSkill, form]);

  const handleSubmit = async (values: SkillDrawerFormValues) => {
    let parsedConfig: Record<string, unknown> | undefined;
    const trimmed = configText.trim();
    if (!trimmed) {
      parsedConfig = {};
    } else {
      try {
        parsedConfig = JSON.parse(trimmed);
        setConfigError("");
      } catch {
        setConfigError("JSON 格式无效");
        return;
      }
    }
    onSubmit({
      ...editingSkill,
      ...values,
      content: contentValue || values.content,
      source: editingSkill?.source || "",
      config: parsedConfig,
    });
  };

  const handleContentChange = (content: string) => {
    setContentValue(content);
    form.setFieldsValue({ content });
    form.validateFields(["content"]).catch(() => {});
    if (onContentChange) {
      onContentChange(content);
    }
  };

  const handleOptimize = async () => {
    if (!contentValue.trim()) {
      message.warning("没有可优化的内容");
      return;
    }

    setOptimizing(true);
    abortControllerRef.current = new AbortController();
    const originalContent = contentValue;
    setContentValue(""); // Clear content for streaming output

    try {
      await api.streamOptimizeSkill(
        originalContent,
        (textChunk) => {
          setContentValue((prev) => {
            const newContent = prev + textChunk;
            form.setFieldsValue({ content: newContent });
            return newContent;
          });
        },
        abortControllerRef.current.signal,
        "zh",
      );
      message.success("技能优化成功");
    } catch (error: unknown) {
      const aborted =
        error instanceof DOMException && error.name === "AbortError";
      if (!aborted) {
        message.error(error instanceof Error ? error.message : "技能优化失败");
      }
    } finally {
      setOptimizing(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopOptimize = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setOptimizing(false);
      abortControllerRef.current = null;
    }
  };

  const drawerFooter = (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        width: "100%",
      }}
    >
      <div>
        {!optimizing ? (
          <Button
            type="default"
            icon={<ThunderboltOutlined />}
            onClick={handleOptimize}
            disabled={!contentValue.trim()}
          >
            {"AI优化"}
          </Button>
        ) : (
          <Button
            type="default"
            danger
            icon={<StopOutlined />}
            onClick={handleStopOptimize}
          >
            {"停止"}
          </Button>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <Button onClick={onClose}>{"取消"}</Button>
        <Button type="primary" onClick={() => form.submit()}>
          {editingSkill ? "保存智能体版本" : "创建"}
        </Button>
      </div>
    </div>
  );

  return (
    <Drawer
      width={520}
      placement="right"
      title={editingSkill ? "调优智能体技能" : "创建技能"}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={drawerFooter}
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {!editingSkill ? (
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: "请输入技能名称" }]}
          >
            <Input placeholder={"例如：weather_query"} />
          </Form.Item>
        ) : (
          <Form.Item name="name" label="Name">
            <Input />
          </Form.Item>
        )}

        <Form.Item
          name="content"
          label="Content"
          rules={[{ required: true, validator: validateFrontmatter }]}
        >
          <MarkdownCopy
            content={contentValue}
            showMarkdown={showMarkdown}
            onShowMarkdownChange={setShowMarkdown}
            editable={true}
            onContentChange={handleContentChange}
            textareaProps={{
              ...(!editingSkill && {
                placeholder:
                  "【格式要求】\n---\nname: 技能名称（必填，英文小写下划线）\ndescription: 功能描述（必填，简洁清晰）\n---\n\n技能实现内容（Markdown格式）\n\n【示例】\n---\nname: weather_query\ndescription: 查询指定城市的天气信息\n---\n\n## 功能\n查询实时天气数据。\n\n## 使用\n用户输入城市名，返回天气信息。",
              }),
              rows: 12,
            }}
          />
        </Form.Item>

        <Form.Item name="channels" label={"适用频道"}>
          <Select mode="multiple" options={CHANNEL_OPTIONS} />
        </Form.Item>

        <Form.Item
          label={"配置"}
          validateStatus={configError ? "error" : undefined}
          help={configError || undefined}
        >
          <Input.TextArea
            rows={4}
            value={configText}
            onChange={(e) => {
              setConfigText(e.target.value);
              setConfigError("");
            }}
            placeholder={'{"KEY": "value"}'}
          />
        </Form.Item>

        {editingSkill && (
          <>
            <Form.Item name="source" label={"类型"}>
              <Input disabled />
            </Form.Item>
            <Form.Item label={"安装来源"}>
              <Input
                disabled
                value={deriveInstalledFromLabel(editingSkill.installed_from)}
              />
            </Form.Item>
          </>
        )}
      </Form>
    </Drawer>
  );
}
