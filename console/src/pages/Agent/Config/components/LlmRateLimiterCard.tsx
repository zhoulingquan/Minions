import { Card, Form, InputNumber } from "@agentscope-ai/design";
import styles from "../index.module.less";

const RL_PAUSE_FIELD = "llm_rate_limit_pause";
const RL_JITTER_FIELD = "llm_rate_limit_jitter";
const RL_MAX_QPM_FIELD = "llm_max_qpm";

export function LlmRateLimiterCard() {
    const form = Form.useFormInstance();

  return (
    <Card
      className={styles.formCard}
      title={"LLM 并发限流"}
    >
      <Form.Item
        label={"最大并发请求数"}
        name="llm_max_concurrent"
        rules={[
          {
            required: true,
            message: "最大并发请求数为必填项",
          },
          {
            type: "number",
            min: 1,
            message: "最大并发请求数必须大于等于 1",
          },
        ]}
        tooltip={"允许同时发出的 LLM 请求上限，所有 Agent 共享。仅首次初始化时生效，修改后需重启服务。"}
      >
        <InputNumber
          style={{ width: "100%" }}
          min={1}
          step={1}
          placeholder={"请输入最大并发数"}
        />
      </Form.Item>

      <Form.Item
        label={"每分钟最大请求数（QPM）"}
        name={RL_MAX_QPM_FIELD}
        rules={[
          {
            required: true,
            message: "每分钟最大请求数为必填项",
          },
          {
            type: "number",
            min: 0,
            message: "每分钟最大请求数必须大于等于 0",
          },
        ]}
        tooltip={"60 秒滑动窗口内允许的最大请求数。超出上限的请求在发送前会等待，从源头预防 429 限流。0 表示不限制。"}
      >
        <InputNumber
          style={{ width: "100%" }}
          min={0}
          step={10}
          placeholder={"请输入每分钟最大请求数（0 = 不限制）"}
        />
      </Form.Item>

      <Form.Item
        label={"限流暂停时长（秒）"}
        name="llm_rate_limit_pause"
        rules={[
          {
            required: true,
            message: "限流暂停时长为必填项",
          },
          {
            type: "number",
            min: 1.0,
            message: "限流暂停时长必须大于等于 1 秒",
          },
        ]}
        tooltip={"收到 429 限流响应时全局暂停的默认时长（秒）。若 API 返回 Retry-After 头，则以其为准。"}
      >
        <InputNumber
          style={{ width: "100%" }}
          step={0.5}
          placeholder={"请输入暂停时长"}
        />
      </Form.Item>

      <Form.Item
        label={"抖动范围（秒）"}
        name="llm_rate_limit_jitter"
        rules={[
          {
            required: true,
            message: "抖动范围为必填项",
          },
          {
            type: "number",
            min: 0.0,
            message: "抖动范围必须大于等于 0 秒",
          },
        ]}
        tooltip={"在暂停时长基础上叠加的随机抖动范围（秒），使并发等待者错开唤醒时间，避免新的请求突刺。"}
      >
        <InputNumber
          style={{ width: "100%" }}
          step={0.5}
          placeholder={"请输入抖动范围"}
        />
      </Form.Item>

      <Form.Item
        label={"槽位获取超时（秒）"}
        name="llm_acquire_timeout"
        dependencies={[RL_PAUSE_FIELD, RL_JITTER_FIELD]}
        rules={[
          {
            required: true,
            message: "槽位获取超时为必填项",
          },
          {
            type: "number",
            min: 10.0,
            message: "槽位获取超时必须大于等于 10 秒",
          },
          {
            validator: async (_, value) => {
              const pause = form.getFieldValue(RL_PAUSE_FIELD);
              const jitter = form.getFieldValue(RL_JITTER_FIELD);
              if (
                typeof value !== "number" ||
                typeof pause !== "number" ||
                typeof jitter !== "number" ||
                value > pause + jitter
              ) {
                return;
              }
              throw new Error("槽位获取超时必须大于限流暂停时长与抖动范围之和");
            },
          },
        ]}
        tooltip={"等待获取限流槽位的最长时间（秒），超时后将抛出错误而非无限等待。"}
      >
        <InputNumber
          style={{ width: "100%" }}
          step={10}
          placeholder={"请输入超时时间"}
        />
      </Form.Item>
    </Card>
  );
}
