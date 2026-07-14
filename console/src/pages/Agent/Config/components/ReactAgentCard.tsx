import {
  Form,
  Input,
  InputNumber,
  Select,
  Card,
  Alert,
  Switch,
} from "@agentscope-ai/design";
import { useTimezoneOptions } from "../../../../hooks/useTimezoneOptions";
import {
  CONTEXT_MANAGER_BACKEND_OPTIONS,
} from "../../../../constants/backendMappings";
import styles from "../index.module.less";

const LANGUAGE_OPTIONS = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
  { value: "id", label: "Bahasa Indonesia" },
  { value: "ru", label: "Русский" },
];

interface ReactAgentCardProps {
  language: string;
  savingLang: boolean;
  onLanguageChange: (value: string) => void;
  timezone: string;
  savingTimezone: boolean;
  onTimezoneChange: (value: string) => void;
}

export function ReactAgentCard({
  language,
  savingLang,
  onLanguageChange,
  timezone,
  savingTimezone,
  onTimezoneChange,
}: ReactAgentCardProps) {
  return (
    <Card className={styles.formCard} title={"ReAct 智能体"}>
      <div className={styles.reactAgentRow}>
        <Form.Item
          label={"智能体语言"}
          tooltip={"智能体人设文件（SOUL.md、AGENTS.md 等）使用的语言。切换语言后将自动重新复制对应语言的 MD 文件。"}
          className={styles.reactAgentField}
        >
          <Select
            value={language}
            options={LANGUAGE_OPTIONS}
            onChange={onLanguageChange}
            loading={savingLang}
            disabled={savingLang}
            style={{ width: "100%" }}
          />
        </Form.Item>

        <Form.Item
          label={"用户时区"}
          tooltip={"用于定时任务、时间显示和 Agent 上下文，默认使用系统时区。"}
          className={styles.reactAgentField}
        >
          <Select
            showSearch
            value={timezone}
            placeholder={"选择时区"}
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
            options={useTimezoneOptions()}
            onChange={onTimezoneChange}
            loading={savingTimezone}
            disabled={savingTimezone}
            style={{ width: "100%" }}
          />
        </Form.Item>

        <Form.Item
          label={"Shell 命令超时（秒）"}
          name="shell_command_timeout"
          rules={[
            {
              required: true,
              message: "Shell 命令超时为必填项",
            },
            {
              type: "number",
              min: 1,
              message: "Shell 命令超时至少为 1 秒",
            },
          ]}
          tooltip={"execute_shell_command 工具的默认超时时间（秒）。LLM 在单次调用时仍可通过 timeout 参数覆盖此值。适用于编译、数据处理等耗时任务。"}
          className={styles.reactAgentField}
        >
          <InputNumber
            style={{ width: "100%" }}
            min={1}
            step={10}
            placeholder={"请输入超时时间"}
          />
        </Form.Item>

        <Form.Item
          label={"Shell 可执行程序"}
          name="shell_command_executable"
          tooltip={"execute_shell_command 使用的 shell 路径。Linux/macOS：如 /bin/bash、/bin/zsh。Windows：支持 powershell.exe、pwsh.exe 或类 POSIX shell（如 Git Bash）。留空时依次回退到 $SHELL 环境变量，再回退到平台默认值（Unix 为 /bin/sh，Windows 为 cmd.exe）。"}
          className={styles.reactAgentField}
        >
          <Input
            style={{ width: "100%" }}
            placeholder={"例如 /bin/bash 或 powershell.exe（留空 = 自动检测）"}
            allowClear
          />
        </Form.Item>
      </div>

      <Form.Item
        label={"自动生成会话标题"}
        name={["auto_title_config", "enabled"]}
        valuePropName="checked"
        tooltip={"新会话首条用户消息发送后，后台触发一次轻量 LLM 调用，把截断的占位标题替换为更贴切的短标题。每个新会话会多一次 LLM 调用；关闭后保留占位标题、不产生该开销。"}
      >
        <Switch />
      </Form.Item>

      <div className={styles.reactAgentRow}>
        <Form.Item
          label={"上下文管理后端"}
          name="context_manager_backend"
          tooltip={"上下文管理器的后端类型，目前仅支持 Light"}
          className={styles.reactAgentField}
        >
          <Select
            options={CONTEXT_MANAGER_BACKEND_OPTIONS}
            style={{ width: "100%" }}
          />
        </Form.Item>

        <Form.Item
          label={"上下文策略"}
          name={["light_context_config", "strategy"]}
          tooltip={"智能体如何管理长上下文。Scroll（推荐）将驱逐的对话轮次持久化到历史库并按需召回；Native 使用就地压缩。更改后需重启 Minions 生效。"}
          className={styles.reactAgentField}
        >
          <Select
            options={[
              {
                value: "scroll",
                label: "Scroll",
              },
              {
                value: "native",
                label: "Native",
              },
            ]}
            style={{ width: "100%" }}
          />
        </Form.Item>

      </div>
      <Alert
        type="warning"
        showIcon
        message={"切换后端不支持热更新，保存后需要重启 Minions 才能生效"}
        style={{ marginBottom: 16 }}
      />
    </Card>
  );
}
