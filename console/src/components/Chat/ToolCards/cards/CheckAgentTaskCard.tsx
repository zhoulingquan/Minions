import React from "react";
import { SyncOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { stringifyResult } from "../shared/utils";

export interface CheckAgentTaskCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const CheckAgentTaskCard: React.FC<CheckAgentTaskCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const agent = (params.agent_id || params.to_agent || "") as string;
  const taskId = (params.task_id || "") as string;

  let title: string;
  if (agent && taskId) {
    title = `检查 ${agent} #${taskId}`;
  } else if (agent) {
    title = `检查 ${agent}`;
  } else {
    title = "检查 任务";
  }

  const resultText = stringifyResult(content.result);

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<SyncOutlined />}
      title={title}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default CheckAgentTaskCard;
