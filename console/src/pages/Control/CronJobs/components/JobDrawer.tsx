import {
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Button,
  Checkbox,
} from "@agentscope-ai/design";
import { DatePicker, TimePicker } from "antd";
import { useEffect, useMemo, useState } from "react";
import type { FormInstance } from "antd";
import type {
  CronDispatchTargetItem,
  CronJobSpecOutput,
} from "../../../../api/types";
import { DEFAULT_FORM_VALUES } from "./constants";
import { useTimezoneOptions } from "../../../../hooks/useTimezoneOptions";
import styles from "../index.module.less";

type CronJob = CronJobSpecOutput;
type SelectOption = { value: string; label: string };

interface JobDrawerProps {
  open: boolean;
  editingJob: CronJob | null;
  form: FormInstance<CronJob>;
  saving: boolean;
  targetItems: CronDispatchTargetItem[];
  targetChannels: string[];
  targetsLoading: boolean;
  onReloadTargets: () => Promise<void>;
  onClose: () => void;
  onSubmit: (values: CronJob) => void;
}

export function JobDrawer({
  open,
  editingJob,
  form,
  saving,
  targetItems,
  targetChannels,
  targetsLoading,
  onReloadTargets,
  onClose,
  onSubmit,
}: JobDrawerProps) {
    const timezoneOptions = useTimezoneOptions();
  const [saveMsgTouched, setSaveMsgTouched] = useState(false);
  const [channelSearch, setChannelSearch] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [sessionSearch, setSessionSearch] = useState("");
  const selectedChannel = Form.useWatch(["dispatch", "channel"], form);
  const selectedTargetUserId = Form.useWatch(
    ["dispatch", "target", "user_id"],
    form,
  );

  const isEdit = !!editingJob;

  useEffect(() => {
    if (open) {
      setSaveMsgTouched(false);
      setChannelSearch("");
      setUserSearch("");
      setSessionSearch("");
      onReloadTargets().catch((error) =>
        console.error("Failed to reload cron dispatch targets", error),
      );
    }
  }, [open, editingJob?.id, onReloadTargets]);

  const mergeOptions = (
    values: Iterable<string>,
    selectedValue?: string,
    searchValue?: string,
  ): SelectOption[] => {
    const merged = new Set<string>();
    Array.from(values).forEach((value) => {
      if (value?.trim()) {
        merged.add(value.trim());
      }
    });
    if (selectedValue?.trim()) {
      merged.add(selectedValue.trim());
    }
    if (searchValue?.trim()) {
      merged.add(searchValue.trim());
    }
    return [...merged].sort().map((value) => ({ value, label: value }));
  };

  const channelOptions = useMemo(() => {
    return mergeOptions(targetChannels, selectedChannel, channelSearch);
  }, [channelSearch, selectedChannel, targetChannels]);

  const userOptions = useMemo(() => {
    const options = new Set<string>();
    targetItems.forEach((item) => {
      if (!selectedChannel || item.channel === selectedChannel) {
        options.add(item.user_id);
      }
    });
    return mergeOptions(options, selectedTargetUserId, userSearch);
  }, [targetItems, selectedChannel, selectedTargetUserId, userSearch]);

  const sessionOptions = useMemo(() => {
    const options = new Set<string>();
    targetItems.forEach((item) => {
      if (
        (!selectedChannel || item.channel === selectedChannel) &&
        (!selectedTargetUserId || item.user_id === selectedTargetUserId)
      ) {
        options.add(item.session_id);
      }
    });
    const selectedSessionId: string | undefined = form.getFieldValue([
      "dispatch",
      "target",
      "session_id",
    ]);
    return mergeOptions(options, selectedSessionId, sessionSearch);
  }, [form, selectedChannel, selectedTargetUserId, sessionSearch, targetItems]);

  return (
    <Drawer
      width={600}
      placement="right"
      title={editingJob ? "编辑任务" : "创建任务"}
      open={open}
      onClose={onClose}
      destroyOnHidden
      footer={
        <div className={styles.formActions}>
          <Button onClick={onClose}>{"取消"}</Button>
          <Button type="primary" loading={saving} onClick={() => form.submit()}>
            {"保存"}
          </Button>
        </div>
      }
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={onSubmit}
        initialValues={DEFAULT_FORM_VALUES}
      >
        {isEdit && (
          <Form.Item
            name="id"
            label={"任务ID"}
            tooltip={"任务的唯一标识符（UUID）由系统在创建时自动分配，不可修改。"}
          >
            <Input disabled placeholder={"例如：daily-report-job"} />
          </Form.Item>
        )}

        <Form.Item
          name="name"
          label={"任务名称"}
          rules={[{ required: true, message: "请输入任务名称" }]}
          tooltip={"任务的友好名称，便于识别。"}
        >
          <Input placeholder={"例如：每日早报"} />
        </Form.Item>

        <Form.Item
          name="enabled"
          label={"启用状态"}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) =>
            prev.task_type !== cur.task_type ||
            prev.scheduleType !== cur.scheduleType ||
            prev.save_result_to_msg !== cur.save_result_to_msg
          }
        >
          {({ getFieldValue, setFieldValue }) => {
            if (!isEdit && !saveMsgTouched) {
              const taskType = getFieldValue("task_type");
              const scheduleType = getFieldValue("scheduleType");
              const expectedDefault = !(
                taskType === "text" && scheduleType === "cron"
              );
              if (getFieldValue("save_result_to_msg") !== expectedDefault) {
                setFieldValue("save_result_to_msg", expectedDefault);
              }
            }
            return null;
          }}
        </Form.Item>

        <Form.Item
          name="save_result_to_msg"
          label={"运行结果存进消息"}
          valuePropName="checked"
          tooltip={"开启后，任务执行成功且投递成功时，会将结果写入消息；若投递失败，系统会自动兜底写入消息。"}
        >
          <Switch onChange={() => setSaveMsgTouched(true)} />
        </Form.Item>

        <Form.Item
          name="scheduleType"
          label={"调度类型"}
          rules={[
            { required: true, message: "请选择调度类型" },
          ]}
        >
          <Select>
            <Select.Option value="cron">
              {"循环任务"}
            </Select.Option>
            <Select.Option value="once">
              {"日程任务"}
            </Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) => prev.scheduleType !== cur.scheduleType}
        >
          {({ getFieldValue }) =>
            getFieldValue("scheduleType") === "once" ? (
              <>
                <Form.Item
                  name="onceRunAt"
                  label={"执行时间"}
                  rules={[
                    { required: true, message: "请选择执行时间" },
                  ]}
                >
                  <DatePicker
                    showTime={{ format: "HH:mm" }}
                    format="YYYY-MM-DD HH:mm"
                    style={{ width: "100%" }}
                  />
                </Form.Item>
                <Form.Item
                  name="onceRepeatEnabled"
                  label={"重复执行"}
                  valuePropName="checked"
                  tooltip={"从该开始时间按固定天数重复执行"}
                >
                  <Switch />
                </Form.Item>
              </>
            ) : null
          }
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) =>
            prev.scheduleType !== cur.scheduleType ||
            prev.onceRepeatEnabled !== cur.onceRepeatEnabled ||
            prev.onceRepeatEndType !== cur.onceRepeatEndType
          }
        >
          {({ getFieldValue }) => {
            if (
              getFieldValue("scheduleType") !== "once" ||
              !getFieldValue("onceRepeatEnabled")
            ) {
              return null;
            }
            const endType = getFieldValue("onceRepeatEndType") || "never";
            return (
              <>
                <Form.Item label={"重复频率"}>
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 8 }}
                  >
                    <span>{"每"}</span>
                    <Form.Item
                      name="onceRepeatEveryDays"
                      noStyle
                      rules={[
                        {
                          required: true,
                          message: "请输入重复频率（天）",
                        },
                      ]}
                    >
                      <InputNumber min={1} style={{ width: 120 }} />
                    </Form.Item>
                    <span>{"天"}</span>
                  </div>
                </Form.Item>
                <Form.Item
                  name="onceRepeatEndType"
                  label={"结束重复"}
                  rules={[
                    {
                      required: true,
                      message: "请选择结束方式",
                    },
                  ]}
                >
                  <Select>
                    <Select.Option value="never">
                      {"无限重复"}
                    </Select.Option>
                    <Select.Option value="until">
                      {"终止于某天"}
                    </Select.Option>
                    <Select.Option value="count">
                      {"限定次数"}
                    </Select.Option>
                  </Select>
                </Form.Item>
                {endType === "until" && (
                  <Form.Item
                    name="onceRepeatUntil"
                    label={"截止时间"}
                    rules={[
                      {
                        required: true,
                        message: "请选择截止时间",
                      },
                    ]}
                  >
                    <DatePicker
                      showTime={{ format: "HH:mm" }}
                      format="YYYY-MM-DD HH:mm"
                      style={{ width: "100%" }}
                    />
                  </Form.Item>
                )}
                {endType === "count" && (
                  <Form.Item
                    name="onceRepeatCount"
                    label={"执行次数"}
                    rules={[
                      {
                        required: true,
                        message: "请输入执行次数",
                      },
                    ]}
                  >
                    <InputNumber min={1} style={{ width: "100%" }} />
                  </Form.Item>
                )}
              </>
            );
          }}
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) =>
            prev.scheduleType !== cur.scheduleType ||
            prev.cronType !== cur.cronType
          }
        >
          {({ getFieldValue }) => {
            if (getFieldValue("scheduleType") !== "cron") {
              return null;
            }
            const cronType = getFieldValue("cronType");
            return (
              <>
                <Form.Item
                  label={"执行时间（Cron）"}
                  required
                  tooltip={"定义任务执行时间"}
                >
                  <Form.Item name="cronType" noStyle>
                    <Select>
                      <Select.Option value="hourly">
                        {"每小时"}
                      </Select.Option>
                      <Select.Option value="daily">
                        {"每天"}
                      </Select.Option>
                      <Select.Option value="weekly">
                        {"每周"}
                      </Select.Option>
                      <Select.Option value="custom">
                        {"自定义"}
                      </Select.Option>
                    </Select>
                  </Form.Item>
                </Form.Item>
                {(cronType === "daily" || cronType === "weekly") && (
                  <Form.Item
                    name="cronTime"
                    label={"执行时间"}
                    rules={[{ required: true }]}
                  >
                    <TimePicker
                      format="HH:mm"
                      minuteStep={15}
                      needConfirm={false}
                      style={{ width: "100%" }}
                    />
                  </Form.Item>
                )}
              </>
            );
          }}
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) =>
            prev.scheduleType !== cur.scheduleType ||
            prev.cronType !== cur.cronType
          }
        >
          {({ getFieldValue }) => {
            if (getFieldValue("scheduleType") !== "cron") {
              return null;
            }
            const cronType = getFieldValue("cronType");
            if (cronType === "weekly") {
              return (
                <Form.Item
                  name="cronDaysOfWeek"
                  label={"星期"}
                  rules={[{ required: true, message: "请选择至少一天" }]}
                >
                  <Checkbox.Group
                    options={[
                      { label: "周一", value: "mon" },
                      { label: "周二", value: "tue" },
                      { label: "周三", value: "wed" },
                      { label: "周四", value: "thu" },
                      { label: "周五", value: "fri" },
                      { label: "周六", value: "sat" },
                      { label: "周日", value: "sun" },
                    ]}
                  />
                </Form.Item>
              );
            }
            return null;
          }}
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) =>
            prev.scheduleType !== cur.scheduleType ||
            prev.cronType !== cur.cronType
          }
        >
          {({ getFieldValue }) => {
            if (getFieldValue("scheduleType") !== "cron") {
              return null;
            }
            const cronType = getFieldValue("cronType");

            if (cronType === "custom") {
              return (
                <Form.Item
                  name="cronCustom"
                  label={"Cron 表达式"}
                  rules={[
                    { required: true, message: "请输入Cron表达式" },
                  ]}
                  extra={
                    <div className={styles.formExtraText}>
                      <div style={{ marginBottom: 4 }}>
                        {"常用示例：'0 9 * * *' = 每天9点 | '*/30 * * * *' = 每30分钟 | '0 */2 * * *' = 每2小时 | '0 0 * * 0' = 每周日0点"}
                      </div>
                      <div>
                        {"不熟悉 Cron 表达式？"}{" "}
                        <a
                          href="https://crontab.guru/"
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.formHelperLink}
                        >
                          {"使用在线工具生成"} →
                        </a>
                      </div>
                    </div>
                  }
                >
                  <Input placeholder="0 9 * * *" />
                </Form.Item>
              );
            }
            return null;
          }}
        </Form.Item>

        <Form.Item name={["schedule", "cron"]} hidden>
          <Input />
        </Form.Item>

        <Form.Item
          name={["schedule", "timezone"]}
          label={"时区"}
          tooltip={"Cron 计划使用的时区。默认：UTC"}
        >
          <Select
            showSearch
            placeholder={"选择时区"}
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
            options={timezoneOptions}
          />
        </Form.Item>

        <Form.Item
          name="task_type"
          label={"任务类型"}
          rules={[
            { required: true, message: "请选择任务类型" },
          ]}
          tooltip={"选择 'text' 用于简单消息任务，选择 'agent' 用于复杂的智能体工作流。"}
        >
          <Select>
            <Select.Option value="text">text</Select.Option>
            <Select.Option value="agent">agent</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          noStyle
          shouldUpdate={(prev, cur) => prev.task_type !== cur.task_type}
        >
          {({ getFieldValue }) => {
            const taskType = getFieldValue("task_type");
            const textRequired = taskType === "text";
            const agentRequired = taskType === "agent";

            return (
              <>
                <Form.Item
                  name="text"
                  label={"消息内容"}
                  required={textRequired}
                  rules={
                    textRequired
                      ? [
                          {
                            required: true,
                            message: "请输入消息内容",
                          },
                        ]
                      : []
                  }
                  tooltip={"简单消息任务：此处为实际的消息正文，任务类型为'text'时必填。"}
                >
                  <Input.TextArea
                    rows={3}
                    placeholder={"简单消息任务时填写实际发送的正文..."}
                  />
                </Form.Item>

                <Form.Item
                  name={["request", "input"]}
                  label={"请求内容"}
                  required={agentRequired}
                  rules={[
                    ...(agentRequired
                      ? [
                          {
                            required: true,
                            message: "请输入请求内容",
                          },
                        ]
                      : []),
                    {
                      validator: (_, value) => {
                        if (!value) return Promise.resolve();
                        try {
                          JSON.parse(value);
                          return Promise.resolve();
                        } catch {
                          return Promise.reject(
                            new Error("JSON格式无效"),
                          );
                        }
                      },
                    },
                  ]}
                  tooltip={"JSON 格式的消息内容。这是智能体将接收和处理的内容，任务类型为'agent'时必填。"}
                  extra={
                    <span className={styles.formExtraText}>
                      {"格式：[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"您的消息内容\"}]}]"}
                    </span>
                  }
                >
                  <Input.TextArea
                    rows={6}
                    placeholder='[{"role":"user","content":[{"text":"Hello","type":"text"}]}]'
                    style={{ fontFamily: "monospace", fontSize: 12 }}
                  />
                </Form.Item>
              </>
            );
          }}
        </Form.Item>

        <Form.Item name={["dispatch", "type"]} label="DispatchType" hidden>
          <Input disabled value="channel" />
        </Form.Item>

        <Form.Item
          name={["dispatch", "channel"]}
          label={"目标频道"}
          rules={[
            { required: true, message: "请输入目标频道" },
          ]}
          tooltip={"响应将发送到的目标频道（例如：'console'、'discord'、'imessage'）。"}
        >
          <Select
            showSearch
            loading={targetsLoading}
            placeholder="console"
            options={channelOptions}
            onSearch={setChannelSearch}
            onBlur={() => setChannelSearch("")}
            notFoundContent="输入自定义值后按 Enter"
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item
          name={["dispatch", "target", "user_id"]}
          label={"目标用户ID"}
          rules={[{ required: true, message: "请输入目标用户ID" }]}
          tooltip={"在目标频道中接收响应的用户ID。"}
        >
          <Select
            showSearch
            loading={targetsLoading}
            placeholder="admin"
            options={userOptions}
            onSearch={setUserSearch}
            onBlur={() => setUserSearch("")}
            notFoundContent="输入自定义值后按 Enter"
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item
          name={["dispatch", "target", "session_id"]}
          label={"目标会话ID"}
          rules={[
            { required: true, message: "请输入目标会话ID" },
          ]}
          tooltip={"在目标频道中传递响应的会话ID。"}
        >
          <Select
            showSearch
            loading={targetsLoading}
            placeholder="default"
            options={sessionOptions}
            onSearch={setSessionSearch}
            onBlur={() => setSessionSearch("")}
            notFoundContent="输入自定义值后按 Enter"
            filterOption={(input, option) =>
              (option?.label?.toString() || "")
                .toLowerCase()
                .includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Form.Item
          name={["dispatch", "mode"]}
          label={"分发模式"}
          tooltip={"选择 'stream' 获取实时响应，或选择 'final' 仅获取完整响应。"}
        >
          <Select>
            <Select.Option value="stream">stream</Select.Option>
            <Select.Option value="final">final</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item
          name={["runtime", "share_session"]}
          label={"共用会话"}
          valuePropName="checked"
          tooltip={"开启时，与目标用户共用会话。关闭时，每次运行创建独立的会话上下文，互不影响。适用于不需要记忆历史的独立任务。默认：开启"}
        >
          <Switch defaultChecked />
        </Form.Item>

        <Form.Item
          name={["runtime", "tool_safety"]}
          label={"工具执行安全检查"}
          valuePropName="checked"
          tooltip={"开启时，高风险工具调用需要用户审批（可能阻塞无人值守的定时任务）。关闭时，所有工具调用直接执行，不弹审批窗口，适用于可信的自动化任务。默认：关闭"}
        >
          <Switch />
        </Form.Item>

        <Form.Item
          name={["runtime", "max_concurrency"]}
          label={"最大并发数"}
          tooltip={"此任务可以同时运行的最大数量。默认：1"}
        >
          <InputNumber min={1} style={{ width: "100%" }} placeholder="1" />
        </Form.Item>

        <Form.Item
          name={["runtime", "timeout_seconds"]}
          label={"超时时间（秒）"}
          tooltip={"最大执行时间（秒）。超时将终止任务。"}
        >
          <InputNumber min={1} style={{ width: "100%" }} placeholder="300" />
        </Form.Item>

        <Form.Item
          name={["runtime", "misfire_grace_seconds"]}
          label={"错过执行宽限期（秒）"}
          tooltip={"错过执行的宽限期。如果任务错过计划时间超过此时长，将不会执行。"}
        >
          <InputNumber min={0} style={{ width: "100%" }} placeholder="600" />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
