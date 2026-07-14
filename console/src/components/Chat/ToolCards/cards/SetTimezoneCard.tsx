import React from "react";
import { GlobalOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell } from "../shared";
import { stringifyResult } from "../shared/utils";

export interface SetTimezoneCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const SetTimezoneCard: React.FC<SetTimezoneCardProps> = ({
  content,
  isStreaming,
}) => {
    const params = content.params || {};
  const title = `设置 ${(params.timezone_name || "") as string}`;

  const inlineResult =
    content.status === "done" && content.result
      ? stringifyResult(content.result) || null
      : null;

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<GlobalOutlined />}
      title={title}
      inlineResult={inlineResult}
    />
  );
};

export default SetTimezoneCard;
