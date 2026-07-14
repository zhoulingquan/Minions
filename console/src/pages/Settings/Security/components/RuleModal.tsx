import { useEffect } from "react";
import { Modal, Form, Input, Select } from "@agentscope-ai/design";
import type { FormInstance } from "antd";
import type { ToolGuardRule } from "../../../../api/modules/security";

const SEVERITY_OPTIONS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];
const CATEGORY_OPTIONS = [
  "command_injection",
  "code_execution",
  "data_exfiltration",
  "path_traversal",
  "sensitive_file_access",
  "network_abuse",
  "credential_exposure",
  "resource_abuse",
  "privilege_escalation",
  "prompt_injection",
];
const BUILTIN_TOOLS = [
  "execute_shell_command",
  "execute_python_code",
  "browser_use",
  "desktop_screenshot",
  "view_image",
  "read_file",
  "write_file",
  "edit_file",
  "append_file",
  "view_text_file",
  "write_text_file",
  "send_file_to_user",
];

interface RuleModalProps {
  open: boolean;
  editingRule: ToolGuardRule | null;
  existingRuleIds: string[];
  onOk: () => void;
  onCancel: () => void;
  form: FormInstance;
}

export function RuleModal({
  open,
  editingRule,
  existingRuleIds,
  onOk,
  onCancel,
  form,
}: RuleModalProps) {

  useEffect(() => {
    if (open) {
      if (editingRule) {
        form.setFieldsValue({
          ...editingRule,
          patterns: editingRule.patterns.join("\n"),
          exclude_patterns: editingRule.exclude_patterns.join("\n"),
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          severity: "HIGH",
          category: "command_injection",
          tools: [],
          params: [],
          patterns: "",
          exclude_patterns: "",
        });
      }
    }
  }, [open, editingRule, form]);

  const toolOptions = BUILTIN_TOOLS.map((name) => ({
    label: name,
    value: name,
  }));

  return (
    <Modal
      title={
        editingRule
          ? "编辑自定义规则"
          : "添加自定义规则"
      }
      open={open}
      onOk={onOk}
      onCancel={onCancel}
      okText={"确认"}
      cancelText={"取消"}
      width={640}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          label={"规则 ID"}
          name="id"
          rules={[
            { required: true, message: "规则 ID 不能为空" },
            {
              validator: (_, value) => {
                if (!value || editingRule) return Promise.resolve();
                if (existingRuleIds.includes(value)) {
                  return Promise.reject(
                    new Error("已存在相同 ID 的规则"),
                  );
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input placeholder="TOOL_CMD_CUSTOM_RULE" disabled={!!editingRule} />
        </Form.Item>
        <Form.Item label={"目标工具"} name="tools">
          <Select
            mode="tags"
            options={toolOptions}
            placeholder={"留空匹配所有工具"}
            allowClear
          />
        </Form.Item>
        <Form.Item label={"目标参数"} name="params">
          <Select
            mode="tags"
            placeholder={"留空匹配所有参数"}
            allowClear
          />
        </Form.Item>
        <Form.Item label={"严重程度"} name="severity">
          <Select
            options={SEVERITY_OPTIONS.map((s) => ({ label: s, value: s }))}
          />
        </Form.Item>
        <Form.Item label={"分类"} name="category">
          <Select
            options={CATEGORY_OPTIONS.map((c) => ({
              label: c === "command_injection" ? "命令注入" : c === "code_execution" ? "代码执行" : c === "data_exfiltration" ? "数据外泄" : c === "path_traversal" ? "路径穿越" : c === "sensitive_file_access" ? "敏感文件访问" : c === "network_abuse" ? "网络滥用" : c === "credential_exposure" ? "凭证泄露" : c === "resource_abuse" ? "资源滥用" : c === "privilege_escalation" ? "权限提升" : c === "prompt_injection" ? "提示注入" : c,
              value: c,
            }))}
          />
        </Form.Item>
        <Form.Item
          label={"正则模式"}
          name="patterns"
          rules={[
            { required: true, message: "至少需要一个正则模式" },
          ]}
          tooltip={"每行一个正则表达式，匹配工具参数值（不区分大小写）。"}
        >
          <Input.TextArea
            rows={3}
            placeholder={"\\brm\\b\\n\\bmv\\b"}
            style={{ fontFamily: "monospace" }}
          />
        </Form.Item>
        <Form.Item
          label={"排除模式"}
          name="exclude_patterns"
          tooltip={"每行一个正则表达式。如果匹配，则跳过该规则。"}
        >
          <Input.TextArea
            rows={2}
            placeholder={"^#"}
            style={{ fontFamily: "monospace" }}
          />
        </Form.Item>
        <Form.Item
          label={"描述"}
          name="description"
        >
          <Input placeholder={"该规则检测什么？"} />
        </Form.Item>
        <Form.Item
          label={"修复建议"}
          name="remediation"
        >
          <Input placeholder={"触发规则时建议的操作"} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
