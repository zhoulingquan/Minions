import { useState } from "react";
import {
  Alert,
  Card,
  Form,
  InputNumber,
  Select,
  Switch,
  Input,
  Button,
  Tabs,
  Tag,
} from "@agentscope-ai/design";
import {
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  Repeat,
  Shield,
  CheckCircle,
  Info,
  Target,
  Rocket,
  Gauge,
  Wallet,
  Lock,
} from "lucide-react";
import styles from "../index.module.less";

const ACTION_OPTIONS = [
  { value: "modify_prompt", label: "Send Reminder" },
  { value: "stop", label: "Pause & Ask for Help" },
];

function SectionHeader({
  icon,
  title,
}: {
  icon: React.ReactNode;
  title: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 16,
        paddingBottom: 8,
        borderBottom: "1px solid var(--border-color, #f0f0f0)",
      }}
    >
      {icon}
      <span style={{ fontWeight: 600, fontSize: 14 }}>{title}</span>
    </div>
  );
}

function SectionDivider() {
  return (
    <hr
      style={{
        border: "none",
        borderTop: "1px solid var(--border-color, #f0f0f0)",
        margin: "24px 0",
      }}
    />
  );
}

function MockGateCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
    return (
    <div
      style={{
        border: "1px solid var(--border-color, #f0f0f0)",
        borderRadius: 8,
        padding: "16px 20px",
        marginBottom: 12,
        opacity: 0.6,
        position: "relative",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {icon}
          <span style={{ fontWeight: 500, fontSize: 13 }}>{title}</span>
        </div>
        <Tag
          style={{
            fontSize: 11,
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <Lock size={10} />
          {"即将推出"}
        </Tag>
      </div>
      <p
        style={{
          margin: "8px 0 0",
          fontSize: 12,
          color: "var(--text-secondary, rgba(0,0,0,0.45))",
        }}
      >
        {description}
      </p>
      <p
        style={{
          margin: "6px 0 0",
          fontSize: 11,
          color: "var(--text-quaternary, rgba(0,0,0,0.25))",
          fontStyle: "italic",
        }}
      >
        {"自定义配置将在未来版本中开放。"}
      </p>
    </div>
  );
}

function IterationSection() {
    const form = Form.useFormInstance();
  const enabled = Form.useWatch(["loop", "iteration", "enabled"], form);

  return (
    <div>
      <SectionHeader
        icon={<Repeat size={16} style={{ opacity: 0.7 }} />}
        title={"迭代限制"}
      />
      <Form.Item
        name={["loop", "iteration", "enabled"]}
        label={"启用迭代限制"}
        valuePropName="checked"
        tooltip={"在固定轮次后停止 Agent 循环"}
      >
        <Switch />
      </Form.Item>
      {enabled && (
        <Form.Item
          name={["loop", "iteration", "max_iterations"]}
          label={"最大迭代次数"}
          tooltip={"循环执行的最大轮次"}
        >
          <InputNumber min={1} max={500} style={{ width: 200 }} />
        </Form.Item>
      )}
    </div>
  );
}

function DoomLoopSection() {
    const form = Form.useFormInstance();
  const [advanced, setAdvanced] = useState(false);
  const enabled = Form.useWatch(["loop", "doom_loop", "enabled"], form);
  const stages = Form.useWatch(["loop", "doom_loop", "stages"], form) || [];

  return (
    <div>
      <SectionHeader
        icon={<Shield size={16} style={{ opacity: 0.7 }} />}
        title={"重复行为保护"}
      />
      <Form.Item
        name={["loop", "doom_loop", "enabled"]}
        label={"重复行为保护"}
        valuePropName="checked"
        tooltip={"当 Agent 陷入重复相同操作时自动介入"}
      >
        <Switch />
      </Form.Item>

      {enabled && (
        <>
          {!advanced && (
            <div style={{ marginBottom: 16 }}>
              {stages.map(
                (
                  stage: {
                    after: number;
                    action: string;
                    prompt: string;
                  },
                  idx: number,
                ) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 8,
                    }}
                  >
                    <span
                      style={{
                        color: "var(--text-secondary)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {"连续重复"}{" "}
                      <strong>{stage.after}</strong>{" "}
                      {"次相同操作后"}{" "}
                      →
                    </span>
                    <span>
                      {stage.action === "stop"
                        ? "暂停并等待确认"
                        : "发送提醒"}
                    </span>
                  </div>
                ),
              )}
            </div>
          )}

          <Button
            type="link"
            size="small"
            onClick={() => setAdvanced(!advanced)}
            style={{ padding: 0, marginBottom: 16 }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {advanced ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
              {advanced
                ? "简单"
                : "高级"}
            </span>
          </Button>

          {advanced && (
            <>
              <div className={styles.reactAgentRow}>
                <Form.Item
                  name={["loop", "doom_loop", "window_size"]}
                  label={"检测范围"}
                  tooltip={"检查最近多少次操作是否重复"}
                  className={styles.reactAgentField}
                >
                  <InputNumber min={2} max={20} style={{ width: "100%" }} />
                </Form.Item>

                <Form.Item
                  name={["loop", "doom_loop", "similarity_threshold"]}
                  label={"匹配灵敏度"}
                  tooltip={"操作相似度超过此值视为重复（越低越严格）"}
                  className={styles.reactAgentField}
                >
                  <InputNumber
                    min={0}
                    max={1}
                    step={0.05}
                    style={{ width: "100%" }}
                  />
                </Form.Item>
              </div>

              <hr
                style={{
                  border: "none",
                  borderTop: "1px solid var(--border-color)",
                  margin: "12px 0",
                }}
              />
              <strong style={{ display: "block", marginBottom: 12 }}>
                {"干预规则"}
              </strong>

              <Form.List name={["loop", "doom_loop", "stages"]}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...rest }) => (
                      <div
                        key={key}
                        style={{
                          display: "flex",
                          gap: 8,
                          marginBottom: 12,
                          alignItems: "flex-start",
                        }}
                      >
                        <Form.Item
                          {...rest}
                          name={[name, "after"]}
                          label={
                            name === 0
                              ? "连续重复"
                              : undefined
                          }
                          rules={[{ required: true }]}
                          style={{ flex: 1 }}
                        >
                          <InputNumber
                            min={1}
                            placeholder="N"
                            style={{ width: "100%" }}
                          />
                        </Form.Item>

                        <Form.Item
                          {...rest}
                          name={[name, "action"]}
                          label={
                            name === 0
                              ? "动作"
                              : undefined
                          }
                          rules={[{ required: true }]}
                          style={{ flex: 1.5 }}
                        >
                          <Select options={ACTION_OPTIONS} />
                        </Form.Item>

                        <Form.Item
                          {...rest}
                          name={[name, "prompt"]}
                          label={
                            name === 0
                              ? "提示语"
                              : undefined
                          }
                          style={{ flex: 3 }}
                        >
                          <Input.TextArea
                            rows={1}
                            autoSize={{ minRows: 1, maxRows: 3 }}
                            placeholder={"提醒内容或暂停原因..."}
                          />
                        </Form.Item>

                        <Button
                          type="text"
                          danger
                          icon={<Trash2 size={14} />}
                          onClick={() => remove(name)}
                          style={{ marginTop: name === 0 ? 30 : 0 }}
                        />
                      </div>
                    ))}
                    <Button
                      type="dashed"
                      onClick={() =>
                        add({
                          after: (stages.length + 1) * 3,
                          action: "modify_prompt",
                          prompt: "",
                        })
                      }
                      icon={<Plus size={14} />}
                      style={{ width: "100%" }}
                    >
                      {"添加规则"}
                    </Button>
                  </>
                )}
              </Form.List>
            </>
          )}
        </>
      )}
    </div>
  );
}

function RubricSection() {
    const form = Form.useFormInstance();
  const [advanced, setAdvanced] = useState(false);
  const enabled = Form.useWatch(["loop", "rubric", "enabled"], form);

  return (
    <div>
      <SectionHeader
        icon={<CheckCircle size={16} style={{ opacity: 0.7 }} />}
        title={"完成度检查"}
      />
      <p
        style={{
          fontSize: 12,
          color: "var(--text-secondary, rgba(0,0,0,0.45))",
          marginBottom: 12,
          lineHeight: 1.6,
        }}
      >
        {"部分大模型可能仅输出文本而不调用任何工具，导致 Agent 提前停止。启用后会重新提示 Agent 继续完成任务。"}
      </p>
      <Form.Item
        name={["loop", "rubric", "enabled"]}
        label={"启用完成度检查"}
        valuePropName="checked"
        tooltip={"每轮结束后让 Agent 自评任务是否完成"}
      >
        <Switch />
      </Form.Item>
      {enabled && (
        <>
          <Form.Item
            name={["loop", "rubric", "prompt"]}
            label={"检查提示语"}
            tooltip={"注入的提示语，要求 Agent 评估任务完成情况"}
          >
            <Input.TextArea
              autoSize={{ minRows: 2, maxRows: 5 }}
              placeholder={"你上一轮没有调用任何工具。如果任务已完成请确认，否则请继续使用工具完成。"}
            />
          </Form.Item>

          <Button
            type="link"
            size="small"
            onClick={() => setAdvanced(!advanced)}
            style={{ padding: 0, marginBottom: 12 }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              {advanced ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
              {advanced
                ? "简单"
                : "高级"}
            </span>
          </Button>

          {advanced && (
            <Form.Item
              name={["loop", "rubric", "max_interventions"]}
              label={"每轮最大介入次数"}
              tooltip={"每轮最多重新提示的次数，防止 LLM 持续输出纯文本导致无限循环。"}
            >
              <InputNumber min={1} max={10} style={{ width: 200 }} />
            </Form.Item>
          )}
        </>
      )}
    </div>
  );
}

function ReactTab() {
  return (
    <>
      <IterationSection />
      <SectionDivider />
      <DoomLoopSection />
      <SectionDivider />
      <RubricSection />
    </>
  );
}

function GoalModeTab() {
    return (
    <div>
      <Alert
        type="info"
        showIcon
        icon={<Info size={14} />}
        message={"Goal模式 vs 默认模式"}
        description={"默认模式在产生回复后即停止。Goal模式让 Agent 围绕目标持续循环执行，通过 Rubric 评估自动判断是否完成，未完成则继续推进。所有操作在当前 Agent 上下文中进行。"}
        style={{ marginBottom: 16 }}
      />
      <MockGateCard
        icon={<Repeat size={14} style={{ opacity: 0.5 }} />}
        title={"目标迭代 Gate"}
        description={"限制目标会话中的 Agent 执行轮次，跟踪迭代次数和 Token 使用量。"}
      />
      <MockGateCard
        icon={<Wallet size={14} style={{ opacity: 0.5 }} />}
        title={"Token 预算 Gate"}
        description={"为目标会话设置 Token 消耗上限，超出预算时停止 Agent。"}
      />
      <MockGateCard
        icon={<CheckCircle size={14} style={{ opacity: 0.5 }} />}
        title={"目标完成度评估"}
        description={"通过检查会话状态评估目标是否已完成。"}
      />
      <MockGateCard
        icon={<Shield size={14} style={{ opacity: 0.5 }} />}
        title={"重复行为保护"}
        description={"在目标执行过程中检测重复模式并触发干预。"}
      />
    </div>
  );
}

function MissionModeTab() {
    return (
    <div>
      <Alert
        type="info"
        showIcon
        icon={<Info size={14} />}
        message={"Mission模式 vs Goal模式"}
        description={"Mission模式将复杂任务自动分解为子任务，由 Worker 子Agent独立执行，Verifier 子Agent验证结果。每个子任务有独立上下文，不会污染主会话历史。适合需要长时间、多步骤协作的复杂工程任务。"}
        style={{ marginBottom: 16 }}
      />
      <MockGateCard
        icon={<Gauge size={14} style={{ opacity: 0.5 }} />}
        title={"任务进度 Gate"}
        description={"跟踪 PRD 用户故事的完成情况，直到所有故事通过或达到最大迭代次数。"}
      />
      <MockGateCard
        icon={<Repeat size={14} style={{ opacity: 0.5 }} />}
        title={"迭代绕行"}
        description={"在任务执行期间临时取消 ReAct 迭代限制，允许长时间运行的阶段。"}
      />
    </div>
  );
}

export function AgentLoopCard() {
  const tabItems = [
    {
      key: "react",
      label: (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Repeat size={13} />
          {"Loop模板 - 默认"}
        </span>
      ),
      children: <ReactTab />,
    },
    {
      key: "goal",
      label: (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Target size={13} />
          {"Loop模板 - Goal模式"}
        </span>
      ),
      children: <GoalModeTab />,
    },
    {
      key: "mission",
      label: (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Rocket size={13} />
          {"Loop模板 - Mission模式"}
        </span>
      ),
      children: <MissionModeTab />,
    },
    {
      key: "add",
      label: (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            color: "var(--text-quaternary, rgba(0,0,0,0.25))",
          }}
        >
          <Plus size={13} />
        </span>
      ),
      children: (
        <div
          style={{
            textAlign: "center",
            padding: "40px 0",
            color: "var(--text-secondary, rgba(0,0,0,0.45))",
          }}
        >
          <Plus size={32} style={{ opacity: 0.3, marginBottom: 12 }} />
          <p style={{ fontSize: 14, fontWeight: 500 }}>
            {"自定义循环模式"}
          </p>
          <p style={{ fontSize: 12 }}>
            {"使用自定义 Gate 组合创建您自己的循环模式，即将推出。"}
          </p>
        </div>
      ),
    },
  ];

  return (
    <Card
      className={styles.formCard}
      title={"智能体 Loop 设置"}
    >
      <Tabs defaultActiveKey="react" items={tabItems} size="small" />
    </Card>
  );
}
