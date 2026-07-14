import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  InputNumber,
  Select,
  Switch,
} from "@agentscope-ai/design";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { TimePicker } from "antd";
import dayjs from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import api from "../../../api";
import { useAgentStore } from "../../../stores/agentStore";
import type { HeartbeatConfig } from "../../../api/types/heartbeat";
import { parseEvery, serializeEvery, type EveryUnit } from "./parseEvery";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

dayjs.extend(customParseFormat);

const TIME_FORMAT = "HH:mm";
const HEARTBEAT_MAX_TIMEOUT_SECONDS = 3600;

/** TimePicker that uses "HH:mm" string as value for Form. */
function TimePickerHHmm({
  value,
  onChange,
}: {
  value?: string | null;
  onChange?: (s: string) => void;
}) {
  const strVal =
    typeof value === "string" ? value : Array.isArray(value) ? value[0] : null;
  return (
    <TimePicker
      format={TIME_FORMAT}
      value={strVal ? dayjs(strVal, TIME_FORMAT) : null}
      onChange={(_, str) => {
        const s = typeof str === "string" ? str : str?.[0];
        if (s) onChange?.(s);
      }}
      minuteStep={15}
      needConfirm={false}
      style={{ width: "100%" }}
    />
  );
}

/** Form values: API shape plus flattened fields for interval and time. */
type HeartbeatFormValues = Omit<HeartbeatConfig, "every"> & {
  every?: string;
  everyNumber?: number;
  everyUnit?: EveryUnit;
  useActiveHours?: boolean;
  activeHoursStart?: string;
  activeHoursEnd?: string;
};

const TARGET_OPTIONS = [
  { value: "main", label: "静默运行（默认，不发送到频道）" },
  { value: "last", label: "发到上次对话频道" },
  { value: "msg", label: "发送到消息" },
];

const EVERY_UNIT_OPTIONS: { value: EveryUnit; label: string }[] = [
  { value: "m", label: "分钟" },
  { value: "h", label: "小时" },
];

function HeartbeatPage() {
    const { selectedAgent } = useAgentStore();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<HeartbeatFormValues>();
  const { message } = useAppMessage();

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const data = await api.getHeartbeatConfig();
      const everyParts = parseEvery(data.every ?? "6h");
      form.setFieldsValue({
        enabled: data.enabled ?? false,
        everyNumber: everyParts.number,
        everyUnit: everyParts.unit,
        target: data.target ?? "main",
        timeoutSeconds: data.timeoutSeconds ?? 300,
        useActiveHours: !!data.activeHours,
        activeHoursStart: data.activeHours?.start ?? "08:00",
        activeHoursEnd: data.activeHours?.end ?? "22:00",
      });
    } catch (e) {
      console.error("Failed to load heartbeat config:", e);
      message.error("加载心跳配置失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAgent]);

  const onFinish = async (values: HeartbeatFormValues) => {
    const every =
      values.everyNumber != null && values.everyUnit
        ? serializeEvery({
            number: values.everyNumber,
            unit: values.everyUnit,
          })
        : "6h";
    const body: HeartbeatConfig = {
      enabled: values.enabled ?? false,
      every,
      target: values.target ?? "main",
      timeoutSeconds: values.timeoutSeconds ?? 300,
      activeHours:
        values.useActiveHours &&
        values.activeHoursStart &&
        values.activeHoursEnd
          ? {
              start: values.activeHoursStart,
              end: values.activeHoursEnd,
            }
          : undefined,
    };
    setSaving(true);
    try {
      await api.updateHeartbeatConfig(body);
      message.success("保存成功，心跳已热重载");
    } catch (e) {
      console.error("Failed to save heartbeat config:", e);
      message.error("保存心跳配置失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.heartbeatPage}>
        <PageHeader
          items={[{ title: "控制" }, { title: "心跳" }]}
        />
        <span className={styles.description}>{"加载中..."}</span>
      </div>
    );
  }

  return (
    <div className={styles.heartbeatPage}>
      <PageHeader
        items={[{ title: "控制" }, { title: "心跳" }]}
      />
      <div className={styles.heartbeatContent}>
        <Card className={styles.card}>
          <Form
            form={form}
            layout="vertical"
            onFinish={onFinish}
            initialValues={{
              enabled: false,
              everyNumber: 6,
              everyUnit: "h",
              target: "main",
              timeoutSeconds: 300,
              useActiveHours: false,
              activeHoursStart: "08:00",
              activeHoursEnd: "22:00",
            }}
          >
            <Form.Item
              name="enabled"
              label={"开启心跳"}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>

            <Form.Item
              label={"执行间隔"}
              required
              className={styles.everyField}
            >
              <div className={styles.everyRow}>
                <Form.Item
                  name="everyNumber"
                  rules={[
                    { required: true, message: "请填写间隔" },
                    {
                      type: "number",
                      min: 1,
                      message: "间隔至少为 1",
                    },
                  ]}
                  noStyle
                >
                  <InputNumber min={1} className={styles.everyNumber} />
                </Form.Item>
                <Form.Item name="everyUnit" noStyle>
                  <Select
                    options={EVERY_UNIT_OPTIONS.map((opt) => ({
                      value: opt.value,
                      label: opt.label,
                    }))}
                    className={styles.everyUnit}
                  />
                </Form.Item>
              </div>
            </Form.Item>

            <Form.Item
              name="timeoutSeconds"
              label={"执行超时（秒）"}
              rules={[
                {
                  required: true,
                  message: "请填写执行超时",
                },
                {
                  type: "number",
                  min: 1,
                  message: "执行超时至少为 1",
                },
                {
                  type: "number",
                  max: HEARTBEAT_MAX_TIMEOUT_SECONDS,
                  message: "执行超时最多为 3600",
                },
              ]}
            >
              <InputNumber
                min={1}
                max={HEARTBEAT_MAX_TIMEOUT_SECONDS}
                className={styles.timeoutNumber}
              />
            </Form.Item>

            <Form.Item
              name="target"
              label={"回复目标"}
              rules={[{ required: true }]}
            >
              <Select
                options={TARGET_OPTIONS.map((opt) => ({
                  value: opt.value,
                  label: opt.label,
                }))}
              />
            </Form.Item>

            <Form.Item
              name="useActiveHours"
              label={"活跃时段（可选）"}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>

            <Form.Item
              noStyle
              shouldUpdate={(prev, cur) =>
                prev.useActiveHours !== cur.useActiveHours
              }
            >
              {({ getFieldValue }) =>
                getFieldValue("useActiveHours") ? (
                  <div className={styles.activeHoursRow}>
                    <Form.Item
                      name="activeHoursStart"
                      label={"开始时间"}
                    >
                      <TimePickerHHmm />
                    </Form.Item>
                    <Form.Item
                      name="activeHoursEnd"
                      label={"结束时间"}
                    >
                      <TimePickerHHmm />
                    </Form.Item>
                  </div>
                ) : null
              }
            </Form.Item>

            <Form.Item className={styles.formActions}>
              <Button type="primary" htmlType="submit" loading={saving}>
                {"保存"}
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  );
}

export default HeartbeatPage;
