import { Card, Form, InputNumber, Switch } from "@agentscope-ai/design";
import styles from "../index.module.less";

interface LlmRetryCardProps {
  llmRetryEnabled?: boolean;
}

export function LlmRetryCard({ llmRetryEnabled = true }: LlmRetryCardProps) {
    const form = Form.useFormInstance();

  return (
    <Card className={styles.formCard} title={"LLM 自动重试"}>
      <Form.Item
        name="llm_retry_enabled"
        label={"启用自动重试"}
        valuePropName="checked"
        tooltip={"对限流、超时、连接中断等瞬时 LLM API 错误自动重试。保存后对新的请求生效。"}
      >
        <Switch />
      </Form.Item>

      <div className={styles.llmRetryRow}>
        <Form.Item
          label={"最大重试次数"}
          name="llm_max_retries"
          rules={[
            {
              required: true,
              message: "最大重试次数为必填项",
            },
            {
              type: "number",
              min: 1,
              message: "最大重试次数必须大于等于 1",
            },
          ]}
          tooltip={"单次 LLM 请求在遇到可重试错误时，最多额外重试多少次。"}
          className={styles.llmRetryField}
        >
          <InputNumber
            style={{ width: "100%" }}
            min={1}
            step={1}
            disabled={!llmRetryEnabled}
            placeholder={"请输入最大重试次数"}
          />
        </Form.Item>

        <Form.Item
          label={"退避基础延迟（秒）"}
          name="llm_backoff_base"
          rules={[
            {
              required: true,
              message: "退避基础延迟为必填项",
            },
            {
              type: "number",
              min: 0.1,
              message: "退避基础延迟必须大于等于 0.1 秒",
            },
          ]}
          tooltip={"第一次重试前的基础等待时间，后续会按指数退避增长。"}
          className={styles.llmRetryField}
        >
          <InputNumber
            style={{ width: "100%" }}
            step={0.1}
            disabled={!llmRetryEnabled}
            placeholder={"请输入基础延迟"}
          />
        </Form.Item>

        <Form.Item
          label={"退避最大延迟（秒）"}
          name="llm_backoff_cap"
          dependencies={["llm_backoff_base"]}
          rules={[
            {
              required: true,
              message: "退避最大延迟为必填项",
            },
            {
              type: "number",
              min: 0.5,
              message: "退避最大延迟必须大于等于 0.5 秒",
            },
            {
              validator: async (_, value) => {
                const backoffBase = form.getFieldValue("llm_backoff_base");
                if (
                  typeof value !== "number" ||
                  typeof backoffBase !== "number" ||
                  value >= backoffBase
                ) {
                  return;
                }
                throw new Error("退避最大延迟必须大于等于基础延迟");
              },
            },
          ]}
          tooltip={"指数退避的最大等待上限，避免重试间隔无限增大。"}
          className={styles.llmRetryField}
        >
          <InputNumber
            style={{ width: "100%" }}
            step={0.5}
            disabled={!llmRetryEnabled}
            placeholder={"请输入最大延迟"}
          />
        </Form.Item>
      </div>
    </Card>
  );
}
