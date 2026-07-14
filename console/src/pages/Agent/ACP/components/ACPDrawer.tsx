import {
  Drawer,
  Form,
  Input,
  Switch,
  Button,
  Select,
  InputNumber,
} from "@agentscope-ai/design";
import { LinkOutlined } from "@ant-design/icons";
import type { FormInstance } from "antd";
import {
  ACP_DEFAULT_STDIO_BUFFER_LIMIT_BYTES,
  type ACPAgentConfig,
  type ACPToolParseMode,
} from "../../../../api/types";
import { getWebsiteLang } from "../../../../layouts/constants";
import styles from "../../../Control/Channels/index.module.less";
import { openExternalLink } from "../../../../utils/openExternalLink";

interface ACPDrawerProps {
  open: boolean;
  activeKey: string | null;
  isCreateMode?: boolean;
  form: FormInstance<Record<string, unknown>>;
  saving: boolean;
  initialValues?: ACPAgentConfig;
  canEditKey?: boolean;
  canDelete?: boolean;
  onClose: () => void;
  onSubmit: (values: Record<string, unknown>) => void;
  onDelete?: () => void;
}

const TOOL_PARSE_MODE_OPTIONS: { value: ACPToolParseMode; label: string }[] = [
  { value: "call_title", label: "call_title" },
  { value: "update_detail", label: "update_detail" },
  { value: "call_detail", label: "call_detail" },
];

const ACP_DOC_SECTION_HASH = {
  zh: "如何配置外部-runner",
  en: "How-to-configure-external-runners",
} as const;

function getACPDocsUrl(lang: string): string {
  const websiteLang = getWebsiteLang(lang);
  const hash =
    websiteLang === "zh" ? ACP_DOC_SECTION_HASH.zh : ACP_DOC_SECTION_HASH.en;
  return `https://minions.agentscope.io/docs/acp-integration?lang=${websiteLang}#${hash}`;
}

export function parseArgsText(value: unknown): string[] {
  return String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseEnvText(value: unknown): Record<string, string> {
  return String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, line) => {
      const index = line.indexOf("=");
      if (index >= 0) {
        const key = line.slice(0, index).trim();
        const envValue = line.slice(index + 1).trim();
        if (key) acc[key] = envValue;
      }
      return acc;
    }, {});
}

function findInvalidEnvLine(value: unknown): string | null {
  const lines = String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

  for (const line of lines) {
    const index = line.indexOf("=");
    if (index <= 0 || !line.slice(0, index).trim()) {
      return line;
    }
  }
  return null;
}

export function stringifyArgs(args: string[] = []): string {
  return args.join("\n");
}

export function stringifyEnv(env: Record<string, string> = {}): string {
  return Object.entries(env)
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
}

export function ACPDrawer({
  open,
  activeKey,
  isCreateMode = false,
  form,
  saving,
  initialValues,
  canEditKey = false,
  canDelete = false,
  onClose,
  onSubmit,
  onDelete,
}: ACPDrawerProps) {

  return (
    <Drawer
      title={
        isCreateMode
          ? "新增 ACP Agent"
          : activeKey
          ? `${"编辑 ACP 配置"}: ${activeKey}`
          : "编辑 ACP 配置"
      }
      open={open}
      onClose={onClose}
      width={520}
      footer={
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div>
            {canDelete ? (
              <Button danger onClick={onDelete}>
                {"删除"}
              </Button>
            ) : null}
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button onClick={onClose}>{"取消"}</Button>
            <Button
              type="primary"
              loading={saving}
              onClick={() => form.submit()}
            >
              {"保存"}
            </Button>
          </div>
        </div>
      }
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={initialValues}
        onFinish={onSubmit}
      >
        <Form.Item
          name="agentKey"
          label={"Agent Key"}
          rules={[
            { required: true, message: "请输入 Agent Key" },
            {
              pattern: /^[A-Za-z0-9_-]+$/,
              message: "Agent Key 只能包含字母、数字、下划线和连字符",
            },
          ]}
        >
          <Input placeholder="my_custom_runner" disabled={!canEditKey} />
        </Form.Item>

        <Form.Item
          name="enabled"
          label={"启用"}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          name="command"
          label={"命令"}
          rules={[{ required: true, message: "请输入命令" }]}
        >
          <Input placeholder="qwen" />
        </Form.Item>

        <Form.Item
          name="argsText"
          label={"参数"}
          tooltip={"每行一个参数"}
        >
          <Input.TextArea autoSize={{ minRows: 4, maxRows: 8 }} />
        </Form.Item>

        <Form.Item
          name="envText"
          label={"环境变量"}
          tooltip={"每行使用 KEY=VALUE 格式"}
          rules={[
            {
              validator: async (_, value) => {
                const invalidLine = findInvalidEnvLine(value);
                if (invalidLine) {
                  throw new Error(
                    `无效环境变量格式：${invalidLine}`,
                  );
                }
              },
            },
          ]}
        >
          <Input.TextArea autoSize={{ minRows: 4, maxRows: 8 }} />
        </Form.Item>

        <div className={styles.formTopActions}>
          <Button
            type="text"
            size="small"
            icon={<LinkOutlined />}
            onClick={() => openExternalLink(getACPDocsUrl("zh"))}
            title={"打开 ACP 集成文档，并跳转到“如何配置外部 runner”章节"}
            className={styles.dingtalkDocBtn}
            style={{ color: "#FF7F16" }}
          >
            {"配置文档"}
          </Button>
        </div>

        <Form.Item
          name="trusted"
          label={"可信执行"}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          name="tool_parse_mode"
          label={"工具解析模式"}
          rules={[{ required: true, message: "请选择工具解析模式" }]}
        >
          <Select options={TOOL_PARSE_MODE_OPTIONS} />
        </Form.Item>

        <Form.Item
          name="stdio_buffer_limit_bytes"
          label={"Stdio 缓冲上限"}
          tooltip={"ACP 子进程 stdio 单行读取缓冲的最大字节数。"}
          rules={[
            {
              required: true,
              message: "请输入 stdio 缓冲上限",
            },
            {
              type: "number",
              min: 1,
              message: "stdio 缓冲上限至少为 1 字节",
            },
          ]}
        >
          <InputNumber
            style={{ width: "100%" }}
            min={1}
            step={1024}
            placeholder={String(ACP_DEFAULT_STDIO_BUFFER_LIMIT_BYTES)}
          />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
