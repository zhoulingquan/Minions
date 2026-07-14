import {
  Form,
  Card,
  Switch,
  Input,
  Collapse,
  Select,
} from "@agentscope-ai/design";
import { SliderWithValue } from "./SliderWithValue";
import styles from "../index.module.less";

interface LightContextCardProps {
  maxInputLength: number;
}

export function LightContextCard({ maxInputLength }: LightContextCardProps) {
  const compactThresholdRatio = Form.useWatch([
    "light_context_config",
    "context_compact_config",
    "compact_threshold_ratio",
  ]);
  const reserveThresholdRatio = Form.useWatch([
    "light_context_config",
    "context_compact_config",
    "reserve_threshold_ratio",
  ]);

  const compactThreshold = Math.floor(
    (maxInputLength ?? 0) * (compactThresholdRatio ?? 0.8),
  );
  const reserveThreshold = Math.floor(
    (maxInputLength ?? 0) * (reserveThresholdRatio ?? 0.1),
  );

  return (
    <Card
      className={styles.formCard}
      title={"上下文管理"}
    >
      <Form.Item
        label={"对话存储路径"}
        name={["light_context_config", "dialog_path"]}
        tooltip={"对话记录持久化存储的相对路径（相对于 working_dir）"}
      >
        <Input placeholder={"dialog"} />
      </Form.Item>

      <Form.Item
        label={"byte/Token 估算除数"}
        name={["light_context_config", "token_count_estimate_divisor"]}
        rules={[
          {
            required: true,
            message: "估算除数为必填项",
          },
        ]}
        tooltip={"基于字节数估算 token 数的除数（token 数 ≈ 字节数 / 除数）。推荐值：3.75 ~ 4。"}
      >
        <SliderWithValue
          min={2}
          max={5}
          step={0.25}
          marks={{ 2: "2", 3: "3", 4: "4", 5: "5" }}
        />
      </Form.Item>

      <Collapse
        items={[
          {
            key: "contextCompact",
            label: "上下文压缩",
            children: (
              <>
                <Form.Item
                  label={"启用上下文压缩"}
                  name={[
                    "light_context_config",
                    "context_compact_config",
                    "enabled",
                  ]}
                  valuePropName="checked"
                  tooltip={"自动压缩上下文，防止上下文窗口溢出"}
                >
                  <Switch />
                </Form.Item>

                <Form.Item
                  label={"上下文压缩阈值比例"}
                  name={[
                    "light_context_config",
                    "context_compact_config",
                    "compact_threshold_ratio",
                  ]}
                  rules={[
                    {
                      required: true,
                      message: "上下文压缩比例为必填项",
                    },
                  ]}
                  tooltip={"当上下文长度达到最大上下文长度的该比例时，触发自动压缩"}
                >
                  <SliderWithValue
                    min={0.1}
                    max={0.9}
                    step={0.01}
                    marks={{ 0.1: "0.1", 0.5: "0.5", 0.9: "0.9" }}
                  />
                </Form.Item>

                <Form.Item
                  label={"压缩触发阈值（tokens）"}
                  tooltip={"根据最大上下文长度与压缩阈值比例自动计算，上下文超过此 token 数时触发压缩"}
                >
                  <Input
                    disabled
                    value={
                      compactThreshold > 0
                        ? compactThreshold.toLocaleString()
                        : ""
                    }
                    placeholder={"自动计算"}
                  />
                </Form.Item>

                <Form.Item
                  label={"上下文保留阈值比例"}
                  name={[
                    "light_context_config",
                    "context_compact_config",
                    "reserve_threshold_ratio",
                  ]}
                  rules={[
                    {
                      required: true,
                      message: "上下文保留比例为必填项",
                    },
                  ]}
                  tooltip={"为保持上下文连贯性，该比例的最新上下文会被保留，不会被压缩"}
                >
                  <SliderWithValue
                    min={0.01}
                    max={0.3}
                    step={0.01}
                    marks={{ 0.01: "0.01", 0.15: "0.15", 0.3: "0.3" }}
                  />
                </Form.Item>

                <Form.Item
                  label={"保留阈值（tokens）"}
                  tooltip={"根据最大上下文长度与保留阈值比例自动计算，压缩后至少保留此 token 数的最新上下文"}
                >
                  <Input
                    disabled
                    value={
                      reserveThreshold > 0
                        ? reserveThreshold.toLocaleString()
                        : ""
                    }
                    placeholder={"自动计算"}
                  />
                </Form.Item>
              </>
            ),
          },
          {
            key: "toolResultPruning",
            label: "工具结果压缩",
            children: (
              <>
                <Form.Item
                  label={"启用工具结果压缩"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "enabled",
                  ]}
                  valuePropName="checked"
                  tooltip={"对过长的工具调用结果进行压缩，节省上下文空间"}
                >
                  <Switch />
                </Form.Item>

                <Form.Item
                  label={"最新工具结果范围"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "pruning_recent_n",
                  ]}
                  rules={[
                    {
                      required: true,
                      message: "最新工具结果范围为必填项",
                    },
                  ]}
                  tooltip={"将消息列表分为两段：最近的 N 条消息与更早的消息，两段分别使用不同的压缩字节阈值"}
                >
                  <SliderWithValue
                    min={1}
                    max={10}
                    step={1}
                    marks={{ 1: "1", 5: "5", 10: "10" }}
                  />
                </Form.Item>

                <Form.Item
                  label={"早期消息压缩阈值（bytes）"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "pruning_old_msg_max_bytes",
                  ]}
                  rules={[
                    {
                      required: true,
                      message: "超出recent_n的工具调用结果最大字符数为必填项",
                    },
                  ]}
                  tooltip={"早期消息（N 条以外）中工具结果超过此字节数时将被压缩，须小于最新消息阈值"}
                >
                  <Input
                    placeholder={"请输入字符阈值"}
                  />
                </Form.Item>

                <Form.Item
                  label={"最新消息压缩阈值（bytes）"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "pruning_recent_msg_max_bytes",
                  ]}
                  rules={[
                    {
                      required: true,
                      message: "recent_n内的工具调用结果最大字符数为必填项",
                    },
                  ]}
                  tooltip={"最近 N 条消息中工具结果超过此字节数时将被压缩，同时也是 read_file 工具单次读取的最大字节上限，须大于等于早期消息阈值"}
                >
                  <Input
                    placeholder={"请输入字符阈值"}
                  />
                </Form.Item>

                <Form.Item
                  label={"工具调用的文件保留天数"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "offload_retention_days",
                  ]}
                  rules={[
                    {
                      required: true,
                      message: "工具调用的文件保留天数为必填项",
                    },
                  ]}
                  tooltip={"压缩后的工具结果文件保留天数，过期自动清理"}
                >
                  <SliderWithValue
                    min={1}
                    max={10}
                    step={1}
                    marks={{ 1: "1", 5: "5", 10: "10" }}
                  />
                </Form.Item>

                <Form.Item
                  label={"豁免文件后缀"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "exempt_file_extensions",
                  ]}
                  tooltip={"这些文件后缀的 read_file 工具结果将使用最新消息的压缩阈值，而不是早期消息阈值"}
                >
                  <Select
                    mode="tags"
                    placeholder={".md, .txt, .json"}
                    tokenSeparators={[",", " "]}
                    style={{ width: "100%" }}
                  />
                </Form.Item>

                <Form.Item
                  label={"豁免工具名称"}
                  name={[
                    "light_context_config",
                    "tool_result_pruning_config",
                    "exempt_tool_names",
                  ]}
                  tooltip={"这些工具的调用结果将使用最新消息的压缩阈值，而不是早期消息阈值"}
                >
                  <Select
                    mode="tags"
                    placeholder={"chat_with_agent, list_agents"}
                    tokenSeparators={[",", " "]}
                    style={{ width: "100%" }}
                  />
                </Form.Item>
              </>
            ),
          },
        ]}
      />
    </Card>
  );
}
