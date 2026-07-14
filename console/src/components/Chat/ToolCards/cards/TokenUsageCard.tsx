import React from "react";
import { DashboardOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell, DefaultBlock } from "../shared";
import { stringifyResult } from "../shared/utils";

export interface TokenUsageCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const TokenUsageCard: React.FC<TokenUsageCardProps> = ({
  content,
  isStreaming,
}) => {
    const title = "查询 Token 用量";
  const resultText = stringifyResult(content.result);

  return (
    <ToolCardShell
      content={content}
      isStreaming={isStreaming}
      icon={<DashboardOutlined />}
      title={title}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default TokenUsageCard;
