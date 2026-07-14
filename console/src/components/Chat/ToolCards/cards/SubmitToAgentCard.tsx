import React from "react";
import { RocketOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell } from "../shared";

export interface SubmitToAgentCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const SubmitToAgentCard: React.FC<SubmitToAgentCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const agent = (params.to_agent || "") as string;
  const task = (params.text || "") as string;
  const taskShort = task.length > 20 ? task.slice(0, 20) + "…" : task;
  const title = agent
    ? `提交 ${agent}${taskShort ? " " + taskShort : ""}`
    : "提交 任务";

  const inlineResult = (() => {
    if (content.status !== "done" || !content.result) return null;
    const result = typeof content.result === "string" ? content.result : "";
    if (!result) return null;
    const match = result.match(/\[TASK_ID:\s*(.+?)\]/);
    return match
      ? `任务 #${match[1]}`
      : "已提交";
  })();

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<RocketOutlined />}
      title={title}
      inlineResult={inlineResult}
    />
  );
};

export default SubmitToAgentCard;
