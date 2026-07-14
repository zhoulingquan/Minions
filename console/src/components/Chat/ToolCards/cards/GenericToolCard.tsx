/**
 * GenericToolCard — fallback card for tool calls not in the builtin registry.
 *
 * Shows the tool name + spinner while no output is available,
 * then a collapsible result block once the tool completes.
 */

import React from "react";
import { ToolOutlined } from "@ant-design/icons";
import type { ToolCallContent } from "../shared/types";
import { ToolCardShell } from "../shared";
import { DefaultBlock } from "../shared";
import { stringifyResult } from "../shared/utils";

export interface GenericToolCardProps {
  content: ToolCallContent;
  isStreaming?: boolean;
}

const GenericToolCard: React.FC<GenericToolCardProps> = ({
  content,
  isStreaming,
}) => {
    const toolLabel = content.serverLabel
    ? `${content.serverLabel} / ${content.name}`
    : content.name;
  const resultText = stringifyResult(content.result);

  return (
    <ToolCardShell
      icon={<ToolOutlined />}
      title={`执行 ${toolLabel}`}
      content={content}
      isStreaming={isStreaming}
    >
      {resultText && <DefaultBlock title="Output" content={resultText} />}
    </ToolCardShell>
  );
};

export default GenericToolCard;
